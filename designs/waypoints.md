# Waypoints & Route Resolution

> Named navigation waypoints and route string resolution across airports and waypoints

## Intent

Enable route strings with mixed airports and waypoints: `"EGTF VESAN POGOL LSGS"` instead of only `"EGTF LSGS"`. The system resolves each token to GPS coordinates so spatial queries (NOTAM filtering, along-route, distance calculations) work seamlessly.

**What should NOT change**: Airport-first resolution (ICAO codes always take precedence over waypoint names). The existing Route/RoutePoint/NavPoint models are reused, not replaced.

## Architecture

### Python (`euro_aip/`)

```
models/
├── waypoint.py              # Waypoint dataclass (name, coords, type, FIR)
├── waypoint_collection.py   # WaypointCollection (QueryableCollection)
├── route_resolver.py        # RouteResolver (airport-first resolution)
├── euro_aip_model.py        # Extended: _waypoints dict, add_waypoint(), etc.

sources/
├── eurocontrol_fra.py       # EurocontrolFRASource (downloads/parses Excel)
├── opennav.py               # OpenNavSource (scrapes per-country waypoint pages)

utils/
├── dms_parser.py            # FRA DMS, OpenNav DMS, ICAO route coordinate parsers

storage/
├── database_storage.py      # Extended: waypoints + waypoints_changes tables
├── field_definitions.py     # Extended: WaypointFields class
```

### Swift (`Sources/RZFlight/`)

```
├── Waypoint.swift           # Waypoint struct (Codable, KDTreePoint)
├── KnownWaypoints.swift     # Database-backed waypoint store + spatial queries
Briefing/
├── RoutePointResolver.swift # Unified airport+waypoint route resolution
```

## Usage Examples

### Python: Resolve a route string
```python
from euro_aip.models import EuroAipModel
from euro_aip.models.route_resolver import RouteResolver
from euro_aip.sources.eurocontrol_fra import EurocontrolFRASource

# Load model with airports + waypoints
model = storage.load_model()
EurocontrolFRASource(cache_dir="cache").update_model(model)

# Resolve route
resolver = RouteResolver(model)
route = resolver.resolve("EGTF VESAN POGOL LSGS")
# route.departure_coords, route.waypoint_coords, route.destination_coords all populated
# route.get_route_navpoints() returns full NavPoint list for spatial queries
```

### Python: Query waypoints
```python
model.waypoints.by_fir("LFFF").count()           # Waypoints in Paris FIR
model.waypoints.by_type("VOR").all()              # All VOR NAVAIDs
model.waypoints.navaids().nearest(navpoint, 10)   # 10 nearest NAVAIDs
"VESAN" in model.waypoints                        # Dict-style lookup
```

### Swift: Resolve a route
```swift
let resolver = RoutePointResolver(airports: knownAirports, waypoints: knownWaypoints)
let route = resolver.resolveRouteString("EGTF VESAN POGOL LSGS")
// route.allCoordinates — full path for map display
// Route+Geometry works unchanged for NOTAM classification
```

## Key Choices

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Naming | `Waypoint` (not NavPoint) | NavPoint is the calculation utility; Waypoint is the data model. A Waypoint *has* a NavPoint. |
| Same database | `waypoints` table in airports.db | Routes need both airports and waypoints from one source |
| Airport-first resolution | ICAO always wins over waypoint name | ICAO codes are authoritative; prevents accidental shadowing |
| Separate KnownWaypoints | Not merged into KnownAirports | Different data shapes, separate KDTrees, clean separation |
| WaypointCollection | Extends QueryableCollection | Follows the established fluent API pattern |
| Point type classification | From Excel "Point Type" column | 5LNC (empty column) vs VOR/DME/VORDME/NDB/VORTAC/NDBDME/LOCATOR |

## Data Sources

### Eurocontrol FRA Points List (primary)
~8,100 unique waypoints (5-letter codes + NAVAIDs) across European free route airspace. Updated every AIRAC cycle (28 days).

- Publication page: `https://www.eurocontrol.int/publication/free-route-airspace-fra-points-list-ecac-area`
- Format: Excel (.xlsx), "FRA Points" sheet
- Coordinates: DMS format (`N404519`, `E0183830`)
- Auto-scrapes the page for the latest download URL; also accepts local file path
- Rows marked "DEL" are skipped; duplicate names merge FIR codes

### OpenNav (supplementary)
Per-country waypoint lists from opennav.com covering all published fixes (not just FRA-significant). Broader coverage than FRA.

- URL pattern: `https://opennav.com/waypoint/{country_code}` (ISO alpha-2, except UK not GB)
- HTML table scraping with regex; coordinates in DMS format (`49° 54' 7.00" N`)
- Covers 32 European countries by default
- Point type inferred by name length (5-letter → 5LNC, shorter → unknown/NAVAID)
- Source field: `"opennav"` vs `"eurocontrol_fra"`

## Database Schema

### waypoints
```sql
CREATE TABLE waypoints (
    name TEXT NOT NULL PRIMARY KEY,
    latitude_deg REAL,
    longitude_deg REAL,
    point_type TEXT,        -- "5LNC", "VOR", "DME", "VORDME", "NDB", "VORTAC", etc.
    fir_codes TEXT,         -- Comma-separated FIR ICAOs
    level_availability TEXT,
    source TEXT,
    created_at TEXT,
    updated_at TEXT
);
```

### waypoints_changes
Field-level change tracking with AIRAC tagging, same pattern as `airports_changes`.

## Patterns

- **Waypoint.navpoint** property mirrors `Airport.navpoint` — returns `NavPoint` for distance calculations
- **RouteResolver** is stateless — create with model, call `resolve()` or `resolve("route string")`
- **WaypointCollection** follows `AirportCollection` patterns: `by_type()`, `by_fir()`, `.filter()`, `.all()`, `.first()`, `.count()`
- **Schema migration**: `DatabaseStorage._migrate_schema_if_needed()` auto-creates waypoints tables on old databases

## Gotchas

- **FRA is European-only**: The Eurocontrol dataset covers ECAC area. Other regions would need different sources.
- **~8,100 not 26,000**: The Excel has ~26,667 rows but many are duplicates across FIRs. Deduplication by name yields ~8,100 unique waypoints.
- **Not all waypoints exist**: Common waypoints like BILGO may not be in the FRA dataset if they're not FRA-significant. Use OpenNav as supplementary source for broader coverage.
- **KnownWaypoints handles missing table**: Older databases without `waypoints` table result in an empty store (no crash).

## References

- Route models: [briefing_models.md](./briefing_models.md)
- Database schema: [database_quick_reference.md](./database_quick_reference.md)
- Query patterns: [query_api_architecture.md](./query_api_architecture.md)
- Swift architecture: [swift_architecture.md](./swift_architecture.md)
- Key code: `euro_aip/models/waypoint.py`, `euro_aip/sources/eurocontrol_fra.py`, `Sources/RZFlight/KnownWaypoints.swift`
