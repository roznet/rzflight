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
├── models/          # Briefing, Notam, Route dataclasses
├── parsers/         # Standalone text parsers (NotamParser)
├── sources/         # BriefingSource implementations (ForeFlight)
├── collections/     # NotamCollection (QueryableCollection)
├── categorization/  # Q-code, text rules, pipeline
├── weather/         # WeatherReport, WeatherParser, WeatherAnalyzer, WeatherCollection
└── filters/         # Filter utilities
```

**Key separation**: Sources extract raw text → Parsers convert to models → Collections filter/query

```
┌─────────────┐     ┌──────────────────┐     ┌─────────────────────┐
│   Source    │────▶│    Parsers       │────▶│    Collections      │
│ (ForeFlight)│     │ NotamParser      │     │ NotamCollection     │
└─────────────┘     │ WeatherParser    │     │ WeatherCollection   │
     PDF            └──────────────────┘     └─────────────────────┘
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

### Weather Analysis
```python
from euro_aip.briefing import WeatherReport, FlightCategory

# Parse and analyze weather
metar = briefing.weather_query.metars().for_airport("LFPG").latest()
print(metar.flight_category)  # FlightCategory.VFR

# Wind components for runway
wc = metar.wind_components(270, "27")
print(f"Headwind: {wc.headwind}kt, Crosswind: {wc.crosswind}kt")
print(f"Within limits: {wc.within_limits(max_crosswind_kt=20)}")

# Find IFR or worse
bad_wx = briefing.weather_query.at_or_worse_than(FlightCategory.IFR).all()
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
- Weather module: [briefing_weather.md](./briefing_weather.md)
- Parsing architecture: [briefing_parsing.md](./briefing_parsing.md)
- Key code: `euro_aip/briefing/`
- Similar patterns: [query_api_architecture.md](./query_api_architecture.md)
