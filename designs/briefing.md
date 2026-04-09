# Briefing Module

> Parse flight briefings (ForeFlight PDFs, APIs) and query NOTAMs/weather with a fluent API

## Intent

Allow users to:
1. **Import** briefing data from multiple sources (ForeFlight PDFs, Autorouter API, Ogimet historical, ICAO FPL strings)
2. **Parse** structured data: NOTAMs, METARs, TAFs, routes
3. **Filter & query** with the same fluent patterns as `euro_aip` (chainable, set operations)
4. **Serialize** to JSON for cross-platform use (CLI, web, iOS)

**What should NOT change**: The source-agnostic design. Parsers work on any NOTAM/METAR text regardless of origin.

## Architecture

```
euro_aip/briefing/
├── models/          # Briefing, Notam, Route dataclasses
├── parsers/         # Standalone text parsers (NotamParser)
├── sources/         # BriefingSource implementations (ForeFlight, Autorouter, AvWx, Ogimet)
├── collections/     # NotamCollection (QueryableCollection)
├── categorization/  # Q-code, text rules, pipeline
├── weather/         # WeatherReport, WeatherParser, WeatherAnalyzer, WeatherCollection
└── filters/         # Filter utilities
```

**Key separation**: Sources extract raw text → Parsers convert to models → Collections filter/query

```
┌──────────────────┐     ┌──────────────────┐     ┌─────────────────────┐
│    Sources       │────▶│    Parsers       │────▶│    Collections      │
│ ForeFlightSource │     │ NotamParser      │     │ NotamCollection     │
│ AutorouterNotam  │     │ WeatherParser    │     │ WeatherCollection   │
│ AutorouterGramet │     │ ICAOFPLParser    │     │                     │
│ AvWxSource       │     │                  │     │                     │
│ OgimetSource     │     │                  │     │                     │
└──────────────────┘     └──────────────────┘     └─────────────────────┘
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

### Historical Weather (Ogimet)
```python
from datetime import date
from euro_aip.briefing import OgimetSource

# Fetch historical METAR/TAF for one airport over a date range
source = OgimetSource()
reports = source.fetch_history("EGLL", date(2026, 4, 1), date(2026, 4, 3))

# Or just METARs / just TAFs
metars = source.fetch_metars("EGLL", date(2026, 4, 7))
tafs = source.fetch_tafs("EGLL", date(2026, 4, 7))

# Returns standard WeatherReport objects — same as AvWxSource
for r in reports:
    print(r.observation_time, r.flight_category, r.raw_text)
```

### Source-Agnostic Parsing
```python
from euro_aip.briefing.parsers import NotamParser

# Parse from ANY text source - not tied to ForeFlight
notam = NotamParser.parse(raw_notam_text)
notams = NotamParser.parse_many(text_block)
```

### Route Resolution with Waypoints
```python
from euro_aip.models.route_resolver import RouteResolver

# Resolve mixed airport/waypoint route strings
resolver = RouteResolver(model)
route = resolver.resolve("EGTF VESAN POGOL LSGS")
# All spatial queries (along_route, get_route_navpoints) work with resolved coords
```

See [waypoints.md](./waypoints.md) for full waypoint architecture and data sources.

### ICAO Flight Plan Parsing
```python
from euro_aip.briefing import parse_icao_fpl

fpl = parse_icao_fpl("(FPL-N122DR-VG -S22T/L-SBDGORVY/LB2 -LFAT0930 ...)")
fpl.route                  # Route with departure, destination, waypoints, times
fpl.is_vfr                 # True
fpl.altitude_feet          # Parsed from F350→35000, A055→5500
fpl.has_gnss               # Equipment flags from field 10
fpl.speed_knots            # Speed converted to knots
fpl.other_info["PBN"]      # Field 18 key/value pairs

# With coordinate resolution
fpl = parse_icao_fpl(text, resolver=RouteResolver(model))
```

GPS coordinates in routes (e.g., `4830N00210E`) are parsed to RoutePoints with lat/lon.
Airways (e.g., `UL9`, `L28`) are skipped. Swift equivalent: `ICAOFlightPlanParser.parse()`.

### Autorouter NOTAM API
```python
from euro_aip.briefing import AutorouterNotamSource

source = AutorouterNotamSource(credential_manager)
notams = source.fetch_notams(["LFPG", "EGTT"], start_validity=start, end_validity=end)
```

### Autorouter GRAMET (Vertical Cross-Section)
```python
from euro_aip.briefing.sources import AutorouterGrametSource

source = AutorouterGrametSource(credential_manager)
image_bytes = source.fetch_gramet(
    waypoints=["EGTK", "LFPB", "LSGS"],
    altitude_ft=8000,
    departure_time=departure,
    duration_hours=4.5,
    fmt="pdf",  # or "png" (default)
)
```

### Using Pre-Obtained OAuth2 Tokens

When calling the Autorouter API from a web service where users have linked their
account via the OAuth2 authorization code flow (e.g. via `flyfun-common`), use
`set_token()` to inject the token directly instead of using client credentials:

```python
from euro_aip.utils.autorouter_credentials import AutorouterCredentialManager
from euro_aip.briefing.sources import AutorouterNotamSource, AutorouterGrametSource

# Token obtained externally (e.g. from flyfun-common's get_autorouter_token)
cred_manager = AutorouterCredentialManager(cache_dir)
cred_manager.set_token(access_token, expires_at=expiry_datetime)

# Same sources work with either credential method
notam_source = AutorouterNotamSource(cred_manager)
gramet_source = AutorouterGrametSource(cred_manager)
```

`AutorouterSource` (AIP data) also accepts a `token` parameter directly:
```python
from euro_aip.sources import AutorouterSource

source = AutorouterSource(cache_dir, token="bearer_token_from_db")
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
- Waypoints & route resolution: [waypoints.md](./waypoints.md)
- Key code: `euro_aip/briefing/`
- Similar patterns: [query_api_architecture.md](./query_api_architecture.md)
