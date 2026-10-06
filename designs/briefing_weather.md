# Briefing: Weather Module

> Parse METAR/TAF reports and analyze flight conditions with fluent API

## Intent

Provide aviation weather analysis within the briefing module:
1. **Parse** METAR and TAF text into structured data via `metar_taf_parser` library
2. **Analyze** flight categories (VFR/MVFR/IFR/LIFR), wind components, TAF trends
3. **Filter** weather reports with the same fluent patterns as `NotamCollection`

Ported from `rzflight-save/python/weather/weather.py` — kept the valuable logic (FAA thresholds, trig-based wind components, TAF validity checking), discarded the monolithic design, SQLite storage, and `eval()` calls. Historical web scraping was later re-added as `OgimetSource` (clean implementation using BeautifulSoup).

**What should NOT change**: Weather lives in `briefing/weather/` (parallel to `categorization/`). It follows the same Source → Parser → Model → Collection pattern as NOTAMs.

## Architecture

```
euro_aip/briefing/weather/
├── models.py        # WeatherReport, FlightCategory, WindComponents, WeatherType
├── parser.py        # WeatherParser — wraps metar_taf_parser library
├── analysis.py      # WeatherAnalyzer — flight categories, wind math, TAF matching
├── collection.py    # WeatherCollection(QueryableCollection[WeatherReport])
├── route_weather.py # RouteWeatherService — METAR/TAF for airports along a route corridor
├── sigmet.py        # SigmetReport model + AWC isigmet parser
├── route_sigmet.py  # RouteSigmetService — SIGMETs intersecting a route corridor
└── __init__.py      # Public API exports
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

### Reading a TAF at a time
```python
taf = WeatherReport.from_taf("TAF LFPG 211100Z 2112/2218 24012KT 9999 FEW040 "
                              "BECMG 2113/2115 BKN025 TEMPO 2114/2118 4000 TSRA BKN020CB",
                             reference=issued_at)
cond = WeatherAnalyzer.taf_conditions_at(taf, check_time)   # None if the TAF isn't valid then
if cond is not None:
    cond.prevailing.flight_category     # main body + completed BECMG / started FM
    cond.worst_temporary                # worst TEMPO/PROB group, laid over prevailing
    cond.temporary_is_worse             # temporary strictly worse than prevailing?
    cond.flight_category                # worse of the two
    cond.significant_weather            # ["TSRA", "CB"]
    WeatherAnalyzer.trend_label(cond.worst_temporary)  # "TEMPO", "PROB30 TEMPO"
```

Rules `taf_conditions_at` applies:
- **Validity first** (`taf_covers`): aviationweather.gov returns an airport's latest TAF however old, so an expired TAF must not be read as current. Unparsed validity covers nothing.
- **Prevailing**: change groups in time order. `FM` replaces the forecast (including weather) from its start; `BECMG` applies fully after its period and, *during* it, as the field-wise worse of before/after.
- **Temporary** (`TEMPO`/`PROB`/`INTER`): each laid over prevailing, so fields a group doesn't restate are inherited and every group has a category.
- **Significant weather**: codes containing TS, FG, FZ, SN, GR, GS, PL, SQ, FC, then CB/TCU cloud types.
- Gotcha: the parser doesn't surface `NSW`, so weather a `BECMG` ends lingers (overstates — the safe direction).

`find_applicable_taf` (last matching group wins, base TAF otherwise, no validity check) is kept for compatibility; prefer `taf_conditions_at`. Pass `reference=` to `from_taf` when parsing a stored TAF — day-of-month fields resolve against now by default.

## Data Sources

Three weather sources, all producing standard `WeatherReport` objects:

| Source | Class | Use Case | Access Pattern |
|--------|-------|----------|----------------|
| aviationweather.gov | `AvWxSource` | Live weather | Multi-airport, last N hours |
| ForeFlight PDF | `ForeFlightSource` | Briefing extraction | Airports in the briefing |
| ogimet.com | `OgimetSource` | Historical weather | Single airport, date range |

### AvWxSource (Live)
```python
from euro_aip.briefing.sources import AvWxSource
source = AvWxSource()
reports = source.fetch_weather(["EGLL", "LFPG"])  # METARs + TAFs
```

### OgimetSource (Historical)
```python
from datetime import date
from euro_aip.briefing.sources import OgimetSource

source = OgimetSource()

# Single day
reports = source.fetch_history("EGLL", date(2026, 4, 7))

# Date range
reports = source.fetch_history("EGLL", date(2026, 4, 1), date(2026, 4, 3))

