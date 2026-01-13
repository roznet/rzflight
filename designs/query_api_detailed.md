# Euro AIP Query API - Detailed Reference

**Purpose:** Complete API documentation with full attribute tables, method signatures, and comprehensive examples.

**See also:** `query_api_quickref.md` for compact reference, `query_api_architecture.md` for design patterns.

---

## Table of Contents

1. [Core Collections](#core-collections)
2. [Airport Querying](#airport-querying)
3. [Airport Attributes Reference](#airport-attributes-reference)
4. [Procedure Querying](#procedure-querying)
5. [Procedure Attributes Reference](#procedure-attributes-reference)
6. [AIP Data Querying](#aip-data-querying)
7. [AIPEntry Attributes Reference](#aipentry-attributes-reference)
8. [Runway Attributes Reference](#runway-attributes-reference)
9. [NavPoint & Distance Calculations](#navpoint--distance-calculations)
10. [Border Crossings](#border-crossings)
11. [Statistics & Metadata](#statistics--metadata)

---

## Core Collections

### Model Entry Points

```python
from euro_aip.storage.database_storage import DatabaseStorage

# Load model from database (preferred method)
storage = DatabaseStorage("data/airports.db")
model = storage.load_model()

# Two main collection entry points
airports = model.airports      # → AirportCollection
procedures = model.procedures  # → ProcedureCollection
```

### Dict-Style Access

`AirportCollection` supports dict-style access for convenient ICAO lookups:

```python
# Direct lookup (raises KeyError if not found)
heathrow = model.airports['EGLL']

# Check existence
if 'EGLL' in model.airports:
    print("Heathrow found")

# Safe lookup with default
airport = model.airports.get('EGLL', default=None)

# Works on filtered collections too
french = model.airports.by_country("FR")
cdg = french['LFPG']
```

### Set Operations

Collections support Python's set operators:

#### Union (`|`) - OR Logic
```python
western_europe = (
    model.airports.by_country("FR") |
    model.airports.by_country("DE") |
    model.airports.by_country("BE")
)
```

#### Intersection (`&`) - AND Logic
```python
premium = (
    model.airports.with_hard_runway() &
    model.airports.with_fuel(avgas=True, jet_a=True)
)
```

#### Difference (`-`) - Exclusion
```python
basic = model.airports.with_runways() - model.airports.with_procedures()
```

#### Complex Combinations
```python
result = (
    (model.airports.by_country("FR") | model.airports.by_country("DE")) &
    model.airports.with_hard_runway()
) - model.airports.with_procedures()
```

### Iteration & Indexing

```python
# Direct iteration (no .all() needed)
for airport in model.airports.by_country("FR"):
    print(f"{airport.ident}: {airport.name}")

# List comprehension
names = [a.name for a in model.airports.with_runways()]

# Indexing and slicing
first = model.airports[0]
last = model.airports[-1]
subset = model.airports[10:20]  # Returns new collection

# Reverse iteration
for airport in reversed(model.airports.order_by('name')):
    print(airport.name)  # Z to A
```

### Debug Output

```python
>>> model.airports.by_country("FR")
AirportCollection(['LFPG', 'LFPO', 'LFLL', ...], count=234)

>>> model.airports.by_country("FR").take(2)
AirportCollection(['LFPG', 'LFPO'], count=2)
```

---

## Airport Querying

### Base Collection Methods

All collections inherit these from `QueryableCollection`:

#### `.filter(predicate: Callable[[T], bool]) -> Collection[T]`

Filter using a custom predicate function.

```python
long_runways = model.airports.filter(
    lambda a: a.longest_runway_length_ft and a.longest_runway_length_ft > 5000
).all()

complex = model.airports.filter(
    lambda a: a.has_hard_runway and
              len(a.procedures) > 10 and
              a.iso_country in ["FR", "DE", "GB"]
).all()
```

#### `.where(**kwargs) -> Collection[T]`

Filter by matching object attributes (AND logic).

```python
french_large = model.airports.where(
    iso_country="FR",
    has_hard_runway=True
).all()
```

#### `.first() -> Optional[T]`

Get first item or None.

```python
first = model.airports.by_country("FR").first()
missing = model.airports.where(ident="XXXX").first()  # Returns None
```

#### `.first_or_raise(exception: Optional[Exception] = None) -> T`

Get first item or raise exception.

```python
airport = model.airports.where(ident="EGLL").first_or_raise()
airport = model.airports.where(ident="XXXX").first_or_raise(
    ValueError("Airport not found")
)
```

#### `.all() -> List[T]`

Get all items as a list.

```python
french_list = model.airports.by_country("FR").all()
```

#### `.count() -> int`

Count items without loading all.

```python
count = model.airports.by_country("FR").count()
total = model.airports.count()
```

#### `.exists() -> bool`

Check if any items exist.

```python
has_french = model.airports.by_country("FR").exists()
```

#### `.any(predicate: Callable[[T], bool]) -> bool`

Check if any item matches predicate.

```python
has_ils = model.airports.any(
    lambda a: any(p.approach_type == 'ILS' for p in a.procedures)
)
```

#### `.all_match(predicate: Callable[[T], bool]) -> bool`

Check if all items match predicate.

```python
all_have_runways = model.airports.by_country("FR").all_match(
    lambda a: len(a.runways) > 0
)
```

#### `.take(n: int) -> Collection[T]`

Take first N items.

```python
first_ten = model.airports.take(10).all()
```

#### `.skip(n: int) -> Collection[T]`

Skip first N items.

```python
page_three = model.airports.skip(20).take(10).all()
```

#### `.order_by(key_func: Callable[[T], Any], reverse: bool = False) -> Collection[T]`

Sort the collection.

```python
by_name = model.airports.order_by(lambda a: a.name or '').all()
by_runway = model.airports.order_by(
    lambda a: a.longest_runway_length_ft or 0,
    reverse=True
).all()
```

#### `.distinct_by(key_func: Callable[[T], Any]) -> Collection[T]`

Remove duplicates by key (keeps first occurrence).

```python
one_per_country = model.airports.distinct_by(lambda a: a.iso_country)
```

#### `.map(transform: Callable[[T], Any]) -> Collection[Any]`

Transform each item.

```python
icao_codes = model.airports.map(lambda a: a.ident).all()
```

#### `.to_dict(key_func: Callable[[T], str]) -> Dict[str, T]`

Convert to dictionary. Raises ValueError on duplicate keys.

```python
airports_dict = model.airports.to_dict(lambda a: a.ident)
heathrow = airports_dict['EGLL']
```

#### `.group_by(key_func: Callable[[T], str]) -> Dict[str, List[T]]`

Group items by key function.

```python
by_country = model.airports.group_by(lambda a: a.iso_country)
french = by_country["FR"]
```

### AirportCollection Domain Methods

#### `.by_country(country_code: str) -> AirportCollection`

```python
french = model.airports.by_country("FR").all()
```

#### `.by_countries(country_codes: List[str]) -> AirportCollection`

```python
schengen = model.airports.by_countries(["FR", "DE", "ES", "IT"]).all()
```

#### `.by_source(source: str) -> AirportCollection`

```python
from_uk_aip = model.airports.by_source("uk_eaip").all()
```

#### `.by_sources(sources: List[str]) -> AirportCollection`

```python
eaip_airports = model.airports.by_sources(["uk_eaip", "france_eaip"]).all()
```

#### `.with_runways() -> AirportCollection`

```python
with_runways = model.airports.with_runways().all()
```

#### `.with_hard_runway() -> AirportCollection`

Airports with concrete/asphalt runways.

```python
paved = model.airports.with_hard_runway().all()
```

#### `.with_soft_runway() -> AirportCollection`

Airports with grass/dirt runways.

#### `.with_water_runway() -> AirportCollection`

Seaplane bases.

#### `.with_lighted_runway() -> AirportCollection`

Airports with night operations capability.

```python
night_capable = model.airports.with_lighted_runway().all()
```

#### `.with_min_runway_length(min_length_ft: int) -> AirportCollection`

```python
jet_capable = model.airports.with_min_runway_length(5000).all()
```

#### `.with_procedures(procedure_type: Optional[str] = None) -> AirportCollection`

```python
with_procs = model.airports.with_procedures().all()
with_approaches = model.airports.with_procedures("approach").all()
```

#### `.with_approach_type(approach_type: str) -> AirportCollection`

```python
with_ils = model.airports.with_approach_type("ILS").all()
with_rnav = model.airports.with_approach_type("RNAV").all()
```

#### `.with_aip_data() -> AirportCollection`

```python
with_aip = model.airports.with_aip_data().all()
```

#### `.with_standardized_aip_data() -> AirportCollection`

```python
standardized = model.airports.with_standardized_aip_data().all()
```

#### `.with_fuel(avgas: bool = False, jet_a: bool = False) -> AirportCollection`

```python
with_avgas = model.airports.with_fuel(avgas=True).all()
both_fuels = model.airports.with_fuel(avgas=True, jet_a=True).all()
```

#### `.border_crossings() -> AirportCollection`

```python
entry_points = model.airports.border_crossings().all()
french_entry = model.airports.border_crossings().by_country("FR").all()
```

#### `.in_region(region_code: str) -> AirportCollection`

```python
england = model.airports.in_region("GB-ENG").all()
```

#### `.by_continent(continent: str) -> AirportCollection`

```python
europe = model.airports.by_continent("EU").all()
```

#### `.with_coordinates() -> AirportCollection`

Filter to airports with valid lat/lon.

#### `.with_scheduled_service() -> AirportCollection`

Airports with commercial airline service.

### AirportCollection Grouping Methods

```python
by_country = model.airports.group_by_country()    # → Dict[str, List[Airport]]
by_source = model.airports.group_by_source()      # → Dict[str, List[Airport]]
by_continent = model.airports.group_by_continent() # → Dict[str, List[Airport]]
by_region = model.airports.group_by_region()      # → Dict[str, List[Airport]]
```

---

## Airport Attributes Reference

### Basic Information

| Attribute | Type | Description |
|-----------|------|-------------|
| `ident` | `str` | ICAO airport code (required, e.g., "EGLL") |
| `name` | `Optional[str]` | Airport name |
| `type` | `Optional[str]` | Airport type |
| `latitude_deg` | `Optional[float]` | Latitude (-90 to +90) |
| `longitude_deg` | `Optional[float]` | Longitude (-180 to +180) |
| `elevation_ft` | `Optional[str]` | Elevation in feet |
| `iso_country` | `Optional[str]` | ISO country code (e.g., "GB", "FR") |
| `iso_region` | `Optional[str]` | ISO region code |
| `municipality` | `Optional[str]` | City/municipality |
| `continent` | `Optional[str]` | Continent code |
| `iata_code` | `Optional[str]` | IATA code (e.g., "LHR") |
| `gps_code` | `Optional[str]` | GPS code |
| `local_code` | `Optional[str]` | Local airport code |
| `scheduled_service` | `Optional[str]` | "yes" or "no" |
| `home_link` | `Optional[str]` | Home page URL |
| `wikipedia_link` | `Optional[str]` | Wikipedia URL |

### Derived Runway Characteristics

Calculated from runway data by `update_all_derived_fields()`:

| Attribute | Type | Description |
|-----------|------|-------------|
| `has_hard_runway` | `Optional[bool]` | Has concrete/asphalt runway |
| `has_soft_runway` | `Optional[bool]` | Has grass/dirt runway |
| `has_water_runway` | `Optional[bool]` | Has water runway |
| `has_snow_runway` | `Optional[bool]` | Has snow runway |
| `has_lighted_runway` | `Optional[bool]` | Has lighted runway |
| `longest_runway_length_ft` | `Optional[int]` | Length of longest runway |

### AIP-Derived Fields

| Attribute | Type | Description |
|-----------|------|-------------|
| `avgas` | `Optional[bool]` | Has AVGAS (from AIP field 402) |
| `jet_a` | `Optional[bool]` | Has Jet A fuel (from AIP field 402) |
| `point_of_entry` | `Optional[bool]` | Is border crossing point |

### Relationship Attributes

| Attribute | Type | Description |
|-----------|------|-------------|
| `runways` | `List[Runway]` | Runway objects |
| `aip_entries` | `List[AIPEntry]` | AIP data entries |
| `procedures` | `List[Procedure]` | Procedure objects |
| `sources` | `Set[str]` | Data source names |

### Computed Properties

| Property | Type | Description |
|----------|------|-------------|
| `navpoint` | `Optional[NavPoint]` | For distance calculations |
| `procedures_query` | `ProcedureCollection` | Queryable procedures |

### Airport Methods

```python
airport.get_authority()  # → str (e.g., "EGC" from "EGLL")

airport.get_most_precise_approach_for_runway(runway)  # → Optional[Procedure]
# Modern: airport.procedures_query.approaches().by_runway("09L").most_precise()

airport.get_aip_entry_for_field(402)  # → Optional[AIPEntry] (by field ID)
airport.get_aip_entry_by_field("Fuel and oil types")  # → Optional[AIPEntry]
airport.get_aip_entries_by_section("admin")  # → List[AIPEntry]
airport.get_standardized_entries()  # → List[AIPEntry]
airport.get_standardized_aip_data()  # → Dict[str, str]
airport.has_standardized_field(402)  # → bool
```

---

## Procedure Querying

### ProcedureCollection Methods

#### Type Filters

```python
.approaches()    # Approach procedures only
.departures()    # SIDs only
.arrivals()      # STARs only
```

#### `.by_type(approach_type: str) -> ProcedureCollection`

```python
ils = model.procedures.approaches().by_type("ILS").all()
```

#### `.by_runway(runway_ident: str) -> ProcedureCollection`

```python
rwy_09l = model.procedures.by_runway("09L").all()
```

#### `.for_runway(runway: Runway) -> ProcedureCollection`

Matches by Runway object (either end).

```python
rwy_procs = procedures.for_runway(runway_obj).all()
```

#### `.by_source(source: str) -> ProcedureCollection`

```python
uk_procedures = model.procedures.by_source("uk_eaip").all()
```

#### `.by_authority(authority: str) -> ProcedureCollection`

```python
egc_procedures = model.procedures.by_authority("EGC").all()
```

#### Precision Methods

```python
.most_precise()                   # → Optional[Procedure]
.by_precision_order()             # Sort by precision (best first)
.precision_approaches()           # ILS only
.rnp_approaches()                 # RNP/RNAV only
.non_precision_approaches()       # VOR, NDB, LOC, etc.
.with_precision_better_than("VOR") # More precise than specified type
```

**Example:**
```python
best = airport.procedures_query \
    .approaches() \
    .by_runway("09L") \
    .most_precise()
```

### ProcedureCollection Grouping

```python
.group_by_runway()       # → Dict[str, List[Procedure]]
.group_by_type()         # → Dict[str, List[Procedure]]
.group_by_approach_type() # → Dict[str, List[Procedure]]
.group_by_source()       # → Dict[str, List[Procedure]]
.group_by_authority()    # → Dict[str, List[Procedure]]
```

---

## Procedure Attributes Reference

| Attribute | Type | Description | Values |
|-----------|------|-------------|--------|
| `airport_ident` | `str` | ICAO code (required) | |
| `name` | `str` | Procedure name (required) | e.g., "ILS 09L" |
| `procedure_type` | `str` | Type (required) | 'approach', 'departure', 'arrival' |
| `approach_type` | `Optional[str]` | Approach type | 'ILS', 'VOR', 'NDB', 'RNAV', 'RNP', 'LOC', 'LDA', 'SDF' |
| `runway_ident` | `Optional[str]` | Runway identifier | e.g., "09L", "27R" |
| `runway_number` | `Optional[str]` | Runway number | e.g., "09", "27" |
| `runway_letter` | `Optional[str]` | Runway letter | "L", "R", "C" or None |
| `source` | `Optional[str]` | Data source | e.g., "uk_eaip" |
| `authority` | `Optional[str]` | Authority code | e.g., "EGC", "LFC" |
| `raw_name` | `Optional[str]` | Original name | |
| `data` | `Optional[Dict]` | Additional data | |

### Precision Hierarchy

1. **ILS** (1) - Most precise
2. **RNP** (2)
3. **RNAV** (3)
4. **VOR** (4)
5. **NDB** (5)
6. **LOC** (6)
7. **LDA** (7)
8. **SDF** (8) - Least precise

### Procedure Methods

```python
procedure.is_approach()      # → bool
procedure.is_departure()     # → bool
procedure.is_arrival()       # → bool
procedure.get_full_runway_ident()  # → Optional[str]
procedure.matches_runway(runway)   # → bool
procedure.get_approach_precision() # → int (lower = more precise)
procedure.compare_precision(other) # → -1, 0, or 1
procedure.is_more_precise_than(other)  # → bool
procedure.is_less_precise_than(other)  # → bool
```

---

## AIP Data Querying

### From Airport Objects

```python
airport = model.airports['EGLL']

# All AIP entries
all_entries = airport.aip_entries

# Filter by section
admin_entries = [e for e in airport.aip_entries if e.section == "admin"]

# Get specific field by ID
fuel_entry = airport.get_aip_entry_for_field(402)

# Get by field name
fuel_entry = airport.get_aip_entry_by_field("Fuel and oil types")

# Get by section
admin = airport.get_aip_entries_by_section("admin")

# Standardized entries only
standardized = airport.get_standardized_entries()

# As dictionary
aip_dict = airport.get_standardized_aip_data()
# → {"Fuel and oil types": "AVGAS, JET A", ...}
```

### Model-Level Statistics

```python
stats = model.get_field_mapping_statistics()
# Returns:
# {
#     'total_fields': int,
#     'mapped_fields': int,
#     'unmapped_fields': int,
#     'mapping_rate': float,
#     'average_mapping_score': float,
#     'section_counts': Dict[str, int]
# }
```

---

## AIPEntry Attributes Reference

| Attribute | Type | Description |
|-----------|------|-------------|
| `ident` | `str` | ICAO airport code |
| `section` | `str` | 'admin', 'operational', 'handling', 'passenger' |
| `field` | `str` | Original field name |
| `value` | `str` | Field value |
| `std_field` | `Optional[str]` | Standardized field name |
| `std_field_id` | `Optional[int]` | Standard field ID (e.g., 402 for fuel) |
| `mapping_score` | `Optional[float]` | Similarity score (0.0-1.0) |
| `alt_field` | `Optional[str]` | Alternative language field |
| `alt_value` | `Optional[str]` | Alternative language value |
| `source` | `Optional[str]` | Data source |

### AIPEntry Methods

```python
entry.is_standardized()         # → bool
entry.get_effective_field_name() # → str (std_field or field)
entry.to_dict()                 # → Dict
```

---

## Runway Attributes Reference

### Basic Attributes

| Attribute | Type | Description |
|-----------|------|-------------|
| `airport_ident` | `str` | ICAO code |
| `length_ft` | `Optional[float]` | Length in feet |
| `width_ft` | `Optional[float]` | Width in feet |
| `surface` | `Optional[str]` | "CONCRETE", "ASPHALT", "GRASS", etc. |
| `lighted` | `Optional[bool]` | Has lighting |
| `closed` | `Optional[bool]` | Is closed |

### Low End (LE) Attributes

| Attribute | Type | Description |
|-----------|------|-------------|
| `le_ident` | `Optional[str]` | Low end identifier (e.g., "09L") |
| `le_latitude_deg` | `Optional[float]` | Low end latitude |
| `le_longitude_deg` | `Optional[float]` | Low end longitude |
| `le_elevation_ft` | `Optional[float]` | Low end elevation |
| `le_heading_degT` | `Optional[float]` | Low end heading (true) |
| `le_displaced_threshold_ft` | `Optional[float]` | Displaced threshold |

### High End (HE) Attributes

| Attribute | Type | Description |
|-----------|------|-------------|
| `he_ident` | `Optional[str]` | High end identifier (e.g., "27R") |
| `he_latitude_deg` | `Optional[float]` | High end latitude |
| `he_longitude_deg` | `Optional[float]` | High end longitude |
| `he_elevation_ft` | `Optional[float]` | High end elevation |
| `he_heading_degT` | `Optional[float]` | High end heading (true) |
| `he_displaced_threshold_ft` | `Optional[float]` | Displaced threshold |

---

## NavPoint & Distance Calculations

### NavPoint Attributes

| Attribute | Type | Description |
|-----------|------|-------------|
| `latitude` | `float` | Latitude (-90 to +90) |
| `longitude` | `float` | Longitude (-180 to +180) |
| `name` | `Optional[str]` | Optional identifier |
| `EARTH_RADIUS_NM` | `3440.065` | Earth's radius in NM |

### NavPoint Methods

```python
# Distance and bearing
bearing, distance = point1.haversine_distance(point2)

# Create point from bearing/distance
new_point = point.point_from_bearing_distance(bearing=045, distance=50, name="FIX")

# Distance to line segment
dist = point.distance_to_segment(line_start, line_end)

# Coordinate formats
lat_dms, lon_dms = point.to_dms()  # → ("48° 51' 24\" N", "2° 21' 8\" E")
lat_dm, lon_dm = point.to_dm()    # → ("48° 51.40' N", "2° 21.13' E")
csv = point.to_csv()              # → "name,description,lat,lon"
```

### Find Airports Near Route

```python
route = ["EGLL", "LFPG", "EDDF"]
nearby = model.find_airports_near_route(route, distance_nm=50.0)

# Returns list of:
# {
#     'airport': Airport,
#     'segment_distance_nm': float,    # Perpendicular distance
#     'enroute_distance_nm': float,    # Distance along route
#     'closest_segment': Tuple[str, str]
# }

# Filter further
suitable = [
    r for r in nearby
    if r['airport'].has_hard_runway and r['segment_distance_nm'] < 25.0
]
```

---

## Border Crossings

### Using Collections (Recommended)

```python
# All border crossing airports
entry_points = model.airports.border_crossings().all()

# Border crossings in France
french_entry = model.airports.border_crossings().by_country("FR").all()

# Border crossings with ILS
ils_entry = model.airports.border_crossings().with_approach_type("ILS").all()

# Count
count = model.airports.border_crossings().count()

# Check if airport is border crossing
egll = model.airports['EGLL']
is_entry = egll.point_of_entry
```

### Legacy Methods

```python
model.get_border_crossing_points_by_country("FR")  # → List[BorderCrossingEntry]
model.get_border_crossing_entry("FR", "LFPG")      # → Optional[BorderCrossingEntry]
model.get_all_border_crossing_points()             # → List[BorderCrossingEntry]
model.get_border_crossing_countries()              # → List[str]
model.get_border_crossing_statistics()             # → Dict
```

### BorderCrossingEntry Attributes

| Attribute | Type | Description |
|-----------|------|-------------|
| `airport_name` | `str` | Airport name |
| `country_iso` | `str` | ISO country code |
| `icao_code` | `Optional[str]` | ICAO code |
| `is_airport` | `Optional[bool]` | Is an airport |
| `source` | `Optional[str]` | Data source |
| `matched_airport_icao` | `Optional[str]` | Matched ICAO |
| `match_score` | `Optional[float]` | Match confidence |

---

## Statistics & Metadata

### Model Statistics

```python
stats = model.get_statistics()
# Returns:
# {
#     'total_airports': int,
#     'airports_with_runways': int,
#     'airports_with_procedures': int,
#     'airports_with_aip_data': int,
#     'airports_with_border_crossing': int,
#     'total_runways': int,
#     'total_procedures': int,
#     'total_aip_entries': int,
#     'total_border_crossing_points': int,
#     'procedure_types': Dict[str, int],
#     'border_crossing': Dict[str, Any],
#     'sources_used': List[str],
#     'created_at': str,
#     'updated_at': str
# }

print(f"Total airports: {stats['total_airports']}")
print(f"With procedures: {stats['airports_with_procedures']}")
```
