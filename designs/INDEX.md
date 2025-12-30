# rzflight

> Flight planning libraries and European AIP data processing in python and swift

Install: `pip install euro-aip` (Python) or Swift Package Manager (Swift)

## Modules

### RZFlight Swift Package
Aviation calculations, airport data management, and flight planning for iOS/macOS. Wind calculations, runway selection, METAR integration, and spatial airport queries.
Key exports: `Airport`, `Runway`, `Procedure`, `RunwayWindModel`, `KnownAirports`, `AVWX`
→ Full doc: swift_package.md

### Python Euro AIP Query API
Fluent, chainable collections for querying airports, procedures, and AIP data. Supports dict-style access, set operations (`|`, `&`, `-`), and filtering.
Key exports: `model.airports`, `model.procedures`, `by_country`, `with_runways`
→ Full doc: models_query_api_documentation.md

### Python Euro AIP Builder API
Transactions, bulk operations, and fluent builders for creating and modifying aviation data models. Atomic updates with rollback support.
Key exports: `model.transaction()`, `bulk_add_airports`, `airport_builder`
→ Full doc: builder_api_guide.md

### Python Euro AIP Quick Start
Getting started guide with installation, basic querying, filtering, and common patterns.
→ Full doc: QUICK_START.md

### Python Euro AIP Web Sources
Documentation for European AIP web sources and data retrieval.
→ Full doc: AIP_WEB_SOURCES.md
