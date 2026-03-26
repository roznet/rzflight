# Briefing: Data Models

> Field reference for Notam, Route, Briefing dataclasses

## Intent

Document the data structures so you can:
- Access the right fields when filtering/querying
- Understand which fields are populated by parsers vs categorization
- Serialize/deserialize for cross-platform use

## Notam

Core NOTAM data structure. All fields serialize to JSON via `to_dict()`/`from_dict()`.

### Essential Fields

| Field | Type | Description |
|-------|------|-------------|
| `id` | `str` | NOTAM ID (e.g., "A1234/24") |
| `location` | `str` | Primary ICAO from A) line |
| `raw_text` | `str` | Full original NOTAM text |
| `message` | `str` | E) line - the main message content |

### Q-Line Decoded Fields

Populated by `NotamParser` from the Q) line:

| Field | Type | Description |
|-------|------|-------------|
| `q_code` | `str?` | 5-letter Q-code (e.g., "QMRLC") |
| `fir` | `str?` | FIR code |
| `traffic_type` | `str?` | I (IFR), V (VFR), IV (both) |
| `purpose` | `str?` | N (immediate), B (briefing), O (ops), M (misc), K (checklist) |
| `scope` | `str?` | A (aerodrome), E (enroute), W (warning) |
| `lower_limit` | `int?` | Lower altitude in feet |
| `upper_limit` | `int?` | Upper altitude in feet |
| `coordinates` | `(lat, lon)?` | Tuple of floats, decimal degrees |
| `radius_nm` | `float?` | Affected radius in nautical miles |

### Schedule Fields

| Field | Type | Description |
|-------|------|-------------|
| `effective_from` | `datetime?` | Start of validity (UTC) |
| `effective_to` | `datetime?` | End of validity (UTC) |
| `is_permanent` | `bool` | True = no end date |
| `schedule_text` | `str?` | Variable schedule (e.g., "SR-SS") |

### Category Fields

Set by parser (from Q-code) and enriched by `CategorizationPipeline`:

| Field | Type | Set By | Description |
|-------|------|--------|-------------|
| `category` | `NotamCategory?` | Parser | Enum from Q-code (AGA_MOVEMENT, AGA_LIGHTING, etc.) |
| `primary_category` | `str?` | Pipeline | Best category string from categorization |
| `custom_categories` | `Set[str]` | Pipeline | All applicable categories |
| `custom_tags` | `Set[str]` | Pipeline | Granular tags (crane, closed, ils) |

### NotamCategory Enum

Based on Q-code subject first letter (ICAO standard):

```python
class NotamCategory(Enum):
    ATM_AIRSPACE = "A"          # FIR, TMA, CTR, ATS routes
    CNS_COMMUNICATIONS = "C"    # Radar, ADS-B
    AGA_FACILITIES = "F"        # Aerodrome, fuel
    CNS_GNSS = "G"              # GNSS Services
    CNS_ILS = "I"               # ILS, localizer, glide path
    AGA_LIGHTING = "L"          # ALS, PAPI, runway lights
    AGA_MOVEMENT = "M"          # Runway, taxiway, apron
    NAVIGATION = "N"            # VOR, DME, NDB
    OTHER_INFO = "O"            # Obstacles, AIS
    ATM_PROCEDURES = "P"        # SID, STAR, approaches
    AIRSPACE_RESTRICTIONS = "R" # D/P/R areas
    ATM_SERVICES = "S"          # ATIS, ACC, TWR
```

### Q-Code Info

Parsed from `q_codes.json`, provides human-readable meanings:

| Field | Type | Description |
|-------|------|-------------|
| `q_code` | `str` | Raw Q-code (e.g., "QMRLC") |
| `subject_code` | `str` | 2-letter subject (e.g., "MR") |
| `subject_meaning` | `str` | Subject meaning (e.g., "Runway") |
| `subject_phrase` | `str` | Short form (e.g., "rwy") |
| `subject_category` | `str` | ICAO category (e.g., "AGA Movement Area") |
| `condition_code` | `str` | 2-letter condition (e.g., "LC") |
| `condition_meaning` | `str` | Condition meaning (e.g., "Closed") |
| `condition_phrase` | `str` | Short form (e.g., "clsd") |
| `condition_category` | `str` | Condition group (e.g., "Limitations") |
| `display_text` | `str` | Combined text (e.g., "Runway: Closed") |
| `short_text` | `str` | Short form (e.g., "RWY CLSD") |
| `is_checklist` | `bool` | True if QKKKK checklist code |
| `is_plain_language` | `bool` | True if XX (refer to Item E) |

