#!/usr/bin/env python3
"""
Convert one or more country Excel files (Q/A format) into a normalized rules.json
that your MCP server can load.

Usage examples:
  # Minimal: add three files with explicit country codes
  python tools/xls_to_rules.py --out rules.json \
      --add GB "EU Rules UK.xlsx" \
      --add FR "EU Rules France.xlsx" \
      --add CH "EU Rules Switzerland.xlsx"

  # Append to an existing rules.json (merge/overwrite per country+question)
  python tools/xls_to_rules.py --out rules.json --append \
      --add DE "EU Rules Germany.xlsx"

Notes:
  - Expected columns (case-insensitive): Question, Answer, (optional) Links
  - If 'Links' is missing, URLs inside the Answer are auto-extracted.
  - last_reviewed defaults to today; override with --last-reviewed YYYY-MM-DD
  - confidence defaults to 'medium'
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
  import pandas as pd  # type: ignore
except Exception as e:
  print("This tool requires pandas. Try: pip install pandas openpyxl", file=sys.stderr)
  raise

# --- Topic inference (lightweight, editable) --------------------------------
TOPIC_RULES: List[Tuple[re.Pattern[str], str]] = [
    (re.compile(r"(customs|poe|port of entry|schengen|immigration)", re.I), "Customs/Schengen"),
    (re.compile(r"(fis|listening\s+squawk|listening\s+code|ats|clearance)", re.I), "FIS/ATC"),
    (re.compile(r"(ifr|vfr|cloudbreak|let-?down|night)\b", re.I), "IFR/VFR"),
    (re.compile(r"(airspace|class\s+[cdegb])", re.I), "Airspace"),
    (re.compile(r"(flight\s*plan|autorouter|skydemon|foreflight)", re.I), "Paperwork"),
]

URL_RE = re.compile(r"https?://\S+", re.I)

def slugify(s: str) -> str:
    s = s.lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return re.sub(r"-{2,}", "-", s)

def qid_for(question_text: str) -> str:
    base = slugify(question_text)[:80]
    h = hashlib.blake2b(question_text.encode("utf-8"), digest_size=6).hexdigest()
    return f"{base}-{h}"

def infer_topic(question_text: str) -> Optional[str]:
    for pat, topic in TOPIC_RULES:
        if pat.search(question_text or ""):
            return topic
    return None

def extract_links(answer: str, explicit_links: Optional[str]) -> List[str]:
    links: List[str] = []
    if explicit_links:
        # split on common separators; keep only urls
        parts = re.split(r"[\s,;]+", explicit_links)
        links.extend([p for p in parts if p and p.lower().startswith(("http://","https://"))])
    for m in URL_RE.findall(answer or ""):
        if m not in links:
            links.append(m)
    return links

def find_col(df, candidates: List[str]) -> Optional[str]:
    cols = {c.lower().strip(): c for c in df.columns}
    for cand in candidates:
        key = cand.lower()
        if key in cols:
            return cols[key]
    # fuzzy contains
    for k, orig in cols.items():
        if any(k.startswith(c.lower()) for c in candidates):
            return orig
    return None

def load_excel(country_code: str, xlsx_path: Path) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Returns (questions, answers) partial lists extracted from the file.
    Handles both files with headers and files without headers (data starts at first row).
    """
    country_code = country_code.upper()
    xl = pd.read_excel(xlsx_path, sheet_name=None)  # all sheets
    questions: Dict[str, Dict[str, Any]] = {}
    answers: List[Dict[str, Any]] = []

    for sheet_name, df in xl.items():
        if df is None or df.empty:
            continue
        
        # Try reading with headers first (backward compatibility)
        qcol = None
        acol = None
        lcol = None
        
        # Normalize columns and try to find by name
        df.columns = [str(c).strip() for c in df.columns]
        qcol = find_col(df, ["Question","Questions","Q"])
        acol = find_col(df, ["Answer","Answers","A","Response"])
        lcol = find_col(df, ["Links","Link","Sources","Source"])
        
        # If no headers found, read without headers and use column indices
        if not qcol or not acol:
            # Re-read this sheet without headers
            xl_no_header = pd.read_excel(xlsx_path, sheet_name=sheet_name, header=None)
            if xl_no_header is not None and not xl_no_header.empty:
                df = xl_no_header
                # Use column indices: 0 = question, 1 = answer, 2 = links (optional)
                qcol = 0
                acol = 1
                if df.shape[1] > 2:
                    lcol = 2

        if qcol is None or acol is None:
            # Skip this sheet if structure doesn't match
            continue

        q_prefix = ""
        for _, row in df.iterrows():
            q = str(row[qcol]).strip() if pd.notna(row[qcol]) else ""
            a = str(row[acol]).strip() if pd.notna(row[acol]) else ""
            if not q and not a:
                q_prefix = ""
                continue
            if q and not a:
                q_prefix = q
                continue

            if q and a and q_prefix:
                q = f"{q_prefix} {q}"
            qid = qid_for(q)
            if qid not in questions:
                questions[qid] = {
                    "question_id": qid,
                    "question_text": q,
                    "topic": infer_topic(q),
                    "tags": [],  # keep empty for now; can enrich later
                }
            explicit_links = str(row[lcol]).strip() if lcol is not None and pd.notna(row[lcol]) else None
            links = extract_links(a, explicit_links)
            answers.append({
                "question_id": qid,
                "country_code": country_code,
                "answer_html": a,                # keep as-is; may already contain HTML fragments
                "links": links,
            })
    return list(questions.values()), answers

