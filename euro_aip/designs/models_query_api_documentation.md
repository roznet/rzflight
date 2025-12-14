# Euro AIP Models Query API Documentation

**Version:** 2.0 (Modern Query API)
**Last Updated:** December 2025

This document describes how to query and use a `EuroAipModel` object using the modern queryable collections interface. It covers all methods for accessing airports, procedures, routes, AIP data, border crossings, and statistics.

**Target Audience:** Developers and AI agents who need to query and extract information from an existing model.

---

## Table of Contents

1. [Overview](#overview)
2. [Core Collections](#core-collections)
3. [Querying Airports](#querying-airports)
4. [Airport Attributes Reference](#airport-attributes-reference)
5. [Querying Procedures](#querying-procedures)
6. [Procedure Attributes Reference](#procedure-attributes-reference)
7. [Querying AIP Data](#querying-aip-data)
8. [AIPEntry Attributes Reference](#aipentry-attributes-reference)
9. [Querying Runways](#querying-runways)
10. [Runway Attributes Reference](#runway-attributes-reference)
11. [Route and Distance Calculations](#route-and-distance-calculations)
12. [NavPoint Attributes Reference](#navpoint-attributes-reference)
13. [Border Crossing Queries](#border-crossing-queries)
14. [BorderCrossingEntry Attributes Reference](#bordercrossingentry-attributes-reference)
15. [Statistics and Metadata](#statistics-and-metadata)
16. [Common Patterns](#common-patterns)

---

## Overview

The modern query API provides a fluent, composable interface for querying Euro AIP data through:

- **Queryable Collections** - Chainable filter methods instead of multiple `get_*` methods
- **Type Safety** - Full generic typing with IDE autocomplete support
- **Consistency** - Predictable patterns across all entity types
- **Flexibility** - Combine domain filters with custom predicates
- **Performance** - Optimizable query pipelines

### Key Concepts

1. **Collections** - Primary entry points: `model.airports` and `model.procedures`
2. **Chaining** - Filters combine with method chaining
3. **Terminal Operations** - `.all()`, `.first()`, `.count()`, `.exists()` execute queries
4. **Iteration** - Collections are iterable without calling `.all()`
5. **Domain Filters** - Specialized methods like `.by_country()`, `.with_runways()`
6. **Custom Filters** - Generic `.filter()` and `.where()` for any logic
7. **Dict-Style Access** - Direct lookup by ICAO: `airports['EGLL']`, `'EGLL' in airports`
8. **Set Operations** - Union (`|`), intersection (`&`), difference (`-`) for combining collections
9. **Reverse Iteration** - Support for `reversed()` built-in

---

## Core Collections

### Model-Level Collections

The `EuroAipModel` provides two main collection properties:

#### `model.airports` → AirportCollection

Returns a queryable collection of all airports in the model.

```python
from euro_aip.models import EuroAipModel

model = EuroAipModel.from_file("data/euro_aip.json")

# Collection of all airports
airports = model.airports

# Use collection methods
french = model.airports.by_country("FR").all()
count = model.airports.count()
```

#### `model.procedures` → ProcedureCollection

Returns a queryable collection of all procedures across all airports.

```python
# Collection of all procedures
procedures = model.procedures

# Query procedures globally
ils_approaches = model.procedures.approaches().by_type("ILS").all()
```

### Dict-Style Access (Convenience API)

The `AirportCollection` supports dict-style access for convenient ICAO code lookups:

```python
# Dict-style lookup by ICAO code (most concise)
heathrow = model.airports['EGLL']

# Check existence with 'in' operator
if 'EGLL' in model.airports:
    print("Heathrow found")

# Safe lookup with default value
airport = model.airports.get('EGLL', default=None)

# Still works with filtered collections
french = model.airports.by_country("FR")
cdg = french['LFPG']  # Get CDG from French airports
```

**When to use:**
- **Dict-style** (`airports['EGLL']`) - When you have an ICAO code and want a single airport
- **Query API** (`airports.where(ident='EGLL').first()`) - When you need complex filtering
- **List-style** (`airports[0]`, `airports[0:10]`) - For indexing and slicing

### Set Operations (Combining Collections)

Collections support Python's set operators for clean, expressive combination logic:

#### Union Operator (`|`) - OR Logic

Combine collections, removing duplicates:

```python
# Get airports from multiple countries (OR logic)
western_europe = (
    model.airports.by_country("FR") |
    model.airports.by_country("DE") |
    model.airports.by_country("BE")
)

# Alternative to .by_countries()
schengen = (
    model.airports.by_country("FR") |
    model.airports.by_country("DE") |
    model.airports.by_country("IT")
)
```

#### Intersection Operator (`&`) - AND Logic

Find items present in both collections:

```python
# Airports with BOTH hard runways AND fuel
premium = (
    model.airports.with_hard_runway() &
    model.airports.with_fuel(avgas=True, jet_a=True)
)

# Complex AND logic
suitable = (
    model.airports.by_country("FR") &
    model.airports.with_min_runway_length(5000) &
    model.airports.with_procedures("approach")
)
```

#### Difference Operator (`-`) - Exclusion

Remove items from the first collection:

```python
# Airports with runways but NO procedures
basic = model.airports.with_runways() - model.airports.with_procedures()

# French airports excluding Paris area
paris_area = model.airports.by_country("FR").filter(
    lambda a: a.name and 'Paris' in a.name
)
provincial = model.airports.by_country("FR") - paris_area
```

#### Complex Combinations

Set operations can be chained and combined:

```python
# (FR OR DE) AND (hard_runway) - NOT (procedures)
result = (
    (model.airports.by_country("FR") | model.airports.by_country("DE")) &
    model.airports.with_hard_runway()
) - model.airports.with_procedures()
```

### Reverse Iteration

Collections support Python's `reversed()` built-in:

```python
# Iterate in reverse order
for airport in reversed(model.airports.order_by('name')):
    print(airport.name)  # Z to A

# Reverse a filtered collection
last_ten = list(reversed(
    model.airports.by_country("FR").take(10)
))
```

### Better Debug Output

Collections now show a preview of items in their representation:

```python
>>> model.airports.by_country("FR")
AirportCollection(['LFPG', 'LFPO', 'LFLL', ...], count=234)

>>> model.airports.by_country("FR").take(2)
AirportCollection(['LFPG', 'LFPO'], count=2)

>>> AirportCollection([])
AirportCollection([])
```

### Airport-Level Collections

Each `Airport` object provides access to its procedures:

#### `airport.procedures_query` → ProcedureCollection

Returns a queryable collection of procedures for that specific airport.

```python
heathrow = model.airports['EGLL']  # Dict-style lookup

# Query this airport's procedures
approaches = heathrow.procedures_query.approaches().all()
ils = heathrow.procedures_query.approaches().by_type("ILS").all()
best = heathrow.procedures_query.approaches().by_runway("09L").most_precise()
```

---

## Querying Airports

### Base Collection Methods

All collections inherit these core methods from `QueryableCollection`:

#### `.filter(predicate: Callable[[T], bool]) -> Collection[T]`

Filter using a custom predicate function.

```python
# Custom filtering logic
long_runways = model.airports.filter(
    lambda a: a.longest_runway_length_ft and a.longest_runway_length_ft > 5000
).all()

# Complex criteria
complex = model.airports.filter(
    lambda a: a.has_hard_runway and
              len(a.procedures) > 10 and
              a.iso_country in ["FR", "DE", "GB"]
).all()
```

#### `.where(**kwargs) -> Collection[T]`

Filter by matching object attributes.

```python
# Find specific airport by ICAO (dict-style is more concise)
heathrow = model.airports['EGLL']  # Recommended for single ICAO lookup
# or
heathrow = model.airports.where(ident="EGLL").first()  # Query API alternative

# Match multiple attributes (use query API)
french_large = model.airports.where(
    iso_country="FR",
    has_hard_runway=True
).all()
```

#### `.first() -> Optional[T]`

Get the first item in the collection, or None if empty.

```python
# Get first French airport
first = model.airports.by_country("FR").first()

# Returns None if no match
missing = model.airports.where(ident="XXXX").first()
```

#### `.all() -> List[T]`

Get all items as a list.

```python
# Execute query and get results
french_list = model.airports.by_country("FR").all()
```

#### `.count() -> int`

Count items in the collection.

```python
# How many French airports?
count = model.airports.by_country("FR").count()

# Total airports
total = model.airports.count()
```

#### `.exists() -> bool`

Check if any items exist.

```python
# Are there any French airports?
has_french = model.airports.by_country("FR").exists()
```

#### `.take(n: int) -> Collection[T]`

Take first N items (for pagination).

```python
# First 10 airports
first_ten = model.airports.take(10).all()
```

#### `.skip(n: int) -> Collection[T]`

Skip first N items (for pagination).

```python
# Skip first 20, take next 10
page_three = model.airports.skip(20).take(10).all()
```

#### `.order_by(key: Callable[[T], Any], reverse: bool = False) -> Collection[T]`

Sort the collection.

```python
# Sort by name
by_name = model.airports.order_by(lambda a: a.name or '').all()

# Longest runways first
by_runway = model.airports.order_by(
    lambda a: a.longest_runway_length_ft or 0,
    reverse=True
).all()
```

#### `.group_by(key: Callable[[T], Any]) -> Dict[Any, List[T]]`

Group items by a key function.

```python
# Group by country
by_country = model.airports.group_by(lambda a: a.iso_country)
french = by_country["FR"]  # List of French airports
```

### AirportCollection Domain Methods

`AirportCollection` extends the base methods with aviation-specific filters:

#### `.by_country(country_code: str) -> AirportCollection`

Filter airports by country.

```python
french = model.airports.by_country("FR").all()
```

#### `.by_countries(country_codes: List[str]) -> AirportCollection`

Filter airports by multiple countries.

```python
schengen = model.airports.by_countries(["FR", "DE", "ES", "IT"]).all()
```

#### `.by_source(source: str) -> AirportCollection`

Filter airports by data source.

```python
from_uk_aip = model.airports.by_source("uk_eaip").all()
```

#### `.with_runways() -> AirportCollection`

Filter airports that have runway data.

```python
with_runways = model.airports.with_runways().all()
```

#### `.with_hard_runway() -> AirportCollection`

Filter airports with hard surface runways (concrete/asphalt).

```python
paved = model.airports.with_hard_runway().all()
```

#### `.with_lighted_runway() -> AirportCollection`

Filter airports with lighted runways.

```python
night_capable = model.airports.with_lighted_runway().all()
```

#### `.with_min_runway_length(min_length_ft: int) -> AirportCollection`

Filter by minimum runway length.

```python
jet_capable = model.airports.with_min_runway_length(5000).all()
```

#### `.with_procedures(procedure_type: Optional[str] = None) -> AirportCollection`

Filter airports that have procedures. Optionally filter by type.

```python
# Any procedures
with_procs = model.airports.with_procedures().all()

# Specific type
with_approaches = model.airports.with_procedures("approach").all()
```

#### `.with_approach_type(approach_type: str) -> AirportCollection`

Filter airports that have a specific approach type.

```python
# Airports with ILS
with_ils = model.airports.with_approach_type("ILS").all()

# Airports with RNAV
with_rnav = model.airports.with_approach_type("RNAV").all()
```

#### `.with_aip_data() -> AirportCollection`

Filter airports that have AIP data entries.

```python
with_aip = model.airports.with_aip_data().all()
```

#### `.with_fuel(avgas: bool = False, jet_a: bool = False) -> AirportCollection`

Filter airports by fuel availability.

```python
# AVGAS available
with_avgas = model.airports.with_fuel(avgas=True).all()

# Both fuels
both_fuels = model.airports.with_fuel(avgas=True, jet_a=True).all()
```

#### `.border_crossings() -> AirportCollection`

Filter airports that are official border crossing points.

```python
entry_points = model.airports.border_crossings().all()

# Border crossings in France
french_entry = model.airports.border_crossings().by_country("FR").all()
```

### AirportCollection Grouping Methods

#### `.group_by_country() -> Dict[str, List[Airport]]`

Group airports by country.

```python
by_country = model.airports.group_by_country()
french = by_country["FR"]
german = by_country["DE"]
```

#### `.group_by_source() -> Dict[str, List[Airport]]`

Group airports by data source.

```python
by_source = model.airports.group_by_source()
uk_aip_airports = by_source.get("uk_eaip", [])
```

#### `.group_by_continent() -> Dict[str, List[Airport]]`

Group airports by continent.

```python
by_continent = model.airports.group_by_continent()
european = by_continent.get("EU", [])
```

### Iteration Support

Collections are iterable without calling `.all()`:

```python
# Direct iteration
for airport in model.airports.by_country("FR"):
    print(f"{airport.ident}: {airport.name}")

# List comprehension
names = [a.name for a in model.airports.with_runways()]
```

### Indexing and Slicing

Collections support indexing and slicing:

```python
# Get first airport
first = model.airports[0]

# Get last airport
last = model.airports[-1]

# Slice
subset = model.airports[10:20]  # Returns new collection
```

---

## Airport Attributes Reference

### Basic Information Attributes

| Attribute | Type | Description | Source |
|-----------|------|-------------|--------|
| `ident` | `str` | ICAO airport code (required, e.g., "EGLL", "LFPG") | Direct input |
| `name` | `Optional[str]` | Airport name | Direct input |
| `type` | `Optional[str]` | Airport type | Direct input |
| `latitude_deg` | `Optional[float]` | Latitude in decimal degrees (-90 to +90) | Direct input |
| `longitude_deg` | `Optional[float]` | Longitude in decimal degrees (-180 to +180) | Direct input |
| `elevation_ft` | `Optional[str]` | Elevation in feet (stored as string) | Direct input |
| `iso_country` | `Optional[str]` | ISO country code (e.g., "GB", "FR", "DE") | Direct input |
| `iso_region` | `Optional[str]` | ISO region code | Direct input |
| `municipality` | `Optional[str]` | City/municipality name | Direct input |
| `continent` | `Optional[str]` | Continent code | Direct input |
| `iata_code` | `Optional[str]` | IATA airport code (e.g., "LHR", "CDG") | Direct input |
| `gps_code` | `Optional[str]` | GPS code | Direct input |
| `local_code` | `Optional[str]` | Local airport code | Direct input |
| `scheduled_service` | `Optional[str]` | Scheduled service indicator | Direct input |
| `home_link` | `Optional[str]` | Home page URL | Direct input |
| `wikipedia_link` | `Optional[str]` | Wikipedia page URL | Direct input |
| `keywords` | `Optional[str]` | Keywords | Direct input |

### Derived Runway Characteristics

These attributes are calculated from runway data by `update_all_derived_fields()`:

| Attribute | Type | Description | Source |
|-----------|------|-------------|--------|
| `has_hard_runway` | `Optional[bool]` | True if airport has hard surface runway (concrete, asphalt) | Derived from `runways` list using surface classification |
| `has_soft_runway` | `Optional[bool]` | True if airport has soft surface runway (grass, dirt) | Derived from `runways` list using surface classification |
| `has_water_runway` | `Optional[bool]` | True if airport has water runway | Derived from `runways` list using surface classification |
| `has_snow_runway` | `Optional[bool]` | True if airport has snow runway | Derived from `runways` list using surface classification |
| `has_lighted_runway` | `Optional[bool]` | True if airport has at least one lighted runway | Derived from `runways[].lighted` |
| `longest_runway_length_ft` | `Optional[int]` | Length of longest runway in feet | Derived from `runways[].length_ft` |

### AIP-Derived Fields

These attributes are calculated from AIP data by `update_all_derived_fields()`:

| Attribute | Type | Description | Source |
|-----------|------|-------------|--------|
| `avgas` | `Optional[bool]` | True if airport has AVGAS fuel available | Derived from AIP field ID 402 ("Fuel and oil types") - looks for "AVGAS" or "100LL" in value |
| `jet_a` | `Optional[bool]` | True if airport has Jet A fuel available | Derived from AIP field ID 402 ("Fuel and oil types") - looks for "JET A", "JET-A", "JETA1", "JET A-1", "JET A1", or "AVTUR" in value |
| `point_of_entry` | `Optional[bool]` | True if airport is a border crossing point | Derived from border crossing data in model |

### Relationship Attributes

| Attribute | Type | Description |
|-----------|------|-------------|
| `runways` | `List[Runway]` | List of Runway objects for this airport |
| `aip_entries` | `List[AIPEntry]` | List of AIPEntry objects containing AIP data |
| `procedures` | `List[Procedure]` | List of Procedure objects (approaches, departures, arrivals) |
| `sources` | `Set[str]` | Set of data source names (e.g., {"worldairports", "uk_eaip"}) |

### Metadata Attributes

| Attribute | Type | Description |
|-----------|------|-------------|
| `created_at` | `datetime` | Creation timestamp |
| `updated_at` | `datetime` | Last update timestamp |

### Computed Properties

| Property | Type | Description |
|----------|------|-------------|
| `navpoint` | `Optional[NavPoint]` | NavPoint representation of airport coordinates. Automatically created from `latitude_deg` and `longitude_deg` if available. Setting this property updates `latitude_deg` and `longitude_deg`. |
| `procedures_query` | `ProcedureCollection` | Queryable collection of this airport's procedures. Use for filtering and querying procedures at the airport level. |

### Airport Methods

#### `get_authority() -> str`

Get the authority code for the airport. Derived from first 2 letters of ICAO code (e.g., "EG" → "EGC"). Special case: "ET" → "EDC".

#### `get_most_precise_approach_for_runway(runway: Runway) -> Optional[Procedure]`

Get the most precise approach procedure for a runway. Precision order: ILS > RNP > RNAV > VOR > NDB > LOC > LDA > SDF.

**Modern Alternative:**
```python
# Using procedures_query
best = airport.procedures_query.approaches().by_runway(runway.le_ident).most_precise()
```

#### `get_most_precise_approach_for_runway_end(runway: Runway, runway_end_ident: str) -> Optional[Procedure]`

Get the most precise approach for a specific runway end (e.g., "13L").

**Modern Alternative:**
```python
# Using procedures_query
best = airport.procedures_query.approaches().by_runway("13L").most_precise()
```

#### `get_precision_category(approach_type: str) -> str`

Get precision category for an approach type:
- 'ILS' → 'precision'
- 'RNP', 'RNAV' → 'rnp'
- Others → 'non-precision'

---

## Querying Procedures

### ProcedureCollection Methods

#### `.approaches() -> ProcedureCollection`

Filter to approach procedures only.

```python
# All approaches across all airports
approaches = model.procedures.approaches().all()

# Approaches at specific airport
heathrow_approaches = heathrow.procedures_query.approaches().all()
```

#### `.departures() -> ProcedureCollection`

Filter to departure procedures (SIDs) only.

```python
departures = model.procedures.departures().all()
```

#### `.arrivals() -> ProcedureCollection`

Filter to arrival procedures (STARs) only.

```python
arrivals = model.procedures.arrivals().all()
```

#### `.by_type(approach_type: str) -> ProcedureCollection`

Filter by approach type (ILS, RNAV, VOR, etc.).

```python
# All ILS approaches
ils = model.procedures.approaches().by_type("ILS").all()

# RNAV approaches at EGLL
rnav = heathrow.procedures_query.approaches().by_type("RNAV").all()
```

#### `.by_runway(runway_ident: str) -> ProcedureCollection`

Filter by runway identifier.

```python
# All procedures for runway 09L
rwy_09l = model.procedures.by_runway("09L").all()

# Approaches for runway 27R at EGLL
approaches_27r = heathrow.procedures_query.approaches().by_runway("27R").all()
```

#### `.by_source(source: str) -> ProcedureCollection`

Filter by data source.

```python
uk_procedures = model.procedures.by_source("uk_eaip").all()
```

#### `.by_authority(authority: str) -> ProcedureCollection`

Filter by authority code.

```python
egc_procedures = model.procedures.by_authority("EGC").all()
```

#### `.most_precise() -> Optional[Procedure]`

Get the most precise approach from the collection.

```python
# Most precise approach for runway 09L at EGLL
best = heathrow.procedures_query.approaches() \
                                .by_runway("09L") \
                                .most_precise()
```

#### `.by_precision_order() -> ProcedureCollection`

Sort approaches by precision (most precise first).

```python
# Get approaches sorted by precision
sorted_approaches = heathrow.procedures_query.approaches() \
                                             .by_runway("09L") \
                                             .by_precision_order() \
                                             .all()
```

#### `.precision_approaches() -> ProcedureCollection`

Filter to precision approaches (ILS) only.

```python
ils_only = model.procedures.precision_approaches().all()
```

#### `.rnp_approaches() -> ProcedureCollection`

Filter to RNP approaches only.

```python
rnp = model.procedures.rnp_approaches().all()
```

#### `.non_precision_approaches() -> ProcedureCollection`

Filter to non-precision approaches (VOR, NDB, LOC, etc.).

```python
non_precision = model.procedures.non_precision_approaches().all()
```

### ProcedureCollection Grouping Methods

#### `.group_by_type() -> Dict[str, List[Procedure]]`

Group procedures by procedure type.

```python
by_type = model.procedures.group_by_type()
approaches = by_type.get("approach", [])
departures = by_type.get("departure", [])
```

#### `.group_by_approach_type() -> Dict[str, List[Procedure]]`

Group approach procedures by approach type.

```python
by_approach = model.procedures.approaches().group_by_approach_type()
ils = by_approach.get("ILS", [])
rnav = by_approach.get("RNAV", [])
```

#### `.group_by_runway() -> Dict[str, List[Procedure]]`

Group procedures by runway.

```python
by_runway = heathrow.procedures_query.group_by_runway()
rwy_09l = by_runway.get("09L", [])
```

---

## Procedure Attributes Reference

### Basic Attributes

| Attribute | Type | Description | Format/Values |
|-----------|------|-------------|---------------|
| `airport_ident` | `str` | ICAO code of the airport (required) | ICAO code (e.g., "EGLL") |
| `name` | `str` | Procedure name (required, e.g., "ILS 09L", "RWY13 ILS LOC") | Free text |
| `procedure_type` | `str` | Procedure type (required) | One of: 'approach', 'departure', 'arrival' |
| `approach_type` | `Optional[str]` | Approach type (for approach procedures) | One of: 'ILS', 'VOR', 'NDB', 'RNAV', 'RNP', 'LOC', 'LDA', 'SDF', etc. |
| `runway_ident` | `Optional[str]` | Full runway identifier | Format: "09L", "27R", "24" (runway number + optional letter L/R/C) |
| `runway_number` | `Optional[str]` | Runway number | Format: "09", "27", "24" (two-digit number) |
| `runway_letter` | `Optional[str]` | Runway letter | Format: "L", "R", "C" (Left, Right, Center) or None |
| `source` | `Optional[str]` | Data source | Source name (e.g., "uk_eaip", "france_eaip") |
| `authority` | `Optional[str]` | Authority code | Format: "EGC", "LFC", "EDC" (derived from ICAO prefix + 'C') |
| `raw_name` | `Optional[str]` | Original procedure name | Free text |
| `data` | `Optional[Dict[str, Any]]` | Additional raw data | Dictionary with arbitrary keys/values |
| `created_at` | `datetime` | Creation timestamp | datetime object |
| `updated_at` | `datetime` | Last update timestamp | datetime object |

### Procedure Precision Hierarchy

Approach procedures have a precision hierarchy (lower number = more precise):
1. ILS (1) - Instrument Landing System (most precise)
2. RNP (2) - Required Navigation Performance
3. RNAV (3) - Area Navigation
4. VOR (4) - VHF Omnidirectional Range
5. NDB (5) - Non-Directional Beacon
6. LOC (6) - Localizer
7. LDA (7) - Localizer Directional Aid
8. SDF (8) - Simplified Directional Facility (least precise)

### Procedure Methods

#### `get_full_runway_ident() -> Optional[str]`

Get the full runway identifier. Combines `runway_number` and `runway_letter`, or returns `runway_ident` if available.

**Returns:** Runway identifier string (e.g., "09L", "24") or None

#### `matches_runway(runway: Runway) -> bool`

Check if this procedure matches a runway by comparing `runway_ident` with runway's `le_ident` or `he_ident`.

#### `is_approach() -> bool`

Check if this is an approach procedure.

#### `is_departure() -> bool`

Check if this is a departure procedure.

#### `is_arrival() -> bool`

Check if this is an arrival procedure.

#### `get_approach_precision() -> int`

Get the precision ranking for this procedure's approach type. Returns 999 for unknown types or non-approach procedures.

**Returns:** Integer (lower = more precise, 999 = unknown/lowest)

#### `compare_precision(other: Procedure) -> int`

Compare precision with another procedure:
- Returns -1 if this is more precise
- Returns 0 if same precision
- Returns 1 if other is more precise

#### `is_more_precise_than(other: Procedure) -> bool`

Check if this procedure is more precise than another.

#### `is_less_precise_than(other: Procedure) -> bool`

Check if this procedure is less precise than another.

#### `has_same_precision_as(other: Procedure) -> bool`

Check if this procedure has the same precision as another.

---

## Querying AIP Data

AIP (Aeronautical Information Publication) data is stored as standardized entries accessible through Airport objects.

### Getting AIP Data from Airport Objects

Each airport has an `aip_entries` list that can be filtered and queried:

```python
airport = model.airports.where(ident="EGLL").first()

# Get all AIP entries
all_entries = airport.aip_entries

# Filter by section
admin_entries = [e for e in airport.aip_entries if e.section == "admin"]

# Get specific field by ID
fuel_entry = next((e for e in airport.aip_entries if e.std_field_id == 402), None)

# Get standardized entries only
standardized = [e for e in airport.aip_entries if e.is_standardized()]
```

### Airport Methods for AIP Data

#### `get_aip_entry_for_field(std_field_id: int) -> Optional[AIPEntry]`

Get AIP entry by standardized field ID.

```python
# Get fuel information (field ID 402)
fuel_entry = airport.get_aip_entry_for_field(402)
```

#### `get_aip_entry_by_field(field_name: str, use_standardized: bool = True) -> Optional[AIPEntry]`

Get AIP entry by field name.

```python
fuel_entry = airport.get_aip_entry_by_field("Fuel and oil types")
```

#### `get_aip_entries_by_section(section: str) -> List[AIPEntry]`

Get all AIP entries for a specific section.

```python
# Get all administrative entries
admin = airport.get_aip_entries_by_section("admin")

# Get all operational entries
operational = airport.get_aip_entries_by_section("operational")
```

#### `get_standardized_entries() -> List[AIPEntry]`

Get all AIP entries that have been standardized.

```python
standardized = airport.get_standardized_entries()
```

#### `get_unstandardized_entries() -> List[AIPEntry]`

Get all AIP entries that have not been standardized.

```python
unstandardized = airport.get_unstandardized_entries()
```

#### `get_standardized_aip_data() -> Dict[str, str]`

Get standardized AIP data as a dictionary.

```python
aip_dict = airport.get_standardized_aip_data()
# Returns: {"Fuel and oil types": "AVGAS, JET A", ...}
```

#### `has_standardized_field(field_id: int) -> bool`

Check if airport has a standardized field with a non-empty value.

```python
has_fuel_info = airport.has_standardized_field(402)
```

### Model-Level AIP Statistics

#### `get_field_mapping_statistics() -> Dict[str, Any]`

Get statistics about AIP field standardization across all airports.

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

| Attribute | Type | Description | Source |
|-----------|------|-------------|--------|
| `ident` | `str` | ICAO airport code (required) | Direct input |
| `section` | `str` | Section name (required) | One of: 'admin', 'operational', 'handling', 'passenger' |
| `field` | `str` | Original field name (required) | Direct input |
| `value` | `str` | Field value (required) | Direct input |
| `std_field` | `Optional[str]` | Standardized field name | Set by field standardization service |
| `std_field_id` | `Optional[int]` | Standard field ID | Set by field standardization service (e.g., 402 for "Fuel and oil types") |
| `mapping_score` | `Optional[float]` | Similarity score from field mapper | Set by field standardization service (0.0-1.0) |
| `alt_field` | `Optional[str]` | Field name in alternative language | Direct input |
| `alt_value` | `Optional[str]` | Value in alternative language | Direct input |
| `source` | `Optional[str]` | Data source | Direct input (e.g., 'uk_eaip', 'france_eaip') |
| `created_at` | `datetime` | Creation timestamp | Automatically set |

### AIPEntry Methods

#### `is_standardized() -> bool`

Check if this entry has been standardized (has `std_field` and `std_field_id`).

#### `get_effective_field_name() -> str`

Get the standardized field name if available, otherwise the original field name.

#### `to_dict() -> Dict[str, Any]`

Convert entry to dictionary representation.

---

## Querying Runways

Runways are accessed through Airport objects via the `runways` list attribute.

### Accessing Runways

```python
# Get airport
airport = model.airports.where(ident="EGLL").first()

# Access runways
runways = airport.runways

# Filter runways
long_runways = [r for r in airport.runways if r.length_ft and r.length_ft > 8000]
hard_runways = [r for r in airport.runways if r.surface in ["CONCRETE", "ASPHALT"]]
lighted = [r for r in airport.runways if r.lighted]
```

### Finding Airports with Runways

```python
# Airports with any runways
with_runways = model.airports.with_runways().all()

# Airports with hard runways
hard_surface = model.airports.with_hard_runway().all()

# Airports with lighted runways
night_ops = model.airports.with_lighted_runway().all()

# Airports with long runways
jet_capable = model.airports.with_min_runway_length(6000).all()
```

---

## Runway Attributes Reference

### Basic Attributes

| Attribute | Type | Description | Format/Values |
|-----------|------|-------------|---------------|
| `airport_ident` | `str` | ICAO code of the airport (required) | ICAO code (e.g., "EGLL") |
| `length_ft` | `Optional[float]` | Runway length in feet | Float value |
| `width_ft` | `Optional[float]` | Runway width in feet | Float value |
| `surface` | `Optional[str]` | Surface type | Examples: "CONCRETE", "ASPHALT", "GRASS", "DIRT", "WATER", "SNOW" |
| `lighted` | `Optional[bool]` | Has runway lighting | True/False |
| `closed` | `Optional[bool]` | Runway is closed | True/False |
| `created_at` | `datetime` | Creation timestamp | datetime object |

### Low End (LE) Attributes

| Attribute | Type | Description | Format |
|-----------|------|-------------|--------|
| `le_ident` | `Optional[str]` | Low end identifier | Format: "09L", "27R", "24" (runway number + optional letter) |
| `le_latitude_deg` | `Optional[float]` | Low end latitude | Decimal degrees (-90 to +90) |
| `le_longitude_deg` | `Optional[float]` | Low end longitude | Decimal degrees (-180 to +180) |
| `le_elevation_ft` | `Optional[float]` | Low end elevation | Feet (float) |
| `le_heading_degT` | `Optional[float]` | Low end heading (true) | Degrees (0-360, where 0/360 is North) |
| `le_displaced_threshold_ft` | `Optional[float]` | Displaced threshold length | Feet (float) |

### High End (HE) Attributes

| Attribute | Type | Description | Format |
|-----------|------|-------------|--------|
| `he_ident` | `Optional[str]` | High end identifier | Format: "27R", "09L", "06" (opposite end of runway) |
| `he_latitude_deg` | `Optional[float]` | High end latitude | Decimal degrees (-90 to +90) |
| `he_longitude_deg` | `Optional[float]` | High end longitude | Decimal degrees (-180 to +180) |
| `he_elevation_ft` | `Optional[float]` | High end elevation | Feet (float) |
| `he_heading_degT` | `Optional[float]` | High end heading (true) | Degrees (0-360, where 0/360 is North) |
| `he_displaced_threshold_ft` | `Optional[float]` | Displaced threshold length | Feet (float) |

**Note:** Runway identifiers follow the format: runway number (two digits, e.g., "09", "27") + optional letter ("L" for Left, "R" for Right, "C" for Center). Examples: "09L", "27R", "24" (no letter).

---

## Route and Distance Calculations

### Finding Airports Near a Route

#### `find_airports_near_route(route_airports: List[Union[str, NavPoint]], distance_nm: float = 50.0) -> List[Dict[str, Any]]`

Find all airports within a specified distance from a route.

**Parameters:**
- `route_airports: List[Union[str, NavPoint]]` - List of ICAO codes or NavPoint objects defining the route
- `distance_nm: float` - Distance in nautical miles from the route (default: 50.0)

**Returns:**
List of dictionaries with:
```python
{
    'airport': Airport,
    'segment_distance_nm': float,  # Perpendicular distance to route
    'enroute_distance_nm': float,  # Distance along route to closest point
    'closest_segment': Tuple[str, str]  # (start, end) for closest segment
}
```

**Example:**
```python
# Find airports within 50nm of route
route = ["EGLL", "LFPG", "EDDF"]
nearby = model.find_airports_near_route(route, distance_nm=50.0)

# Filter results further
suitable = [
    result for result in nearby
    if result['airport'].has_hard_runway and
       result['segment_distance_nm'] < 25.0
]
```

**Behavior:**
- For single airport: treats it as a point search
- For multiple airports: calculates perpendicular distance to route segments
- Results are sorted by `segment_distance_nm` (closest first)

---

## NavPoint Attributes Reference

| Attribute | Type | Description | Format/Constraints |
|-----------|------|-------------|-------------------|
| `latitude` | `float` | Latitude in decimal degrees (required) | -90 to +90 (negative for South, positive for North) |
| `longitude` | `float` | Longitude in decimal degrees (required) | -180 to +180 (negative for West, positive for East) |
| `name` | `Optional[str]` | Optional identifier for the point | Free text |

### Class Constants

| Constant | Value | Description |
|----------|-------|-------------|
| `EARTH_RADIUS_NM` | `3440.065` | Earth's radius in nautical miles |

### NavPoint Methods

#### `haversine_distance(other: NavPoint) -> Tuple[float, float]`

Calculate bearing and distance to another NavPoint using the Haversine formula.

**Parameters:**
- `other: NavPoint` - Target NavPoint

**Returns:**
- `Tuple[float, float]` - (bearing in degrees, distance in nautical miles)

**Example:**
```python
airport = model.airports.where(ident="EGLL").first()
target = model.airports.where(ident="LFPG").first()

if airport.navpoint and target.navpoint:
    bearing, distance = airport.navpoint.haversine_distance(target.navpoint)
    print(f"Bearing: {bearing}°, Distance: {distance} nm")
```

#### `point_from_bearing_distance(bearing: float, distance: float, name: Optional[str] = None) -> NavPoint`

Create a new NavPoint from this point's position, bearing, and distance.

**Parameters:**
- `bearing: float` - Bearing in degrees (0-360)
- `distance: float` - Distance in nautical miles
- `name: Optional[str]` - Optional name for the new point

**Returns:**
- `NavPoint` - New NavPoint at the calculated position

#### `distance_to_segment(line_start: NavPoint, line_end: NavPoint) -> float`

Compute distance from this point to a line segment.

**Parameters:**
- `line_start: NavPoint` - Start point of the segment
- `line_end: NavPoint` - End point of the segment

**Returns:**
- `float` - Distance in nautical miles

#### `to_dms() -> Tuple[str, str]`

Convert coordinates to Degrees, Minutes, Seconds format.

**Returns:**
- `Tuple[str, str]` - (latitude string, longitude string)
  - Example: ("48° 51' 24\" N", "2° 21' 8\" E")

#### `to_dm() -> Tuple[str, str]`

Convert coordinates to Degrees, Decimal Minutes format.

**Returns:**
- `Tuple[str, str]` - (latitude string, longitude string)
  - Example: ("48° 51.40' N", "2° 21.13' E")

#### `to_csv() -> str`

Convert to CSV format.

**Returns:**
- `str` - Format: "name,description,latitude,longitude"

**Note:** All distance calculations use nautical miles. All bearing calculations use degrees (0-360, where 0/360 is North).

---

## Border Crossing Queries

### Using Collections

The recommended way to query border crossings is through the airport collections:

```python
# All border crossing airports
entry_points = model.airports.border_crossings().all()

# Border crossings in France
french_entry = model.airports.border_crossings().by_country("FR").all()

# Border crossings with ILS
ils_entry = model.airports.border_crossings() \
                          .with_approach_type("ILS") \
                          .all()

# Count border crossings
count = model.airports.border_crossings().count()

# Check if specific airport is a border crossing
egll = model.airports.where(ident="EGLL").first()
is_entry_point = egll.point_of_entry if egll else False
```

### Legacy Border Crossing Methods

These methods are still available for backward compatibility:

#### `get_border_crossing_points_by_country(country_iso: str) -> List[BorderCrossingEntry]`

Get raw border crossing entries for a country.

#### `get_border_crossing_entry(country_iso: str, icao_code: str) -> Optional[BorderCrossingEntry]`

Get a specific border crossing entry.

#### `get_all_border_crossing_points() -> List[BorderCrossingEntry]`

Get all border crossing entries.

#### `get_border_crossing_countries() -> List[str]`

Get list of countries with border crossing entries.

#### `get_border_crossing_statistics() -> Dict[str, Any]`

Get statistics about border crossing entries.

**Returns:**
```python
{
    'total_entries': int,
    'countries_count': int,
    'matched_count': int,
    'unmatched_count': int,
    'match_rate': float,
    'by_source': Dict[str, int],
    'by_country': Dict[str, int]
}
```

---

## BorderCrossingEntry Attributes Reference

| Attribute | Type | Description | Source |
|-----------|------|-------------|--------|
| `airport_name` | `str` | Name of the airport (required) | Direct input |
| `country_iso` | `str` | ISO country code (required) | Direct input |
| `icao_code` | `Optional[str]` | ICAO code if available | Direct input or matching |
| `is_airport` | `Optional[bool]` | Whether this is an airport | Direct input |
| `source` | `Optional[str]` | Data source | Direct input |
| `extraction_method` | `Optional[str]` | Extraction method used | Direct input |
| `metadata` | `Optional[Dict[str, Any]]` | Additional metadata | Direct input |
| `matched_airport_icao` | `Optional[str]` | ICAO of matched airport | Set by matching process |
| `match_score` | `Optional[float]` | Fuzzy match score | Set by matching process (0.0-1.0) |
| `created_at` | `datetime` | Creation timestamp | Automatically set |
| `updated_at` | `datetime` | Last update timestamp | Automatically set |

### BorderCrossingEntry Methods

#### `merge_with(other: BorderCrossingEntry) -> BorderCrossingEntry`

Merge this entry with another, combining information intelligently.

#### `is_more_complete_than(other: BorderCrossingEntry) -> bool`

Check if this entry is more complete than another.

---

## Statistics and Metadata

### Model Statistics

#### `get_statistics() -> Dict[str, Any]`

Get comprehensive statistics about the model.

**Returns:**
```python
{
    'total_airports': int,
    'airports_with_runways': int,
    'airports_with_procedures': int,
    'airports_with_aip_data': int,
    'airports_with_border_crossing': int,
    'total_runways': int,
    'total_procedures': int,
    'total_aip_entries': int,
    'total_border_crossing_points': int,
    'procedure_types': Dict[str, int],
    'border_crossing': Dict[str, Any],
    'sources_used': List[str],
    'created_at': str,
    'updated_at': str
}
```

**Example:**
```python
stats = model.get_statistics()
print(f"Total airports: {stats['total_airports']}")
print(f"With procedures: {stats['airports_with_procedures']}")
print(f"Border crossings: {stats['airports_with_border_crossing']}")
```

---

## Common Patterns

### Pattern 1: Dict-Style Lookups

For simple ICAO code lookups, use dict-style access:

```python
# Get single airport by ICAO (most concise)
heathrow = model.airports['EGLL']
cdg = model.airports['LFPG']

# Check if airport exists
if 'EGLL' in model.airports:
    heathrow = model.airports['EGLL']
    print(f"Found {heathrow.name}")

# Safe lookup with default
airport = model.airports.get('ZZZZ')  # Returns None if not found
airport = model.airports.get('ZZZZ', default=None)

# Works on filtered collections too
french = model.airports.by_country("FR")
if 'LFPG' in french:
    cdg = french['LFPG']
```

### Pattern 2: Progressive Filtering

Start broad, then narrow down:

```python
# Start with all airports
airports = model.airports

# Add filters progressively
airports = airports.by_country("FR")
airports = airports.with_hard_runway()
airports = airports.with_min_runway_length(3000)
airports = airports.with_approach_type("ILS")

# Execute query
results = airports.all()
```

### Pattern 3: Method Chaining

Chain filters in a fluent style:

```python
suitable = model.airports \
    .by_country("FR") \
    .with_hard_runway() \
    .with_min_runway_length(3000) \
    .with_fuel(avgas=True, jet_a=True) \
    .with_approach_type("ILS") \
    .all()
```

### Pattern 4: Set Operations for OR Logic

Use union operator for clean OR queries:

```python
# Multiple countries (OR logic)
western_europe = (
    model.airports.by_country("FR") |
    model.airports.by_country("DE") |
    model.airports.by_country("BE") |
    model.airports.by_country("NL")
)

# Complex OR with filters
premium_or_busy = (
    model.airports.with_fuel(avgas=True, jet_a=True) |
    model.airports.with_scheduled_service()
)
```

### Pattern 5: Set Operations for AND/Exclusion

Use intersection and difference for complex logic:

```python
# AND logic - must meet ALL criteria
premium_french = (
    model.airports.by_country("FR") &
    model.airports.with_hard_runway() &
    model.airports.with_fuel(avgas=True, jet_a=True)
)

# Exclusion - remove unwanted items
suitable = (
    model.airports.with_runways() -
    model.airports.filter(lambda a: a.longest_runway_length_ft < 3000) -
    model.airports.filter(lambda a: a.has_water_runway)
)

# Complex: (FR OR DE) AND hard_runway - procedures
result = (
    (model.airports.by_country("FR") | model.airports.by_country("DE")) &
    model.airports.with_hard_runway()
) - model.airports.with_procedures()
```

### Pattern 6: Combining Domain and Custom Filters

Use domain methods for common cases, custom filters for specific logic:

```python
complex = model.airports \
    .by_countries(["FR", "DE", "BE"]) \
    .with_procedures() \
    .filter(lambda a:
        a.has_hard_runway and
        a.longest_runway_length_ft and
        a.longest_runway_length_ft > 4000 and
        len(a.procedures) > 5
    ).all()
```

### Pattern 7: Pagination

Use `skip()` and `take()` for pagination:

```python
# Page 1 (0-9)
page1 = model.airports.take(10).all()

# Page 2 (10-19)
page2 = model.airports.skip(10).take(10).all()

# Page 3 (20-29)
page3 = model.airports.skip(20).take(10).all()
```

### Pattern 8: Grouping and Analysis

Use grouping for analysis:

```python
# Airports by country
by_country = model.airports.with_procedures().group_by_country()

# Analyze each country
for country, airports in by_country.items():
    print(f"{country}: {len(airports)} airports with procedures")

# Procedures by type
by_type = model.procedures.approaches().group_by_approach_type()
for approach_type, procs in by_type.items():
    print(f"{approach_type}: {len(procs)} procedures")
```

### Pattern 9: Direct Iteration

Iterate without calling `.all()`:

```python
# No need for .all() when iterating
for airport in model.airports.by_country("FR").with_procedures():
    print(f"{airport.ident}: {len(airport.procedures)} procedures")

# List comprehension
names = [a.name for a in model.airports.with_runways()]
```

### Pattern 10: Reverse Iteration

Iterate in reverse order:

```python
# Reverse iteration with reversed()
for airport in reversed(model.airports.order_by('name')):
    print(airport.name)  # Z to A

# Get last N items
last_five = list(reversed(model.airports.take(5)))

# Reverse after filtering
recent_procedures = model.procedures \
    .approaches() \
    .order_by(lambda p: p.name)

for proc in reversed(recent_procedures):
    print(proc.name)  # Reverse alphabetical
```

### Pattern 11: Existence Checks

Use `.exists()` and `.count()` for efficient checks:

```python
# Check if any exist
has_french = model.airports.by_country("FR").exists()

# Count without loading all
french_count = model.airports.by_country("FR").count()

# Conditional logic
if model.airports.with_approach_type("ILS").exists():
    ils_airports = model.airports.with_approach_type("ILS").all()
```

### Pattern 8: Airport-Level Procedure Queries

Query procedures at the airport level:

```python
# Get airport
heathrow = model.airports.where(ident="EGLL").first()

# Query its procedures
all_procs = heathrow.procedures_query.all()
approaches = heathrow.procedures_query.approaches().all()
ils = heathrow.procedures_query.approaches().by_type("ILS").all()

# Most precise approach for runway
best_09l = heathrow.procedures_query \
    .approaches() \
    .by_runway("09L") \
    .most_precise()
```

### Pattern 9: Sorting and Ranking

Sort collections before retrieving:

```python
# Longest runways first
by_runway = model.airports \
    .with_runways() \
    .order_by(lambda a: a.longest_runway_length_ft or 0, reverse=True) \
    .all()

# Alphabetically by name
by_name = model.airports \
    .by_country("FR") \
    .order_by(lambda a: a.name or '') \
    .all()
```

### Pattern 10: Complex Queries

Combine everything for sophisticated queries:

```python
# Find best alternates for EGLL within 100nm
primary = model.airports.where(ident="EGLL").first()

alternates = model.airports \
    .by_country("GB") \
    .with_hard_runway() \
    .with_min_runway_length(5000) \
    .with_approach_type("ILS") \
    .filter(lambda a:
        a.ident != "EGLL" and
        a.navpoint and
        primary.navpoint and
        primary.navpoint.haversine_distance(a.navpoint)[1] <= 100
    ) \
    .order_by(lambda a:
        primary.navpoint.haversine_distance(a.navpoint)[1]
    ) \
    .take(5) \
    .all()
```

---

## Summary

The modern query API provides:

- **Collections** - Two main entry points: `model.airports` and `model.procedures`
- **Chainable Filters** - Compose queries naturally with method chaining
- **Domain Methods** - Specialized filters like `.by_country()`, `.with_runways()`
- **Custom Filters** - Generic `.filter()` and `.where()` for any logic
- **Terminal Operations** - `.all()`, `.first()`, `.count()`, `.exists()`
- **Iteration Support** - Direct iteration without `.all()`
- **Grouping** - `.group_by()` for analysis
- **Sorting** - `.order_by()` for ordering
- **Pagination** - `.skip()` and `.take()` for paging

All queries are composable, type-safe, and support IDE autocomplete for a superior development experience.