# Filter by type
metars = source.fetch_metars("EGLL", date(2026, 4, 7))
tafs = source.fetch_tafs("EGLL", date(2026, 4, 7))
```

Ogimet scrapes HTML from `display_metars2.php`. It automatically fixes TAF validity dates (the parser infers year/month from `now()`, but for historical data it uses the actual report datetime from ogimet). Results are sorted chronologically.

## Route Services

`RouteWeatherService` (METAR/TAF) and `RouteSigmetService` (SIGMETs) both take a route as a sequence of **route points — ICAO codes or `NavPoint`s** (`RoutePointLike = Union[str, NavPoint]`, in `route_weather.py`):

- A **code is placed only if it is an airport**, looked up with `EuroAipModel.find_airport_by_code`: current code first, then the previous code in `alt_ident`, so `["LELO", "LEMD"]` places LELO at LERJ in both services (SIGMET corridor used `airports.get` until #27 and dropped it). Navaids, fixes and lat/lon points passed as codes are dropped from the geometry with a warning per point, so the corridor silently runs straight between the airports. Callers that already resolved the route (e.g. a flight plan with waypoints) should pass `NavPoint`s.
- `result.route_icaos` stays a `List[str]` of names (`route_point_name`: the code, or the NavPoint's name, or `"lat,lon"` if unnamed).

### RouteWeatherService (`route_weather.py`)

`model.find_airports_near_route(points, distance_nm=corridor_nm)` finds the airports in the corridor, then one `AvWxSource.fetch_weather` call fetches them all. Route points that are 4-letter alphabetic codes are always included (distance 0) even if the airport table doesn't place them. Airports with an `alt_ident` (renumbered in the AIP, METAR still issued under the old code — LERJ/LELO) are fetched under both codes and filed under the current ident. Results are `RouteAirportWeather` (`latest_metar`, `latest_taf`, `has_weather`) sorted by enroute distance; `result.collection` merges everything into one `WeatherCollection`. `fetch_airports_weather(icaos)` is the no-geometry variant.

```python
from euro_aip.briefing.weather import RouteWeatherService
from euro_aip.models.navpoint import NavPoint

route = [egll.navpoint, NavPoint(latitude=50.95, longitude=1.85, name="CAL"), lfpg.navpoint]
result = RouteWeatherService().fetch_route_weather(route, corridor_nm=25, model=model)
for apt in result.airports_with_weather:
    print(apt.icao, apt.enroute_distance_nm, apt.latest_metar.flight_category)
```

**Corridor search is bbox-prefiltered** (`EuroAipModel.find_airports_near_route`): each segment gets a padded lat/lon box (corridor width + the great-circle poleward bulge ≈ L²/(8R)·tan(lat), doubled, + 1 nm), and an airport is only measured against segments whose box holds it. The box is conservative, so the result is identical to measuring every segment (checked on 1212 routes, 0 differences) but a 13-point route over the ~8.9k-airport table drops from ~550 ms to ~15 ms. Boxes reaching past ±89° lat or spanning the antimeridian disable the filter rather than risk a miss.

## SIGMETs

SIGMETs (Significant Meteorological Information) warn of in-flight hazards — turbulence, icing, convection, mountain waves, volcanic ash — bounded by a polygon and a vertical band over a FIR. They are modelled separately from `WeatherReport` (they are area/FIR hazards, not point observations) and follow the same Source → Model pattern.

Scope is **international (FIR) SIGMETs only** — AIRMET is deliberately out of scope.

### SigmetReport (`sigmet.py`)

Parsed from aviationweather.gov's `/api/data/isigmet` JSON. Coordinates use the euro_aip `(lon, lat)` convention so the polygon plugs straight into `euro_aip.utils.geometry` and the FIR machinery.

| Field | Type | Description |
|-------|------|-------------|
| `raw_text` | `str` | Original SIGMET bulletin (`rawSigmet`) |
| `fir_id` / `fir_name` | `str` / `str?` | Issuing FIR ICAO id and name |
| `icao_id` | `str?` | Issuing office, if distinct from the FIR |
| `hazard` | `str?` | `TURB`, `ICE`, `TS`, `MTW`, `VA`, … |
| `qualifier` | `str?` | Intensity/coverage: `SEV`, `EMBD`, `ISOL`, … |
| `base_ft` / `top_ft` | `int?` | Vertical band, **feet MSL** (None if unknown) |
| `valid_from` / `valid_to` | `datetime?` | Validity window (aware UTC) |
| `direction` / `speed_kt` | `str?` / `int?` | Movement (None if stationary/unknown) |
| `coords` | `List[(lon, lat)]` | Polygon outline |

Geometry helpers mirror `FIR`: `polygons` (multipolygon shape), `bbox`, `contains_point`, `overlaps_altitude(low, high)`, `is_valid_at(when)`. `to_dict`/`from_dict` round-trip like `WeatherReport`. The parser is defensive — every field tolerates a missing key, and the level/time helpers accept the encodings AWC has shipped (epoch / ISO time; feet / `FL340` / `SFC`) — so the Sept-2025 schema change (dropped `isigmetId`) degrades gracefully.

```python
from euro_aip.briefing.sources import AvWxSource
sigmets = AvWxSource().fetch_isigmet(hazard="turb")  # server-side hazard filter
# Also the ones issued but not yet valid, up to 4 h ahead:
sigmets = AvWxSource().fetch_isigmet(lookahead=timedelta(hours=4))
```

**Lookahead (pending SIGMETs).** isigmet lists only SIGMETs valid at the query time, so a SIGMET issued at 06:32 to start at 07:00 is invisible until 07:00. `lookahead=` adds queries at `date = now + k·step` (default step 30 min) and merges them into the now query. Choices, each load-bearing:

- **Combine, never replace**: the now query is the source of truth for what is valid now; a shifted query alone loses a SIGMET expiring before it.
- **Failures**: a failed now query returns `[]` as always and skips the lookahead. A failed lookahead query is logged and **ends** the lookahead (not retried): the now result and earlier steps are kept. Stopping at the first failure bounds the extra latency of a sick upstream to one timeout instead of eight.
- **Dedupe** on `(firId, seriesId, validTimeFrom)`, else `rawSigmet`; now entries first.
- **Gap**: a pending SIGMET valid for less than `step` can fall between two queries.
- **Cost**: one global request (~150 entries) per step, sequential. 4 h / 30 min = 9 requests per call.

`RouteSigmetService.fetch_route_sigmets(lookahead=...)` forwards it, only when set (sources without the parameter keep working).

### RouteSigmetService (`route_sigmet.py`)

Mirrors `RouteWeatherService`: resolve the route points to geometry (NavPoints as given, codes via `find_airport_by_code`, `alt_ident` fallback included), fetch SIGMETs, then keep only those intersecting the route corridor, altitude band and (optional) time window. Filter stages, cheapest first:

1. **Time + vertical** — drop SIGMETs whose validity misses the requested `(from_datetime, to_datetime)` window (`overlaps_time`) or whose layer misses `altitude_band_ft` (`overlaps_altitude`). Both window bounds are optional; naive datetimes are assumed UTC.
2. **FIR match** — `model.firs_along_route` gives the route's FIRs; a SIGMET's `fir_id` membership is recorded in `matched_firs` and is the *only* test when a SIGMET has no usable polygon. It does not gate SIGMETs that have geometry.
3. **Geometry refine** (authoritative when geometry exists) — densely sample the route (`sample_step_nm`, default 5), bbox-prefilter against the corridor-padded route box, then test each sample for polygon containment / corridor distance, recording perpendicular distance and the enroute extent affected.

```python
from datetime import datetime, timezone, timedelta
from euro_aip.briefing.weather.route_sigmet import RouteSigmetService

