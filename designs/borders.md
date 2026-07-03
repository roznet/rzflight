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
    from_known: bool,            # origin found in the reference tables
    to_known: bool,              # destination found in the reference tables
)
```

Rules:

- `immigration_required = not (is_schengen(from) and is_schengen(to))`
- `customs_required     = not (is_eu_customs_union(from) and is_eu_customs_union(to))`
- Same country → both `False` (domestic flight, no border).
- Unknown country → the `*_required` flags default to `True` (treated as outside
  every bloc), but `from_known` / `to_known` is `False` so callers can report
  "couldn't determine" rather than assume an open border.

### Examples

| From → To | immigration | customs | note |
|-----------|:-----------:|:-------:|------|
| FR → GB   | ✓ | ✓ | GB in neither table (`to_known=False`) |
| FR → CH   | ✗ | ✓ | Schengen but not EU-customs |
| FR → IE   | ✓ | ✗ | EU-customs but not Schengen |
| FR → DE   | ✗ | ✗ | both blocs |

```python
>>> crossing_requirements("FR", "CH")
CrossingRequirements(immigration_required=False, customs_required=True,
                     from_known=True, to_known=True)
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

## Maintenance

Bloc memberships change — **review the tables in `euro_aip/borders.py`
annually**. Bulgaria and Romania fully joined Schengen in 2024–2025; Croatia
joined in 2023. Sources are cited in the module docstring.
