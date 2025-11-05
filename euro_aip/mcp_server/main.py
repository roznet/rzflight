#!/usr/bin/env python3
"""
MCP Server for Euro AIP Airport Database

This server provides tools for querying airport data, route planning, and flight information
to LLM clients like ChatGPT and Claude.

"""
from __future__ import annotations
import os
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional, TypedDict
import json

from fastmcp import FastMCP, Context

from euro_aip.storage.database_storage import DatabaseStorage
from euro_aip.models.euro_aip_model import EuroAipModel
from euro_aip.models.airport import Airport

# ---- Types for structured output (optional but nice) -------------------------
class AirportSummary(TypedDict, total=False):
    ident: str
    name: str
    municipality: Optional[str]
    country: Optional[str]
    latitude_deg: Optional[float]
    longitude_deg: Optional[float]
    longest_runway_length_ft: Optional[int]
    point_of_entry: bool

class AirportNearRoute(TypedDict):
    airport: AirportSummary
    distance_nm: float

# ---- Global model storage for FastMCP 2.11 --------------------------------
_model: Optional[EuroAipModel] = None
_rules: Optional[Dict[str, Any]] = None
_rules_index: Optional[Dict[str, Any]] = None

def get_model() -> EuroAipModel:
    """Get the global model instance."""
    if _model is None:
        raise RuntimeError("Model not initialized. Server not started properly.")
    return _model

# ---- Server with lifespan to manage resources --------------------------------
@asynccontextmanager
async def lifespan(app: FastMCP):
    global _model
    global _rules
    global _rules_index
    db_path = os.environ.get("AIRPORTS_DB", "airports.db")
    # Let FastMCP handle logging/levels via FASTMCP_LOG_LEVEL, etc.
    db_storage = DatabaseStorage(db_path)
    _model = db_storage.load_model()
    # Load rules store
    rules_path = os.environ.get("RULES_JSON", os.path.join(os.path.dirname(__file__), "rules.json"))
    try:
        with open(rules_path, "r", encoding="utf-8") as f:
            _rules = json.load(f)
        _rules_index = _build_rules_index(_rules or {})
    except Exception:
        _rules = {"questions": []}
        _rules_index = _build_rules_index(_rules)
    try:
        yield
    finally:
        # Add teardown if needed
        pass

mcp = FastMCP(
    name="euro_aip",
    instructions=(
        "Euro AIP Airport MCP Server. Tools for querying airport data, route planning, "
        "and country-specific aviation rules. Use two-letter ISO country codes (e.g., FR, GB). "
        "Rules tools support filters by category/tags; try listing available countries, categories, and tags first."
    ),
    lifespan=lifespan,
)

# ---- Helpers -----------------------------------------------------------------
def _airport_summary(a: Airport) -> AirportSummary:
    return {
        "ident": a.ident,
        "name": a.name,
        "municipality": a.municipality,
        "country": a.iso_country,
        "latitude_deg": getattr(a, "latitude_deg", None),
        "longitude_deg": getattr(a, "longitude_deg", None),
        "longest_runway_length_ft": getattr(a, "longest_runway_length_ft", None),
        "point_of_entry": bool(getattr(a, "point_of_entry", False)),
    }

def _pretty_airport(a: Airport) -> str:
    lines = [f"**{a.ident} - {a.name}**"]
    loc = f"{a.municipality or 'Unknown'}, {a.iso_country or 'Unknown'}"
    lines.append(f"Location: {loc}")
    if getattr(a, "latitude_deg", None) is not None and getattr(a, "longitude_deg", None) is not None:
        lines.append(f"Coordinates: {a.latitude_deg:.4f}, {a.longitude_deg:.4f}")
    if getattr(a, "longest_runway_length_ft", None) is not None:
        lines.append(f"Runway: {a.longest_runway_length_ft}ft")
    if getattr(a, "point_of_entry", False):
        lines.append("Border crossing point")
    return "\n".join(lines)

# ---- Rules helpers -----------------------------------------------------------
def _get_rules() -> Dict[str, Any]:
    if _rules is None:
        raise RuntimeError("Rules store not initialized. Server not started properly.")
    return _rules

def _get_rules_index() -> Dict[str, Any]:
    if _rules_index is None:
        raise RuntimeError("Rules index not initialized. Server not started properly.")
    return _rules_index