### Document References

References to external documents (AIP supplements) extracted from NOTAM text:

| Field | Type | Description |
|-------|------|-------------|
| `document_references` | `List[DocumentReference]` | Extracted document links |

Each `DocumentReference` contains:

| Field | Type | Description |
|-------|------|-------------|
| `type` | `str` | Document type (e.g., "aip_supplement") |
| `identifier` | `str` | Reference ID (e.g., "SUP 059/2025") |
| `provider` | `str` | Provider ID (e.g., "uk_nats") |
| `provider_name` | `str` | Human name (e.g., "UK NATS AIP Supplements") |
| `search_url` | `str?` | Generic search/browse page |
| `document_urls` | `List[str]` | Direct PDF links |

### Parsing Metadata

| Field | Type | Description |
|-------|------|-------------|
| `source` | `str?` | Where it came from ("foreflight", "avwx") |
| `parsed_at` | `datetime` | When parsing occurred |
| `parse_confidence` | `float` | 0-1, how much was successfully parsed |

## Route

Flight route with coordinates for spatial NOTAM filtering.

### Core Fields

| Field | Type | Description |
|-------|------|-------------|
| `departure` | `str` | Departure ICAO |
| `destination` | `str` | Destination ICAO |
| `alternates` | `List[str]` | Alternate airport ICAOs |
| `waypoints` | `List[str]` | Waypoint names along route |

### Coordinate Fields

For spatial queries (`along_route()`, `near_airports()`):

| Field | Type | Description |
|-------|------|-------------|
| `departure_coords` | `(lat, lon)?` | Departure airport coordinates |
| `destination_coords` | `(lat, lon)?` | Destination airport coordinates |
| `alternate_coords` | `Dict[icao, (lat,lon)]` | Alternate coordinates |
| `waypoint_coords` | `List[RoutePoint]` | Full waypoint data with coords |

### Flight Details

| Field | Type | Description |
|-------|------|-------------|
| `aircraft_type` | `str?` | Aircraft type code |
| `departure_time` | `datetime?` | Planned departure (UTC) |
| `arrival_time` | `datetime?` | Estimated arrival (UTC) |
| `flight_level` | `int?` | Cruise FL (e.g., 350) |
| `cruise_altitude_ft` | `int?` | Cruise altitude in feet |

### Key Methods

```python
route.get_all_airports()        # [departure, destination, alternates] unique
route.get_airport_coordinates() # {icao: (lat, lon)} for all known coords
route.get_flight_window(60)     # (dep_time, arr_time + 60min buffer)
route.get_route_navpoints()     # List[NavPoint] for distance calcs

# Create from route string with waypoint resolution
Route.from_route_string("EGTF VESAN POGOL LSGS", resolver)
```

### Route Resolution

Use `RouteResolver` to resolve mixed airport/waypoint route strings:

```python
from euro_aip.models.route_resolver import RouteResolver

resolver = RouteResolver(model)  # model has airports + waypoints
route = resolver.resolve("EGTF VESAN POGOL LSGS")
# First/last tokens = departure/destination, middle = waypoints
# Airport-first: ICAO codes take precedence over waypoint names
# DCT/-> tokens are filtered out
```

See [waypoints.md](./waypoints.md) for full waypoint architecture.

## RoutePoint

Individual waypoint with coordinates.

| Field | Type | Description |
|-------|------|-------------|
| `name` | `str` | Waypoint name or ICAO |
| `latitude` | `float` | Decimal degrees |
| `longitude` | `float` | Decimal degrees |
| `point_type` | `str` | "departure", "destination", "alternate", "waypoint" |

Has `.navpoint` property for `NavPoint` integration (distance calculations).

## ICAOFlightPlan

Parsed ICAO flight plan with all extractable fields. Python: `parse_icao_fpl()`, Swift: `ICAOFlightPlanParser.parse()`.

### Parsed Fields