def merge_rules(existing: Dict[str, Any], new_q: List[Dict[str, Any]], new_a: List[Dict[str, Any]],
                last_reviewed: Optional[str], confidence: str) -> Dict[str, Any]:
    q_by_id = {q["question_id"]: q for q in existing.get("questions", [])}
    a_by_key = {(a["question_id"], a["country_code"]): a for a in existing.get("answers", [])}

    # merge questions
    for q in new_q:
        if q["question_id"] in q_by_id:
            # if wording differs slightly, keep the original; you can add auditing here
            pass
        else:
            q_by_id[q["question_id"]] = q

    # merge answers (overwrite per question+country)
    for a in new_a:
        rec = dict(a)
        if last_reviewed:
            rec["last_reviewed"] = last_reviewed
        rec["confidence"] = confidence
        a_by_key[(rec["question_id"], rec["country_code"])] = rec

    out = {
        "questions": sorted(q_by_id.values(), key=lambda x: x["question_text"].lower()),
        "answers": sorted(a_by_key.values(), key=lambda x: (x["question_id"], x["country_code"])),
    }
    return out

def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(description="Convert country Excel Q/A files into rules.json")
    p.add_argument("--out", required=True, help="Output rules.json path")
    p.add_argument("--append", action="store_true", help="Append into existing rules.json if present")
    p.add_argument("--last-reviewed", default=dt.date.today().isoformat(), help="YYYY-MM-DD for last_reviewed (default: today)")
    p.add_argument("--confidence", default="medium", choices=["low","medium","high"])
    p.add_argument("--add", action="append", nargs=2, metavar=("CC","XLSX"),
                   help="Add Excel file for country code CC (ISO-2), can be repeated")
    args = p.parse_args(argv)

    out_path = Path(args.out)
    if not args.add:
        p.error("Provide at least one --add CC XLSX")

    combined: Dict[str, Any] = {"questions": [], "answers": []}
    if args.append and out_path.exists():
        try:
            combined = json.loads(out_path.read_text(encoding="utf-8"))
        except Exception:
            print(f"Warning: failed to parse existing {out_path}, starting fresh", file=sys.stderr)
            combined = {"questions": [], "answers": []}

    for cc, fpath in args.add:
        xlsx = Path(fpath).expanduser()
        if not xlsx.exists():
            print(f"Error: file not found {xlsx}", file=sys.stderr)
            return 2
        q, a = load_excel(cc, xlsx)
        combined = merge_rules(combined, q, a, last_reviewed=args.last_reviewed, confidence=args.confidence)
        print(f"Loaded {len(q)} questions / {len(a)} answers from {cc}:{xlsx.name}")

    # normalize fields naming for answers: links_json vs links; keep 'links' for MCP, but also write links_json for future MySQL loader
    for rec in combined["answers"]:
        if "links_json" not in rec:
            rec["links_json"] = rec.get("links", [])

    out_path.write_text(json.dumps(combined, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {out_path} with {len(combined['questions'])} questions and {len(combined['answers'])} answers.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())