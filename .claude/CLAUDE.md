# rzflight

Flight-planning libraries released from one repo:

- **`euro_aip/`**: Python package `euro-aip` on PyPI.
- **`Sources/RZFlight/`**: Swift package `RZFlight` (SPM; macOS 13 / iOS 16).

This is a **library** with several consumers (flyfun-apps builds `airports.db` with it,
flyfun-weather uses it at runtime, plus others). Before changing public API, parser
output or the DB schema, read `designs/consumers.md` to know who calls it.

## Design docs

Start from `designs/INDEX.md` (or `mcp__library-docs__get_design_doc`). Read the module's
doc before changing it, and update it in the same PR when you change behaviour, choices or
public API.

## Python

- Use **`euro_aip/venv/`**, not the repo-root `venv/` (which lacks the dependencies):
  `cd euro_aip && ./venv/bin/pytest tests/<path> -q`
- Tests never hit the network; mock HTTP.

## Swift

`swift build` / `swift test` from the repo root. Needs macOS (CoreLocation, MapKit,
UIKit), so not buildable in a Linux/cloud sandbox. If you can't build, say "written, not
compiled" and re-read touched Swift files for type/optional mistakes.

## Python ↔ Swift parity

Briefing/NOTAM parsing, Q-codes, document references, the ICAO FPL parser, METAR, route
resolution and airport lookup exist on **both** sides and must agree. Fix one side →
check the other, or open an issue naming the counterpart file. Shared config files must
stay byte-identical: `q_codes.json`, `document_references.json`
(`Sources/RZFlight/Resources/` ↔ `euro_aip/euro_aip/briefing/data/`) and `aip_fields.csv`
(`Sources/RZFlight/Resources/` ↔ `euro_aip/euro_aip/utils/`). The `airports.db` schema is
also shared: Python writes it, Swift reads it (`designs/consumers.md`).

## Versioning & releases

Procedure in `designs/releasing.md`. Rules to always keep:

- `euro_aip` version lives in `pyproject.toml` **and** `euro_aip/__init__.py` (must
  match); tags `v0.x.y`. RZFlight version is the bare `1.x.y` tag only.
- Bump in its own commit: `chore(release): bump euro_aip to 0.x.y`. Patch for fixes;
  minor for additive or breaking (while 0.x), and call breaking changes out in the PR.
- Building, `twine upload` and pushing tags are the **user's** confirmed step.

## Conventions

- Conventional commit subjects (`feat(scope): …`, `fix(scope): …`, `docs(designs): …`).
- Stage specific paths, never `git add -A`.
- `gh` must run with the sandbox disabled locally (otherwise it returns empty, exit 0).
- `Closes #N` only for issues filed by `roznet` here; outside reporters → `Addresses #N`
  (PR body and commit bodies); consumer-repo issues → `roznet/<repo>#N`, no keyword.
- Every PR push triggers the review bot (`.claude/commands/code-review.md`); handle it
  with `/process-review`.
