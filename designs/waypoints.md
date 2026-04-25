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
├── field15.py               # ICAO Field-15 route tokenizer (pure, DB-free)
├── route_resolver.py        # RouteResolver (airport-first + detour gate)
├── euro_aip_model.py        # Extended: _waypoints dict, add_waypoint(), etc.

sources/
├── eurocontrol_fra.py       # EurocontrolFRASource (downloads/parses Excel)
├── opennav.py               # OpenNavSource (scrapes per-country waypoint pages)
├── ourairports_navaids.py   # OurAirportsNavaidSource (worldwide NAVAIDs CSV; country-filterable)
├── faa_nasr_fix.py          # FAANasrFixSource (US 70k named fixes from NASR subscription)
├── eurocontrol_sdo.py       # EurocontrolSDOSource (EAD/SDO HTML exports; manual download, ~98k EU+NA fixes)

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

# Resolve a full Field-15 string — speed/level, airways, IFR/VFR, DCT all drop out
resolver = RouteResolver(model)
route = resolver.resolve("N0175F160 EGTF DCT BILGO/N0180F100 UL612 XIDIL VFR LSGS")
# route.departure_coords, route.waypoint_coords, route.destination_coords all populated
# route.rejected_waypoints — tokens whose coords fell too far off the route
# route.get_route_navpoints() returns full NavPoint list for spatial queries
```

### Python: Tokenize without resolving
```python
from euro_aip.models import parse_field15, waypoints_of, TokenKind

tokens = parse_field15("EGTF DCT BILGO/N0180F100 UL612 XIDIL LSGS")
waypoints_of(tokens)        # ['EGTF', 'BILGO', 'XIDIL', 'LSGS']
[(t.value, t.kind) for t in tokens if t.qualifier]
# [('BILGO', TokenKind.WAYPOINT)]  — qualifier 'N0180F100' captured on the token
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
| Tokenizer vs resolver split | `parse_field15` is pure; resolver does DB lookups | Pure tokenizer is testable and reusable (`waypoints_of`, `annotations_of`). Resolver demotes AIRWAY/UNKNOWN → WAYPOINT *after* classification when a DB hit exists (covers real-world collisions like Y8 airway vs NDB). |
| Multi-candidate disambiguation | Minimise detour on `reference→forward` leg (forward = destination) | Raw distance to `reference` (legacy) picks the wrong candidate when dep and dest are far apart — e.g. ABB would pick the US VORTAC over the French VORDME on an EGKB→LFMD route. Detour-on-leg is direction-aware. |
| Detour filter | Reject middle waypoints whose detour > `min(cap, max(floor, coef × leg_nm))` | Defaults: `floor=30 nm`, `coef=0.5`, `cap=300 nm`. Prevents 5-letter fixes with only-far-off candidates being silently plotted hundreds of nm off route. Rejected entries surface on `Route.rejected_waypoints`, not silently dropped. |

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

### OurAirports NAVAIDs (supplementary)
Worldwide NAVAIDs (~9,900 across 231 countries) from the OurAirports `navaids.csv`. Used to fill NAVAID gaps not covered by FRA/OpenNav.

- CSV URL: `https://raw.githubusercontent.com/davidmegginson/ourairports-data/main/navaids.csv`
- Decimal coordinates — no DMS parsing
- Accepts `countries=` ISO alpha-2 list to scope fetch at source level (authoritative per-row `iso_country`, independent of the continent miscoding in the airports CSV)
- Source field: `"ourairports"`, source_id: `"ourairports:{country}"`

### Eurocontrol SDO Designated Points (manual export, opt-in)
~98,000 ICAO 5-letter waypoints across Europe + North America, sourced from the Eurocontrol European AIS Database (EAD) SDO Reporting tool. Most authoritative European source — fed upstream by national ANSPs (DFS, AVINOR, DHMI, ENAIRE, NAV CANADA, FAA via "FAA LOADER", etc.).

- Download (behind EAD login, manual): SDO Reporting → Designated Points → Hemisphere North/East and North/West
- Format: HTML table; coords mix four formats in one file (DDMMSS, DDMMSS.s, DDMM[.m], decimal degrees)
- Filtered to `Type=ICAO` rows only — `OTHER` (runway-relative procedure points), `ADHP` (aerodrome holding), `COORD` (10° grid points) are skipped by default but `types=...` accepts them if needed
- Bounding-box scoped to Europe (lat 30-75, lon -30 to 50) + North America (lat 15-75, lon -180 to -50); ~18k Asia/Africa/Pacific rows skipped
- Source: `"eurocontrol_sdo"`, source_id: `"eurocontrol_sdo:{originator_slug}"` (e.g. `eurocontrol_sdo:NAV_CANADA`)
- Local-file-only — no auto-fetch (would need scraping a logged-in session). Drop new exports into `data/eurocontrol_sdo/*.html` (gitignored) and run `build_nav_db.py --include-sdo`. The committed `nav.db` is the authoritative artefact for downstream consumers.

### FAA NASR Fixes (US-only, opt-in)
~70,200 US named fixes (intersections, RNAV waypoints, reporting points) from the FAA 28-day NASR subscription. The 9,900-row OurAirports worldwide set covers NAVAIDs (VOR/NDB/DME) but NOT 5-letter intersections — FAA NASR fills that gap for the US.