| Field | Type | Description |
|-------|------|-------------|
| `aircraft_registration` | `str?` | Field 7: e.g., "N122DR" |
| `aircraft_type` | `str?` | Field 9: e.g., "S22T" |
| `flight_rules` | `str?` | V=VFR, I=IFR, Y/Z=mixed |
| `flight_type` | `str?` | G=general, S=scheduled, N/M/X |
| `speed` | `str?` | Raw: "N0166" or "K0280" |
| `speed_knots` | `int?` | Always in knots (K converted via ÷1.852) |
| `level` | `str?` | Raw: "VFR", "F350", "A055" |
| `altitude_feet` | `int?` | F350→35000, A055→5500, VFR→None |
| `equipment` | `str?` | Field 10a COM/NAV codes: "SBDGORVY" |
| `surveillance` | `str?` | Field 10b: "LB2" |
| `date_of_flight` | `date?` | From DOF/YYMMDD in field 18 |
| `departure_time_utc` | `time?` | From field 13 HHMM |
| `eet_minutes` | `int?` | From field 16, total minutes |
| `raw_route` | `str?` | Unparsed field 15 route string |
| `other_info` | `Dict[str,str]` | Field 18 key/value pairs (DOF, PBN, RMK, EET, etc.) |
| `route` | `Route` | Fully populated with departure, destination, waypoints, times |

### Derived Properties

| Property | Type | Logic |
|----------|------|-------|
| `is_ifr` | `bool` | flight_rules in {I, Y, Z} |
| `is_vfr` | `bool` | flight_rules == V |
| `has_gnss` | `bool` | G in equipment |
| `has_rnav` | `bool` | R in equipment |
| `has_adsb` | `bool` | B/1/2 in surveillance |
| `has_rvsm` | `bool` | W in equipment |
| `pbn_codes` | `str?` | other_info["PBN"] |
| `remarks` | `str?` | other_info["RMK"] |

### Route Token Classification

Field 15 route tokens are classified:
- **GPS coords** (`4830N00210E`) → RoutePoint with parsed lat/lon, point_type="gps"
- **Airways** (`UL9`, `L28`) → skipped (no airway DB)
- **DCT/VFR/IFR** → filtered out
- **Everything else** → waypoint name, resolved if resolver provided

### Key Code

- Python: `euro_aip/briefing/models/icao_fpl.py`
- Swift: `Sources/RZFlight/Briefing/ICAOFlightPlanParser.swift`

## Briefing

Container for complete flight briefing.

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `id` | `str` | UUID, auto-generated |
| `created_at` | `datetime` | Creation time |
| `source` | `str` | "foreflight", "avwx", etc. |
| `route` | `Route?` | Flight route |
| `notams` | `List[Notam]` | All NOTAMs in briefing |
| `weather_reports` | `List[WeatherReport]` | Parsed METARs/TAFs |
| `valid_from` | `datetime?` | Briefing validity start |
| `valid_to` | `datetime?` | Briefing validity end |
| `raw_data` | `Dict?` | Source-specific metadata |

### Key Properties/Methods

```python
briefing.notams_query           # Returns NotamCollection for filtering
briefing.weather_query          # Returns WeatherCollection for filtering
briefing.set_model(euro_model)  # Enable coord lookup from euro_aip
briefing.to_dict() / from_dict()
briefing.to_json() / from_json()
briefing.save(path) / load(path)
```

## Usage Pattern

```python
from euro_aip.briefing import ForeFlightSource, CategorizationPipeline

# Parse
briefing = ForeFlightSource().parse("briefing.pdf")

# Categorize (populates custom_categories, custom_tags, primary_category)
CategorizationPipeline().categorize_all(briefing.notams)

# Access fields
for notam in briefing.notams:
    print(f"{notam.id} at {notam.location}")
    print(f"  Q-code: {notam.q_code}, Category: {notam.category}")
    print(f"  Tags: {notam.custom_tags}")
    if notam.coordinates:
        print(f"  Coords: {notam.coordinates}")
    if notam.effective_from:
        print(f"  Valid: {notam.effective_from} - {notam.effective_to}")

# Use route for time windows
if briefing.route and briefing.route.departure_time:
    start, end = briefing.route.get_flight_window(buffer_minutes=60)
    relevant = briefing.notams_query.active_during(start, end)
```

## Gotchas

- **coordinates can be None**: Many NOTAMs lack coords, spatial filters skip them
- **category vs custom_categories**: `category` is enum from parser, `custom_categories` is Set[str] from pipeline
- **Times are UTC**: All datetime fields should be UTC
- **parse_confidence < 1.0**: Means partial parse, some fields may be missing
- **is_permanent + no effective_to**: Permanent NOTAMs have no end date

## References

- Main briefing doc: [briefing.md](./briefing.md)
- Filtering: [briefing_filtering.md](./briefing_filtering.md)
- Weather models & analysis: [briefing_weather.md](./briefing_weather.md)
- Code: `euro_aip/briefing/models/`, `euro_aip/briefing/weather/models.py`
