Review target: $ARGUMENTS

If $ARGUMENTS is a GitHub PR URL or repo/pull/number:

- Use gh to fetch the PR diff and description
- Focus review on changed lines only
- Post the review as a PR comment using gh pr comment

Otherwise:

- Interpret $ARGUMENTS as a description of what to review
- Use git log, git diff, or file reads as appropriate to find the relevant changes

---

## Non-negotiable: post before you finish

This command usually runs headless in CI, where there is no follow-up turn. **A review
that is not posted did not happen.** So:

- Never end your turn with review work outstanding. "I'll compile the findings once the
  agents report back" is a failed run — the session ends there and the subagents are killed.
- If you delegate to subagents, pass `run_in_background: false` so you block on their
  reports and can synthesise them in the same turn. Never fan out into background agents.
- Large diffs are not a reason to defer. Shard the work yourself: `git diff` a subset of
  paths at a time, use `/tmp` for scratch files, and keep the findings in your own context.
- Your final action is `gh pr comment` (or, for a non-PR target, printing the review).
  Do that before you say anything terminal.

---

## Context loading

Before starting the review, read the following:

- `.claude/CLAUDE.md` for coding standards, parity rules and release conventions
- `designs/consumers.md` when the diff touches public API, parser output or the DB schema
- `designs/INDEX.md`, then the design docs for the modules being changed — use these for
  module intent and architecture
- If the PR body references a consumer issue (`roznet/<repo>#N`), read it with
  `gh issue view N -R roznet/<repo>` to understand what the caller needs

---

## Single-pass completeness requirement

**Do one complete pass. Find every issue. Report them all.**

Do not hold issues back for a follow-up round. If there are 10 real issues, report all 10
now. The goal is one complete review that can be acted on in one go, not an iterative
dialogue.

Group output by severity:

- **Critical** - bugs, logic errors, data corruption, security issues, unflagged breaking
  API changes: must fix before merge
- **Important** - architecture violations, design deviations, correctness problems,
  parity gaps, release mistakes: should fix
- **Minor** - best practices, missed optimisations, low-effort improvements: fix if low effort

Within each group, order by file/module for readability.

---

## Output format (machine-read — do not restyle)

`/process-review` watches for this comment by matching on its first line, so the
comment shape is a contract, not a stylistic choice. Emit exactly this skeleton
and do not substitute bold, plain text, or a different heading level for the
headings below:

```markdown
## Code Review

<one- or two-sentence summary of what was reviewed>

### Critical
- `path/to/file.py:123` — <finding>

### Important
- `path/to/file.swift:45` — <finding>

### Minor
- `path/to/file.py:67` — <finding>
```

Rules:

- The **first line is always exactly `## Code Review`** — including for a clean
  review, which follows it with a brief approval line and no severity sections.
- Severity headings are `### Critical` / `### Important` / `### Minor`.
- **Omit a severity section entirely when it has no findings** — do not emit an
  empty heading or a "none" placeholder.
- Findings are list items; lead each with the file path (and line where known).

---

## Review criteria

Apply all of the following in the single pass:

**General**
- Bugs and logic errors
- `.claude/CLAUDE.md` violations
- Deviations from documented architecture/design intent in `designs/`
- Code and logic duplication, opportunities for consolidation
- Simplicity, maintainability and extensibility

**Python**
- Type hints on public functions
- Error handling: exceptions caught at the right level, not swallowed
- Tests don't hit the network (HTTP is mocked)

**Swift**
- Memory management (retain cycles, weak/unowned correctness)
- Concurrency (actor isolation, `Sendable`, data races)
- `public` visibility: new API meant for consumers is `public`; nothing internal leaks out
- Force-unwraps / `try!` on parsed or network-derived data

---

## Library & public API

This repo is a library consumed by other projects (see `designs/consumers.md`:
flyfun-apps builds `airports.db` with it, flyfun-weather uses it at runtime, plus
flyfun-forms and flightlogstats). For every
change to a public name — Python module-level functions/classes/methods without a
leading `_`, Swift `public`/`open` declarations — check:

- **Breaking or additive?** A changed signature, removed/renamed name, changed return
  shape, a new required argument, or **different output for the same input** (a parser
  that now reads a field differently) is breaking. A breaking change the PR doesn't call
  out is **Critical**.