etd = datetime.now(timezone.utc)
result = RouteSigmetService().fetch_route_sigmets(
    route_navpoints, corridor_nm=100, model=model, altitude_band_ft=(0, 45000),  # or ["LFPG", "LGAV"]
    from_datetime=etd, to_datetime=etd + timedelta(hours=3),  # period of interest
)
for rs in result.sigmets:  # sorted by nearest enroute distance
    print(rs.sigmet.fir_id, rs.sigmet.hazard, rs.min_distance_nm,
          rs.enroute_distance_from_nm, rs.enroute_distance_to_nm)
```

The plain isigmet query carries only SIGMETs valid now; with `lookahead` it also carries upcoming ones (issued ahead of validity), so a time window matched to the planned ETA/ETA-band is the way to keep only the hazards relevant to the flight.

### AWC isigmet API behaviour (verified live, 2026-05-20)

- **`base`/`top` are feet MSL** (`base: 30000` ↔ raw `FL300`), matching `base_ft`/`top_ft`. `FL`-prefixed strings are still converted.
- **`region` is ignored** by the endpoint — every value returns the same global set (~125 SIGMETs). Filter geographically on the client; `RouteSigmetService` does this via route geometry.
- **`hazard` filters server-side** (`turb`/`ice`/`conv`/…).
- **`level` is a flight level (hundreds of feet)**: `level=100` = FL100 = 10,000 ft — not feet.
- **`validTimeFrom`/`validTimeTo` are epoch seconds**; `dir` uses `"-"` for stationary (normalised to `None`); `spd` is a numeric string or `"UNK"` (→ `None`).
- **Only SIGMETs valid at the query time** (2026-10-05): the live feed had 0 of 154 with a future start, though many reached AWC 10–149 min before validity. `date=<future>` returns the ones that will be valid then (`now+1h`: 40 not yet valid, all already received). Whether `date` is rounded or cached is unchecked.

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
| `visibility_min_meters` | `int?` | Minimum visibility (second group, `9999 1400` / `9999 1400SW`); never used for the category |
| `visibility_min_direction` | `str?` | Its direction (`SW`), when reported |
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
| Route services accept NavPoints | A code only resolves as an airport; passing codes for navaids/fixes silently straightened the corridor |
| Bbox prefilter in corridor search | Exact same result as all-segments measurement, ~35x faster on long routes — route weather is on the briefing hot path |

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
- **Minimum visibility (flyfun-weather #682)**: metar_taf_parser reads a
  second visibility group *without* a direction (`9999 1400`, common on French
  AUTO stations) as the visibility itself, so `9999 1400` graded LIFR.
  `WeatherParser._metar_visibility_groups` re-reads the METAR body (up to
  TEMPO/BECMG/NOSIG/PROB/RMK): first group prevailing → `visibility_meters`
  and the category; the group right after it → `visibility_min_*`. TAFs and
  trend groups carry one visibility each and are not affected.
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
