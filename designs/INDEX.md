# rzflight

> Flight planning libraries and European AIP data processing in Python and Swift

Install: `pip install euro-aip` (Python) or Swift Package Manager (Swift)

## Cross-Platform Design

The briefing/NOTAM parsing system has **parallel implementations in Python and Swift** that must produce identical output. Both share configuration files:

- `q_codes.json` - Q-code subject/condition meanings
- `document_references.json` - AIP supplement and AIC URL patterns

When modifying parsing logic, update BOTH implementations and run tests on both platforms.

## Releasing & Versioning
Two packages released independently from this repo with separate tag conventions.
→ Full doc: releasing.md

## Consumers
Who depends on euro_aip / RZFlight and what each uses: flyfun-apps builds `airports.db` with the Python sources + `DatabaseStorage`; flyfun-weather uses the briefing/weather parsers at runtime; flyfun-forms and flightlogstats use borders/customs and RZFlight Swift. The `airports.db` schema is a Python-writes / Swift-reads contract.
→ Full doc: consumers.md

## Modules

### RZFlight Swift Package
Aviation calculations, airport data management, and flight planning for iOS/macOS. Wind calculations, runway selection, METAR integration, spatial airport/waypoint queries, route resolution, and native PDF briefing parsing.
Key exports: `Airport`, `Runway`, `Procedure`, `RunwayWindModel`, `KnownAirports`, `Waypoint`, `KnownWaypoints`, `RoutePointResolver`, `ICAOFlightPlanParser`, `Briefing`, `Notam`, `ForeFlightParser`, `Route`, `FlightExchange`

**Documentation:**
- `swift_package.md` - Package overview, quick start
- `swift_briefing.md` - Briefing/NOTAM parsing and models
- `native_pdf_parsing.md` - ForeFlight PDF parsing implementation

### Python Euro AIP Query API
Fluent, chainable collections for querying airports, procedures, and AIP data. Supports dict-style access, set operations (`|`, `&`, `-`), and filtering.
Key exports: `model.airports`, `model.procedures`, `by_country`, `with_runways`

**Documentation (load in order of need):**
- `query_api_architecture.md` - Design patterns & conventions (read FIRST when implementing new features)
- `query_api_quickref.md` - Compact method reference (quick syntax lookup)
- `query_api_detailed.md` - Full API documentation (complete details)

### Python Euro AIP Waypoints & Route Resolution
Named navigation waypoints (5-letter codes, VOR/DME/NDB) from Eurocontrol FRA, Eurocontrol SDO (EAD designated points), OpenNav, OurAirports, and FAA NASR, with route string resolution that mixes airports and waypoints. Includes country-scoped fetch, bounding-box scoping for SDO, and cross-source dedup with source priority.
Key exports: `Waypoint`, `WaypointCollection`, `RouteResolver`, `EurocontrolFRASource`, `EurocontrolSDOSource`, `OpenNavSource`, `OurAirportsNavaidSource`, `FAANasrFixSource`, `EuroAipModel.dedup_waypoints()`
→ Full doc: waypoints.md

### Python Euro AIP Database
SQLite database structure, quick queries, and DatabaseStorage for model persistence. Includes airports, runways, procedures, AIP entries, border crossings, and waypoints tables.
Key exports: `DatabaseStorage`, `load_model()`, `save_model()`
→ Full doc: database_quick_reference.md

### Python Euro AIP Builder API
Transactions, bulk operations, and fluent builders for creating and modifying aviation data models. Atomic updates with rollback support.
Key exports: `model.transaction()`, `bulk_add_airports`, `airport_builder`
→ Full doc: builder_api_guide.md

### Python Euro AIP Borders & Customs
Offline Schengen / EU-customs-union membership and per-flight crossing requirements, plus the AIP customs-field interpreter (field 302): notice periods and how to notify (contact e-mails, web forms, myhandling, mandated e-mail subject).
Key exports: `crossing_requirements`, `is_schengen`, `is_eu_customs_union`, `CustomInterpreter`, `InterpreterFactory`
→ Full doc: borders.md

### Python Euro AIP Web Sources
Documentation for European AIP web sources and data retrieval.
→ Full doc: AIP_WEB_SOURCES.md

### Python Euro AIP Briefing
Flight briefing data extraction, NOTAM filtering, and weather analysis. Parse ForeFlight PDFs, fetch live or historical METARs/TAFs, extract NOTAMs, and filter with fluent API.
Key exports: `Briefing`, `NotamCollection`, `WeatherCollection`, `ForeFlightSource`, `AutorouterNotamSource`, `AutorouterGrametSource`, `AvWxSource`, `OgimetSource`, `ICAOFlightPlan`, `parse_icao_fpl`, `CategorizationPipeline`, `WeatherReport`, `FlightCategory`, `Route`, `RoutePoint`, `FlightExchange`

**Documentation (load in order of need):**
- `briefing.md` - Overview, architecture, usage examples (read FIRST)
- `briefing_models.md` - Data model field reference (Notam, Route, Briefing, WeatherReport)
- `briefing_filtering.md` - NotamCollection/WeatherCollection API and categorization pipeline
- `briefing_weather.md` - Weather parsing, flight categories, wind components, TAF analysis, SIGMETs, route weather/SIGMET services (codes or NavPoints)
- `briefing_parsing.md` - Source/parser separation, adding new sources
- `swift_briefing.md` - Swift models for iOS/macOS (loads Python JSON)
