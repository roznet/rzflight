# Briefing Module

> Parse flight briefings (ForeFlight PDFs, APIs) and query NOTAMs/weather with a fluent API

## Intent

Allow users to:
1. **Import** briefing data from multiple sources (ForeFlight PDFs first, APIs later)
2. **Parse** structured data: NOTAMs, METARs, TAFs, routes
3. **Filter & query** with the same fluent patterns as `euro_aip` (chainable, set operations)
4. **Serialize** to JSON for cross-platform use (CLI, web, iOS)

**What should NOT change**: The source-agnostic design. Parsers work on any NOTAM/METAR text regardless of origin.

## Architecture

```
euro_aip/briefing/
├── models/          # Briefing, Notam, Metar, Taf, Route dataclasses
├── parsers/         # Standalone text parsers (NotamParser, MetarParser)
├── sources/         # BriefingSource implementations (ForeFlight, AVWX)
├── collections/     # NotamCollection, WeatherCollection (QueryableCollection)
├── filters/         # Categorizers, scorers, presets
└── utils/           # ICAO Q-code decoder
```

**Key separation**: Sources extract raw text → Parsers convert to models → Collections filter/query

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Source    │────▶│   Parser    │────▶│ Collection  │
│ (ForeFlight)│     │ (standalone)│     │  (fluent)   │
└─────────────┘     └─────────────┘     └─────────────┘
     PDF              Any text           Filter/query
```

## Usage Examples

### Basic: Parse and Query
```python
from euro_aip.briefing import ForeFlightSource, CategorizationPipeline

# Parse → Categorize → Query
briefing = ForeFlightSource().parse("briefing.pdf")
CategorizationPipeline().categorize_all(briefing.notams)

# Fluent filtering (same pattern as euro_aip)
critical = (
    briefing.notams_query
    .for_airport("LFPG")
    .active_during(dep_time, arr_time)
    .runway_related()
    .all()
)
```

### Spatial and Time Filtering
```python
# NOTAMs along route corridor
enroute = briefing.notams_query.along_route(briefing.route, corridor_nm=25)

# Active during flight window
flight_start, flight_end = briefing.route.get_flight_window(buffer_minutes=60)
relevant = briefing.notams_query.active_during(flight_start, flight_end)
```

### Source-Agnostic Parsing
```python
from euro_aip.briefing.parsers import NotamParser

# Parse from ANY text source - not tied to ForeFlight
notam = NotamParser.parse(raw_notam_text)
notams = NotamParser.parse_many(text_block)
```

## Key Choices

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Parsers are standalone | `NotamParser.parse(text)` works without a source | Reusable, testable, source-agnostic |
| Follow euro_aip patterns | `QueryableCollection`, `CachedSource`, dataclasses | Consistency, familiar API |
| Categorization is pluggable | Pipeline of categorizers (Q-code, text rules, LLM) | Extensible, combinable |
| Time filtering uses windows | `active_during(start, end)` not just `active_now()` | Flight planning needs future windows |
| Coordinates on Route | `Route` holds waypoint coords for spatial queries | Enable `along_route()` filtering |

## Patterns

- **Fluent chaining**: All filters return new collections, chainable
- **Set operations**: `collection_a | collection_b`, `&`, `-` work like euro_aip
- **to_dict/from_dict**: All models serialize to JSON
- **Categorizers return CategorizationResult**: primary_category, categories set, tags set, confidence

## Gotchas

- **NOTAMs without coordinates**: Some NOTAMs lack coords - `along_route()` skips them, use `for_airport()` as fallback
- **Q-code not always present**: ForeFlight may abbreviate - text rules categorizer is backup
- **Time zones**: All times should be UTC, NOTAM effective times are UTC
- **Parse confidence**: Parser sets `parse_confidence` 0-1, check for partial parses

## References

- Filtering details: [briefing_filtering.md](./briefing_filtering.md)
- Parsing architecture: [briefing_parsing.md](./briefing_parsing.md)
- Key code: `euro_aip/briefing/`
- Similar patterns: [query_api_architecture.md](./query_api_architecture.md)