- Cycle index: `https://www.faa.gov/air_traffic/flight_info/aeronav/aero_data/NASR_Subscription/`
- Direct download: `https://nfdc.faa.gov/webContent/28DaySub/extra/{DD}_{MonAbbr}_{YYYY}_FIX_CSV.zip` (no auth)
- Auto-discovers cycle start date via `getNasr56EffectiveDate` JSON endpoint
- Decimal coordinates; `ARTCC_ID_HIGH`/`_LOW` → `fir_codes` (comma-joined when they differ)
- All emitted as `point_type="5LNC"`; source: `"faa_nasr"`, source_id: `"faa_nasr:{STATE}"`
- Opt-in via `build_nav_db.py --include-faa` — doubles DB size (~12 MB → ~22 MB) so default build is European-scoped

## Dedup and Country Scoping

### Country-scoped OurAirports fetch
`build_nav_db.py` derives the country list from the filtered `airports_df['iso_country'].unique()` and passes it to `OurAirportsNavaidSource(countries=...)`. With `--continents EU NA`, this scopes the worldwide CSV to ~90 countries, cutting ~4,000 out-of-scope NAVAIDs (AU, CN, BR, JP, etc.) before they ever enter the model.

### `EuroAipModel.dedup_waypoints(tolerance_nm=0.5, source_priority=...)`
Post-source cleanup pass that collapses near-duplicate candidates while preserving genuine geographic collisions.

- Groups candidates by `name`, clusters by great-circle distance within `tolerance_nm`
- Per cluster, keeps the candidate from the highest-priority source
- Clusters > tolerance apart stay as distinct candidates (e.g. NDB `MA` exists in Germany, Spain, Canada, USA, Russia simultaneously — all kept)
- Default priority: `eurocontrol_fra > eurocontrol_sdo > opennav > ourairports > faa_nasr` (richer metadata sources win; SDO is authoritative upstream but lacks the FIR/level metadata of FRA)
- Type-mixed same-coord candidates (e.g. OurAirports says NDB, FRA says VORDME) resolve to FRA's VORDME — more authoritative classification supersedes outdated entries

Invoked after all sources in `build_nav_db.py`. Typical effect on a European build: 34k → 26k rows (−25%), with zero < 0.5 nm near-duplicates remaining and ~870 genuine global collisions preserved.

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
- **SID/STAR names tokenize as UNKNOWN**: Identifiers like `PERUS1N`, `SOKDU1V`, `KATHY1V` don't match the strict 2–5 letter waypoint regex, so they stay UNKNOWN and are dropped from the resolved waypoint list. This is intentional — SIDs/STARs are procedures, not points, and the DB doesn't carry their endpoints under that name.
- **AIRWAY vs WAYPOINT demotion is DB-grounded**: `Y8` classifies as AIRWAY by grammar but also exists as an NDB in some nav DBs. The resolver promotes AIRWAY/UNKNOWN → WAYPOINT only when `resolve_point` finds a hit — and the detour gate then filters the far-off candidate. Both passes are needed; removing either one regresses real routes.
- **Inline DMS coordinates classify as UNKNOWN**: Tokens like `4830N/00210E` split on `/`, leaving `4830N` as value and `00210E` as qualifier. The resolver skips them (no DB name match). Field-15 consumers that care about inline coords must read them off the raw token.
- **Rejected ≠ unresolved**: `Route.rejected_waypoints` = DB hit but coords too far off the route (detour gate). Unresolved waypoints are just dropped with a warning; only rejections are structurally preserved for caller inspection.
- **FAA NASR is fixes only, not NAVAIDs**: The `FIX.zip` dataset covers named waypoints (intersections, RNAV points). US NAVAIDs (VOR/NDB/DME) are in a separate `NAV.zip` — the OurAirports NAVAIDs source already covers them, so no need to fetch `NAV.zip` today.
- **Country filter vs continent filter**: OurAirports NAVAIDs are scoped by `iso_country` (authoritative per-row), not by `continent` (which has known miscoding — e.g. `LE*` Spanish airports tagged `AF`). The build derives the country list from the filtered airports and passes it to the source.
- **Dedup preserves same-name different-location candidates**: 2-letter NDB idents (`MA`, `PA`) are reused globally. Dedup clusters by coord distance, so each regional instance survives as a separate candidate. The detour gate at resolve time picks the right one per route.

## References

- Route models: [briefing_models.md](./briefing_models.md)
- Database schema: [database_quick_reference.md](./database_quick_reference.md)
- Query patterns: [query_api_architecture.md](./query_api_architecture.md)
- Swift architecture: [swift_architecture.md](./swift_architecture.md)
- Key code: `euro_aip/models/waypoint.py`, `euro_aip/models/field15.py`, `euro_aip/models/route_resolver.py`, `euro_aip/models/euro_aip_model.py` (`dedup_waypoints`), `euro_aip/sources/eurocontrol_fra.py`, `euro_aip/sources/eurocontrol_sdo.py`, `euro_aip/sources/ourairports_navaids.py`, `euro_aip/sources/faa_nasr_fix.py`, `Sources/RZFlight/KnownWaypoints.swift`
