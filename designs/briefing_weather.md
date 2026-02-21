# Briefing: Weather Module

> Parse METAR/TAF reports and analyze flight conditions with fluent API

## Intent

Provide aviation weather analysis within the briefing module:
1. **Parse** METAR and TAF text into structured data via `metar_taf_parser` library
2. **Analyze** flight categories (VFR/MVFR/IFR/LIFR), wind components, TAF trends
3. **Filter** weather reports with the same fluent patterns as `NotamCollection`

Ported from `rzflight-save/python/weather/weather.py` — kept the valuable logic (FAA thresholds, trig-based wind components, TAF validity checking), discarded the monolithic design, web scraping, SQLite storage, and `eval()` calls.

**What should NOT change**: Weather lives in `briefing/weather/` (parallel to `categorization/`). It follows the same Source → Parser → Model → Collection pattern as NOTAMs.

## Architecture

```
euro_aip/briefing/weather/
├── models.py       # WeatherReport, FlightCategory, WindComponents, WeatherType
├── parser.py       # WeatherParser — wraps metar_taf_parser library
├── analysis.py     # WeatherAnalyzer — flight categories, wind math, TAF matching
├── collection.py   # WeatherCollection(QueryableCollection[WeatherReport])
└── __init__.py     # Public API exports
```

**Key design**: TAF trends are nested `WeatherReport` objects (same fields as main report), not a separate class. This eliminates complex attribute-copying logic from the old code.

## Usage Examples

### Parse and Analyze
```python
from euro_aip.briefing.weather import WeatherReport, FlightCategory

# Convenience class methods
report = WeatherReport.from_metar("METAR LFPG 211230Z 24015G25KT 9999 FEW040 18/09 Q1015")
print(report.flight_category)  # FlightCategory.VFR
print(report.wind_components(270, "27"))  # WindComponents(headwind=..., crosswind=...)

# From a briefing
briefing = ForeFlightSource().parse("briefing.pdf")
metar = briefing.weather_query.metars().for_airport("LFPG").latest()
bad_wx = briefing.weather_query.at_or_worse_than(FlightCategory.IFR).all()
```

### Wind Component Analysis
```python
from euro_aip.briefing.weather import WeatherAnalyzer

# Check multiple runways
runways = {"27L": 270, "09R": 90}
components = WeatherAnalyzer.wind_components_for_runways(report, runways)
for rwy, wc in components.items():
    print(f"{rwy}: headwind={wc.headwind}, crosswind={wc.crosswind}")
    print(f"  Within limits: {wc.within_limits(max_crosswind_kt=20)}")
```

### TAF Trend Matching
```python
taf = WeatherReport.from_taf("TAF LFPG 211100Z 2112/2218 24012KT 9999 FEW040 "
                              "TEMPO 2114/2118 4000 TSRA BKN020CB")
applicable = WeatherAnalyzer.find_applicable_taf(taf, check_time)
print(WeatherAnalyzer.compare_categories(metar.flight_category, applicable.flight_category))
```

## Data Models

### WeatherReport

Core fields — same structure for METARs, SPECIs, and TAF base/trends:

| Field | Type | Description |
|-------|------|-------------|
| `icao` | `str` | Airport ICAO code |
| `report_type` | `WeatherType` | METAR, SPECI, or TAF |
| `raw_text` | `str` | Original report text |
| `observation_time` | `datetime?` | Time of observation/issuance |
| `wind_direction` | `int?` | Degrees (None if variable/calm) |
| `wind_speed` | `int?` | Speed in knots |
| `wind_gust` | `int?` | Gust speed in knots |
| `wind_variable_from/to` | `int?` | Variable wind range |
| `wind_unit` | `str` | Wind unit: "KT", "MPS", "KMH" (default "KT") |
| `visibility_meters` | `int?` | Visibility in meters |
| `visibility_sm` | `float?` | Visibility in statute miles |
| `ceiling_ft` | `int?` | Lowest BKN/OVC layer in feet |
| `cavok` | `bool` | Ceiling And Visibility OK |
| `clouds` | `List[dict]` | `[{quantity, height, type}]` |
| `weather_conditions` | `List[str]` | `["RA", "TSRA", "-SN"]` |
| `temperature` / `dewpoint` | `int?` | Celsius |
| `altimeter` | `float?` | Pressure setting |
| `flight_category` | `FlightCategory?` | Computed from vis + ceiling |
| `validity_start/end` | `datetime?` | TAF validity period |
| `trends` | `List[WeatherReport]` | TAF change groups (nested) |
| `trend_type` | `str?` | "BECMG", "TEMPO", "FM" |
| `probability` | `int?` | TAF trend probability % |

### FlightCategory Enum

Ordered from worst to best. Supports `<`, `>`, `min()`, `sorted()`:

```python
FlightCategory.LIFR < FlightCategory.IFR < FlightCategory.MVFR < FlightCategory.VFR
min(FlightCategory.VFR, FlightCategory.IFR)  # → IFR
```

### WindComponents

| Field | Type | Description |
|-------|------|-------------|
| `headwind` | `float` | Positive = from ahead |
| `crosswind` | `float` | Positive = from right |
| `gust_headwind/crosswind` | `float?` | Gust components |
| `max_crosswind` | `float?` | Worst-case including variable wind |

`within_limits(max_crosswind_kt=20, max_tailwind_kt=10)` checks all components including gusts.

## Key Choices

| Decision | Rationale |
|----------|-----------|
| TAF trends as nested WeatherReport | Same fields, eliminates attribute-copying complexity |
| metar_taf_parser library | Handles METAR/TAF grammar; we extract fields from parsed objects |
| Safe fraction parsing | `_safe_parse_fraction("1/2")` replaces `eval()` from old code |
| Static methods on WeatherAnalyzer | Pure functions, no state — easy to test |
| Flight category on each trend | Each TAF group gets its own category independently |
| Visibility in both meters and SM | Library returns various formats ("10km", "3000m", "2SM") — we normalize both |

## FAA Flight Category Thresholds

| Category | Visibility | Ceiling |
|----------|-----------|---------|
| LIFR | < 1 SM | < 500 ft |
| IFR | 1 to < 3 SM | 500 to < 1000 ft |
| MVFR | 3 to 5 SM | 1000 to 3000 ft |
| VFR | > 5 SM | > 3000 ft |

Worst condition (ceiling or visibility) determines category.

## Gotchas

- **metar_taf_parser normalizes 9999**: Returns `"> 10km"` = 10000m, not 9999
- **Visibility format varies**: Library gives `"3000m"`, `"2SM"`, `"> 10km"` — parser handles all
- **CAVOK**: Sets both visibility (10000m) and ceiling (None) → always VFR
- **Variable wind without direction**: Uses full speed as worst-case crosswind
- **TAF validity month-crossing**: Parser handles end_day < start_day (spans month boundary)
- **Package name**: PyPI package is `metar-taf-parser-mivek`, not `metar-taf-parser`

## References

- Main briefing doc: [briefing.md](./briefing.md)
- Briefing models: [briefing_models.md](./briefing_models.md)
- Filtering patterns: [briefing_filtering.md](./briefing_filtering.md)
- Code: `euro_aip/briefing/weather/`
- Tests: `tests/briefing/test_weather/`
- Dependency: `metar-taf-parser-mivek>=1.6.0`