def _build_rules_index(rules: Dict[str, Any]) -> Dict[str, Any]:
    questions = rules.get("questions", []) or []
    by_id: Dict[str, Dict[str, Any]] = {}
    by_category: Dict[str, List[str]] = {}
    by_tag: Dict[str, List[str]] = {}
    categories: set[str] = set()
    tags: set[str] = set()
    for q in questions:
        qid = q.get("question_id")
        if not qid:
            continue
        by_id[qid] = q
        cat = (q.get("category") or "").strip()
        if cat:
            categories.add(cat)
            by_category.setdefault(cat.lower(), []).append(qid)
        for t in (q.get("tags") or []):
            tt = (t or "").strip()
            if not tt:
                continue
            tags.add(tt)
            by_tag.setdefault(tt.lower(), []).append(qid)
    return {
        "by_id": by_id,
        "by_category": by_category,
        "by_tag": by_tag,
        "categories": sorted(categories),
        "tags": sorted(tags),
    }

def _iter_filtered_questions(
    category: Optional[str],
    tags: Optional[List[str]],
    search: Optional[str],
    tags_mode: str = "any",
):
    rules = _get_rules()
    index = _get_rules_index()
    all_questions = rules.get("questions", []) or []
    search_lc = (search or "").strip().lower()
    cat_lc = (category or "").strip().lower()
    tags_lc = [t.strip().lower() for t in (tags or []) if t and t.strip()]

    def matches(q: Dict[str, Any]) -> bool:
        if cat_lc and (q.get("category") or "").strip().lower() != cat_lc:
            return False
        if tags_lc:
            qtags = {(t or "").strip().lower() for t in (q.get("tags") or [])}
            if tags_mode == "all":
                if not all(t in qtags for t in tags_lc):
                    return False
            else:
                if not any(t in qtags for t in tags_lc):
                    return False
        if search_lc:
            qt = (q.get("question_text") or "").lower()
            if search_lc not in qt:
                return False
        return True

    for q in all_questions:
        if matches(q):
            yield q

def _format_rule_item_for_country(q: Dict[str, Any], cc: str, include_unanswered: bool) -> Optional[Dict[str, Any]]:
    answers = q.get("answers_by_country", {}) or {}
    ans = answers.get(cc)
    if not ans and not include_unanswered:
        return None
    return {
        "question_id": q.get("question_id"),
        "question_text": q.get("question_text"),
        "category": q.get("category"),
        "tags": q.get("tags") or [],
        "answer_html": (ans or {}).get("answer_html"),
        "links": (ans or {}).get("links", []),
        "last_reviewed": (ans or {}).get("last_reviewed"),
    }

def _pretty_grouped_by_category(items: List[Dict[str, Any]], title: str) -> str:
    if not items:
        return f"No results for {title}."
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for it in items:
        grouped.setdefault(it.get("category") or "(uncategorized)", []).append(it)
    lines: List[str] = [f"**{title}:**\n"]
    for cat, arr in grouped.items():
        lines.append(f"**{cat}:**")
        for it in arr:
            q = it.get("question_text") or ""
            ans = it.get("answer_html")
            if ans:
                lines.append(f"- {q}\n  → {ans}")
            else:
                lines.append(f"- {q}\n  → (no answer)")
        lines.append("")
    return "\n".join(lines)

# ---- Tools -------------------------------------------------------------------
@mcp.tool(name="search_airports", description="Search by name, ICAO, IATA, or municipality")
def search_airports(query: str, max_results: int = 20, ctx: Context = None) -> Dict[str, Any]:
    model = get_model()
    q = query.upper().strip()
    matches: List[Airport] = []

    for a in model.airports.values():
        if (
            (q in a.ident)
            or (a.name and q in a.name.upper())
            or (getattr(a, "iata_code", None) and q in a.iata_code)
            or (a.municipality and q in a.municipality.upper())
        ):
            matches.append(a)
            if len(matches) >= max_results:
                break

    items = [_airport_summary(a) for a in matches]
    pretty = "No airports found." if not items else (
        f"Found {len(items)} airports matching '{query}':\n\n" + "\n\n".join(_pretty_airport(a) for a in matches)
    )
    return {"count": len(items), "items": items, "pretty": pretty}

