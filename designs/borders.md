# Border-area membership & crossing requirements

`euro_aip.borders` is pure, offline reference data (no network, no I/O) that
answers a single question consumers keep re-encoding: **what border formalities
apply when flying between two countries?**

Two overlapping-but-distinct European blocs drive the answer:

- the **Schengen area** → drives whether **immigration** (passport) applies;
- the **EU customs union** → drives whether **customs** applies.

The memberships do not coincide:

- `CH`, `NO`, `IS`, `LI` are Schengen but **outside** the EU customs union.
- `CY`, `IE` are in the EU customs union but **outside** Schengen.

So France→Switzerland needs customs but no immigration, while France→Ireland
needs immigration but no customs.

## API

```python
from euro_aip.borders import (
    is_schengen,            # (cc) -> bool
    is_eu_customs_union,    # (cc) -> bool
    is_known,               # (cc) -> bool  (in either table)
    crossing_requirements,  # (from_cc, to_cc) -> CrossingRequirements
)
```

All predicates take ISO-3166-1 alpha-2 codes and are case-insensitive.

`crossing_requirements(from_cc, to_cc)` returns a frozen dataclass:

```python
CrossingRequirements(
    immigration_required: bool,  # not (both Schengen)
    customs_required: bool,      # not (both EU customs union)
)
```

Rules:

- `immigration_required = not (is_schengen(from) and is_schengen(to))`
- `customs_required     = not (is_eu_customs_union(from) and is_eu_customs_union(to))`
- Same country → both `False` (domestic flight, no border).
- A country in neither bloc table — a recognized third country like `GB`, or an
  unrecognized code — is treated as outside every bloc, so both flags default to
  `True`. That is correct for a third country and a safe over-flag for a bad
  code. Callers that must reject bad codes should validate the ISO code (e.g.
  via `is_known`, or their own airport metadata) before calling.

### Examples

| From → To | immigration | customs | note |
|-----------|:-----------:|:-------:|------|
| FR → GB   | ✓ | ✓ | GB left both blocs → full border |
| FR → CH   | ✗ | ✓ | Schengen but not EU-customs |
| FR → IE   | ✓ | ✗ | EU-customs but not Schengen |
| FR → DE   | ✗ | ✗ | both blocs |

```python
>>> crossing_requirements("FR", "CH")
CrossingRequirements(immigration_required=False, customs_required=True)
```

### Airport convenience properties

`Airport` exposes two derived properties (from `iso_country`). Both return
`None` when the country is unknown, so "outside the area" stays distinct from
"couldn't determine":

```python
airport.is_schengen           # Optional[bool]
airport.is_eu_customs_union    # Optional[bool]
```

## Known edge cases (caller may special-case)

- **IE↔GB Common Travel Area** — the rule flags immigration (GB is not
  Schengen), but the CTA means there is no immigration check in practice.
- **Channel Islands / Isle of Man** (`JE`, `GG`, `IM`) — outside both blocs, so
  a flight to/from the EU reads as customs + immigration, which is correct.

## Airport side: reading the AIP customs field (`euro_aip.interp`)

`crossing_requirements` says *whether* customs/immigration applies; the
airport's own AIP says *how* to arrange it. That text lives in standardised
field **302** ("Custom and Immigration", an `AIPEntry` with `std_field_id=302`)
and is free text in French/English. `CustomInterpreter` turns it into a dict.
It is a pure text-to-dict function: it never reads the model it is constructed
with, and the optional `airport` argument currently has no effect.

```python
from euro_aip.interp import CustomInterpreter    # or InterpreterFactory.create_interpreter('custom', model)

interp = CustomInterpreter(model)
entry = next(e for e in airport.aip_entries if e.std_field_id == 302)
info = interp.interpret_field_value(entry.value, airport)
info['weekday_pn'], info['weekend_pn']   # "24H" | "H24" | "O/R" | None
info['contact_emails']                   # ['bsep-le-havre@douane.finances.gouv.fr', ...]
info['email_subject']                    # 'ppf le havre octeville' (LFOH) or None
```

Fields (`get_structured_fields()`), plus `raw_value`:

- **When**: `weekday_pn` / `weekend_pn` (notice period), `advance_notice_required`
  (False when both are `H24`/`O/R`), `custom_available`, `immigration_available`
  (keyword presence, not a guarantee of service).
- **How** (euro-aip >= 0.18.0): `contact_emails`, `contact_urls` (online
  notification forms), `mentions_myhandling` (notification goes through the
  myhandling portal: "Via My Handling", `cy.myhandlingsoftware.com`), and
  `email_subject` (the subject line some airports mandate, matched from
  `subject:` / `objet :` followed by a quoted string, any quote style incl. `« »`).

Choices and why:

- **Contacts are read from the original text**, not the upper-cased copy the
  notice-period parsing uses: upper-casing would mangle URLs and the subject.
- **E-mails are lower-cased, de-duplicated, in order of appearance.** Order
  matters (the AIP lists the primary address first), and the same address is
  often repeated per time window (weekday/weekend).
- **Known AIP typos are fixed** in `_EMAIL_DOMAIN_FIXES`, e.g. LFMT publishes
  `douane.finance.gouv.fr`, which does not deliver; it maps to
  `douane.finances.gouv.fr`. Add new entries there rather than patching callers.
- The extractors (`extract_contact_emails`, `extract_contact_urls`,
  `mentions_myhandling`, `extract_email_subject`) are module-level functions in
  `interp_custom.py`, usable on other text.

Gotchas:

- Contacts are **not conditional**: "e-mail without handling, myhandling with
  handling" (LFLB) returns both the e-mails and `mentions_myhandling=True`; the
  condition stays only in `raw_value`.
- `myhandling` detection strips whitespace before matching, so "My Handling"
  matches; a hyphenated "My-Handling" would not.
- The subject regex stops at the first quote character, so a subject containing
  an apostrophe would be truncated.
- Consumer: `flyfun-forms/scripts/sync_aip_emails.py` feature-detects the
  contact fields via `"contact_emails" in interp.get_structured_fields()`, so
  keep the field names stable.

## Maintenance

Bloc memberships change — **review the tables in `euro_aip/borders.py`
annually**. Bulgaria and Romania fully joined Schengen in 2024–2025; Croatia
joined in 2023. Sources are cited in the module docstring.
