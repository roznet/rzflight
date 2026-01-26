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
| `category` | `NotamCategory?` | Parser | Enum from Q-code (RUNWAY, LIGHTING, etc.) |
| `primary_category` | `str?` | Pipeline | Best category string from categorization |
| `custom_categories` | `Set[str]` | Pipeline | All applicable categories |
| `custom_tags` | `Set[str]` | Pipeline | Granular tags (crane, closed, ils) |

### NotamCategory Enum

```python
class NotamCategory(Enum):
    MOVEMENT_AREA = "MX"  # Taxiway, apron
    LIGHTING = "LX"
    NAVIGATION = "NA"     # VOR, ILS, DME
    COMMUNICATION = "CO"
    AIRSPACE = "AR"       # Restricted, TFRs
    RUNWAY = "RW"
    OBSTACLE = "OB"       # Cranes, towers
    PROCEDURE = "PI"      # SIDs, STARs, approaches
    SERVICES = "SE"       # Fuel, ATC
    WARNING = "WA"
    OTHER = "XX"
```

### Q-Code Info

Parsed from `q_codes.json`, provides human-readable meanings:

| Field | Type | Description |
|-------|------|-------------|
| `q_code` | `str` | Raw Q-code (e.g., "QMRLC") |
| `subject_code` | `str` | 2-letter subject (e.g., "MR") |
| `subject_meaning` | `str` | Subject meaning (e.g., "Runway") |
| `condition_code` | `str` | 2-letter condition (e.g., "LC") |
| `condition_meaning` | `str` | Condition meaning (e.g., "Closed") |
| `display_text` | `str` | Combined text (e.g., "Runway: Closed") |
| `short_text` | `str` | Short form (e.g., "RWY CLSD") |

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
```

## RoutePoint

Individual waypoint with coordinates.

| Field | Type | Description |
|-------|------|-------------|
| `name` | `str` | Waypoint name or ICAO |
| `latitude` | `float` | Decimal degrees |
| `longitude` | `float` | Decimal degrees |
| `point_type` | `str` | "departure", "destination", "alternate", "waypoint" |

Has `.navpoint` property for `NavPoint` integration (distance calculations).

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
| `valid_from` | `datetime?` | Briefing validity start |
| `valid_to` | `datetime?` | Briefing validity end |
| `raw_data` | `Dict?` | Source-specific metadata |

### Key Properties/Methods

```python
briefing.notams_query           # Returns NotamCollection for filtering
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
- Code: `euro_aip/briefing/models/`