@mcp.tool(name="find_airports_near_route", description="Find airports within max_distance_nm of a direct route")
def find_airports_near_route(from_icao: str, to_icao: str, max_distance_nm: float = 50.0, ctx: Context = None) -> Dict[str, Any]:
    model = get_model()
    results = model.find_airports_near_route([from_icao.upper(), to_icao.upper()], max_distance_nm)
    if not results:
        return {"count": 0, "items": [], "pretty": f"No airports within {max_distance_nm}nm of {from_icao}->{to_icao}."}

    items: List[AirportNearRoute] = []
    pretty_lines: List[str] = [f"Found {len(results)} airports within {max_distance_nm}nm of route {from_icao} to {to_icao}:\n"]
    for item in results:
        a: Airport = item["airport"]
        items.append({"airport": _airport_summary(a), "distance_nm": float(item["distance_nm"])})
        pretty_lines.append(f"{_pretty_airport(a)} (Distance: {item['distance_nm']:.1f}nm)\n")
    return {"count": len(items), "items": items, "pretty": "\n".join(pretty_lines)}

@mcp.tool(name="get_airport_details", description="Get details by ICAO")
def get_airport_details(icao_code: str, ctx: Context = None) -> Dict[str, Any]:
    model = get_model()
    icao = icao_code.strip().upper()
    if not icao:
        raise ValueError("ICAO code is required")

    a = model.get_airport(icao)
    if not a:
        return {"found": False, "pretty": f"Airport {icao} not found."}

    details: Dict[str, Any] = {
        "found": True,
        "airport": _airport_summary(a),
        "runways": {
            "count": len(a.runways),
            "longest_ft": getattr(a, "longest_runway_length_ft", None),
            "hard_surface": bool(getattr(a, "has_hard_runway", False)),
        },
        "procedures": {"count": len(a.procedures)},
        "point_of_entry": bool(getattr(a, "point_of_entry", False)),
        "standardized": [
            {"field": e.std_field, "value": e.value}
            for e in (a.get_standardized_entries() or [])
            if getattr(e, "std_field", None) and getattr(e, "value", None)
        ],
    }

    pretty = [
        f"**{a.ident} - {a.name}**",
        f"City: {a.municipality or 'Unknown'}",
        f"Country: {a.iso_country or 'Unknown'}",
    ]
    if getattr(a, "latitude_deg", None) is not None and getattr(a, "longitude_deg", None) is not None:
        pretty.append(f"Coordinates: {a.latitude_deg:.4f}, {a.longitude_deg:.4f}")
    if getattr(a, "elevation_ft", None) is not None:
        pretty.append(f"Elevation: {a.elevation_ft}ft")
    pretty += [
        "",
        f"Runways: {len(a.runways)} (longest {getattr(a, 'longest_runway_length_ft', 'Unknown')}ft)",
        f"Hard surface: {'Yes' if getattr(a,'has_hard_runway', False) else 'No'}",
        "",
        f"Procedures: {len(a.procedures)}",
        "",
        f"Border crossing point: {'Yes' if getattr(a,'point_of_entry', False) else 'No'}",
    ]
    details["pretty"] = "\n".join(pretty)
    return details

@mcp.tool(name="list_rules_for_country", description="List aviation rules answers for a country (ISO-2 code, e.g., FR, GB). Optional: category, tags, search. Example: {country:'FR', category:'VFR'}")
def list_rules_for_country(country: str,
                           category: Optional[str] = None,
                           tags: Optional[List[str]] = None,
                           include_unanswered: bool = False,
                           search: Optional[str] = None,
                           tags_mode: str = "any",
                           ctx: Context = None) -> Dict[str, Any]:
    cc = (country or "").strip().upper()
    items: List[Dict[str, Any]] = []
    for q in _iter_filtered_questions(category, tags, search, tags_mode):
        it = _format_rule_item_for_country(q, cc, include_unanswered)
        if it:
            items.append(it)
    pretty = _pretty_grouped_by_category(items, f"Rules for {cc}")
    return {"count": len(items), "items": items, "pretty": pretty}