- **All callers updated** inside this repo (grep both the Python and Swift sides).
- **Version bump matches the change**: patch for fixes, minor for additive or breaking
  (while 0.x). If the PR bumps `euro_aip`, `pyproject.toml` and `euro_aip/__init__.py`
  must carry the same version. A bump that doesn't match the change is Important.
- **Defaults preserve old behaviour** when a new option is added, unless the PR says
  otherwise.
- **Swift has no version gate.** Every Swift consumer tracks `main`, so a breaking
  Swift change reaches the apps on their next package update. Treat it as breaking
  even when no version is bumped.
- **Which consumer is affected?** Name it in the finding (e.g. "flyfun-apps' AIRAC import
  calls this source"; "flyfun-weather reads this field"), so the owner knows where the
  follow-up lands.

**`airports.db` schema / `DatabaseStorage`.** The DB is written by Python (in flyfun-apps'
pipeline) and read by Swift (`Airport(db:ident:)`, `KnownAirports`, `KnownWaypoints`) in
the apps. A renamed/dropped column, a changed meaning or format of a stored value, or a
change to how `*_changes` / `airac_updates` are recorded must be matched by the Swift
readers (or flagged as breaking), and the PR must say which DBs need rebuilding. Missing
either is Critical.

---

## Parsers & external data sources

Most of this code reads messy real-world input: AIP pages and PDFs, NOTAMs, METAR/TAF,
ICAO flight plans, SIGMETs, vendor APIs and scraped sites.

**Robustness**
- Does the parser cope with real-world variants (extra whitespace, missing optional
  groups, out-of-order groups, month/year boundaries, lowercase, trailing `=`), or only
  the happy path in the test?
- Malformed input degrades to `None`/empty with a log line, rather than raising out of a
  batch or silently producing a wrong value. A wrong value is worse than a missing one.
- Tests include at least one real-shaped sample (redacted if needed), not only synthetic
  strings written to fit the code.

**Aviation correctness**
- Units and conventions: metres vs statute miles vs feet, true vs magnetic, UTC,
  lat/lon ordering, ICAO vs national codes (an airport's current ident vs `alt_ident`).
- Semantics match the relevant standard (ICAO Annex 3 for METAR/TAF, Doc 4444 for FPL,
  Doc 8126 for NOTAM/Q-codes). Flag anything that could mislead a pilot downstream.

**Network sources**
- Timeouts set; failures logged distinguishably; a failed optional call doesn't throw
  away the data already fetched.
- Bounded work: no unbounded retry loops, pagination without a limit, or per-item
  requests that scale with the input.
- Caching keys include everything that changes the answer (e.g. AIRAC cycle, date).

---

## Python ↔ Swift parity

Several parsers exist on both sides (see `.claude/CLAUDE.md` "Python ↔ Swift parity"). If the diff
changes logic in one of them, or one of the shared config files, check the counterpart:

- Shared files (`q_codes.json`, `document_references.json`, `aip_fields.csv`) changed in
  only one location → Important.
- Parsing logic fixed on one side only → flag it with the counterpart file, and whether
  the PR says it's deferred (an issue link is fine).

This is a flag-and-defer check: note the parity risk, don't ask for the other platform to
be implemented inside this PR unless the PR claims parity.

---

## Operational & consistency

Apply to every PR, briefly:

- **Growth and cost.** Caches, downloaded files or DB tables that grow without a bound or
  prune path; per-call work that multiplies (requests per waypoint, per FIR, per step).
- **Silent failure paths.** An error that is logged and skipped where the caller can't
  tell "no data" from "fetch failed"; a log line that can't be told apart from another
  failure.
- **Comments and docs that assert facts.** New or touched docstrings, design-doc lines
  and test fixtures must match the code.
- **Design docs.** A change to public API, behaviour or a documented choice should update
  the relevant `designs/` doc in the same PR.

---

## Do NOT flag

- Style issues not covered by `.claude/CLAUDE.md`
- Nits or minor suggestions below the Minor threshold
- Pre-existing issues not touched by this PR

If no issues found, post a brief approval comment — still under the `## Code Review`
first line required by the output-format contract above.