@mcp.tool(name="compare_rules_between_countries", description="Compare aviation rules answers between two countries (ISO-2, e.g., FR vs GB). Optional: category, tags, search. Differences shown by default.")
def compare_rules_between_countries(country_a: str,
                                    country_b: str,
                                    category: Optional[str] = None,
                                    tags: Optional[List[str]] = None,
                                    search: Optional[str] = None,
                                    only_differences: bool = True,
                                    tags_mode: str = "any",
                                    ctx: Context = None) -> Dict[str, Any]:
    ca = (country_a or "").strip().upper()
    cb = (country_b or "").strip().upper()
    diffs: List[Dict[str, Any]] = []
    for q in _iter_filtered_questions(category, tags, search, tags_mode):
        qa = _format_rule_item_for_country(q, ca, True) or {}
        qb = _format_rule_item_for_country(q, cb, True) or {}
        a_html = (qa.get("answer_html") or "").strip()
        b_html = (qb.get("answer_html") or "").strip()
        different = (a_html != b_html)
        if only_differences and not different:
            continue
        diffs.append({
            "question_id": q.get("question_id"),
            "question_text": q.get("question_text"),
            "category": q.get("category"),
            "tags": q.get("tags") or [],
            "a": {"answer_html": qa.get("answer_html"), "links": qa.get("links", []), "exists": qa.get("answer_html") is not None},
            "b": {"answer_html": qb.get("answer_html"), "links": qb.get("links", []), "exists": qb.get("answer_html") is not None},
            "different": different,
        })
    # Pretty output
    if not diffs:
        return {"count": 0, "items": [], "pretty": f"No differences between {ca} and {cb}."}
    lines: List[str] = [f"**Comparison {ca} vs {cb}:**\n"]
    for item in diffs:
        lines.append(f"- {item['question_text']}")
        lines.append(f"  {ca}: {(item['a'].get('answer_html') or '(no answer)')}\n  {cb}: {(item['b'].get('answer_html') or '(no answer)')}\n")
    return {"count": len(diffs), "items": diffs, "pretty": "\n".join(lines)}

@mcp.tool(name="get_answers_for_questions", description="Get answers by country for specific question IDs (country keys are ISO-2 codes). Use list_rule_categories_and_tags and list_rules_for_country to discover IDs.")
def get_answers_for_questions(question_ids: List[str], ctx: Context = None) -> Dict[str, Any]:
    index = _get_rules_index()
    by_id = index["by_id"]
    items: List[Dict[str, Any]] = []
    for qid in question_ids or []:
        q = by_id.get(qid)
        if not q:
            continue
        items.append({
            "question_id": q.get("question_id"),
            "question_text": q.get("question_text"),
            "category": q.get("category"),
            "tags": q.get("tags") or [],
            "answers_by_country": q.get("answers_by_country", {}),
        })
    pretty_lines: List[str] = []
    for item in items:
        pretty_lines.append(f"**{item['question_text']}**")
        abc = item.get("answers_by_country") or {}
        for cc, ans in sorted(abc.items()):
            pretty_lines.append(f"- {cc}: {ans.get('answer_html') or '(no answer)'}")
        pretty_lines.append("")
    return {"count": len(items), "items": items, "pretty": "\n".join(pretty_lines)}

@mcp.tool(name="list_rule_categories_and_tags", description="List available aviation rule categories and tags in the rules store")
def list_rule_categories_and_tags(ctx: Context = None) -> Dict[str, Any]:
    index = _get_rules_index()
    categories = index.get("categories", [])
    tags = index.get("tags", [])
    # counts
    by_category = index.get("by_category", {})
    by_tag = index.get("by_tag", {})
    pretty = ["**Categories:**"]
    for c in categories:
        pretty.append(f"- {c} ({len(by_category.get(c.lower(), []))})")
    pretty.append("")
    pretty.append("**Tags:**")
    for t in tags:
        pretty.append(f"- {t} ({len(by_tag.get(t.lower(), []))})")
    return {
        "categories": categories,
        "tags": tags,
        "counts": {
            "by_category": {c: len(by_category.get(c.lower(), [])) for c in categories},
            "by_tag": {t: len(by_tag.get(t.lower(), [])) for t in tags},
        },
        "pretty": "\n".join(pretty),
    }

@mcp.tool(name="list_rule_countries", description="List available countries (ISO-2 codes) present in the aviation rules store")
def list_rule_countries(ctx: Context = None) -> Dict[str, Any]:
    rules = _get_rules()
    countries: set[str] = set()
    for q in rules.get("questions", []) or []:
        for cc in (q.get("answers_by_country", {}) or {}).keys():
            if cc:
                countries.add(str(cc).upper())
    items = sorted(countries)
    pretty = "**Rule Countries (ISO-2):**\n" + ("\n".join(f"- {c}" for c in items) if items else "(none)")
    return {"count": len(items), "items": items, "pretty": pretty}

@mcp.tool(name="get_border_crossing_airports", description="List airports that are border crossing points (optional country filter)")
def get_border_crossing_airports(country: Optional[str] = None, ctx: Context = None) -> Dict[str, Any]:
    model = get_model()
    airports = model.get_border_crossing_airports()
    if country:
        c = country.upper()
        airports = [a for a in airports if (a.iso_country or "").upper() == c]

    grouped: Dict[str, List[AirportSummary]] = {}
    for a in airports:
        grouped.setdefault(a.iso_country or "Unknown", []).append(_airport_summary(a))

    pretty_lines: List[str] = [f"**Border Crossing Airports{' in ' + country if country else ''}:**\n"]
    for cc, arr in grouped.items():
        pretty_lines.append(f"**{cc}:**")
        for item in arr:
            label = item["ident"] + " - " + (item["name"] or "")
            city = item.get("municipality")
            pretty_lines.append(f"- {label}" + (f" ({city})" if city else ""))
        pretty_lines.append("")
    return {"count": sum(len(v) for v in grouped.values()), "by_country": grouped, "pretty": "\n".join(pretty_lines)}

@mcp.tool(name="get_airport_statistics", description="Basic stats for airports (optional country)")
def get_airport_statistics(country: Optional[str] = None, ctx: Context = None) -> Dict[str, Any]:
    model = get_model()
    airports = model.get_airports_by_country(country.upper()) if country else list(model.airports.values())
    total = len(airports)
    stats = {
        "total_airports": total,
        "with_customs": sum(1 for a in airports if getattr(a, "point_of_entry", False)),
        "with_avgas": sum(1 for a in airports if getattr(a, "avgas", False)),
        "with_jet_a": sum(1 for a in airports if getattr(a, "jet_a", False)),
        "with_procedures": sum(1 for a in airports if a.procedures),
    }
    pct = lambda n: round((n / total * 100), 1) if total else 0.0
    stats.update({
        "with_customs_pct": pct(stats["with_customs"]),
        "with_avgas_pct": pct(stats["with_avgas"]),
        "with_jet_a_pct": pct(stats["with_jet_a"]),
        "with_procedures_pct": pct(stats["with_procedures"]),
    })

    pretty = [
        f"**Airport Statistics{' for ' + country if country else ''}:**",
        f"Total airports: {stats['total_airports']}",
        f"With customs: {stats['with_customs']} ({stats['with_customs_pct']}%)",
        f"With AVGAS: {stats['with_avgas']} ({stats['with_avgas_pct']}%)",
        f"With Jet A: {stats['with_jet_a']} ({stats['with_jet_a_pct']}%)",
        f"With procedures: {stats['with_procedures']} ({stats['with_procedures_pct']}%)",
    ]
    return {"stats": stats, "pretty": "\n".join(pretty)}

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Euro AIP MCP Server")
    parser.add_argument(
        "--transport",
        choices=["stdio", "http"],
        default="stdio",
        help="Transport type: stdio (default) or http (replaces legacy SSE).",
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host for HTTP transport (default: 127.0.0.1)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8001,
        help="Port for HTTP transport (default: 8001)",
    )
    parser.add_argument(
        "--database",
        default="airports.db",
        help="Database file (default: airports.db)",
    )
    parser.add_argument(
        "--rules",
        default=os.path.join(os.path.dirname(__file__), "rules.json"),
        help="Rules JSON file (default: mcp_server/rules.json)",
    )

    args = parser.parse_args()
    if args.database:
        os.environ["AIRPORTS_DB"] = args.database
    if args.rules:
        os.environ["RULES_JSON"] = args.rules

    if args.transport == "http":
        mcp.run(transport="http", host=args.host, port=args.port)
    else:
        mcp.run()