# Euro AIP Query API - Quick Reference

**Purpose:** Compact method reference for quick syntax lookup.

---

## Setup

```python
from euro_aip.storage.database_storage import DatabaseStorage

storage = DatabaseStorage("data/airports.db")
model = storage.load_model()
```

---

## Airports

### Access
```python
model.airports                    # All airports → AirportCollection
model.airports['EGLL']            # By ICAO → Airport (raises KeyError if missing)
model.airports.get('EGLL')        # By ICAO → Airport or None
'EGLL' in model.airports          # Check exists → bool
```

### Filter by Location
```python
.by_country("FR")                 # Single country
.by_countries(["FR", "DE", "BE"]) # Multiple countries
.by_continent("EU")               # Continent code
.in_region("GB-ENG")              # ISO region
.with_coordinates()               # Has lat/lon
```

### Filter by Capabilities
```python
.with_runways()                   # Has runway data
.with_hard_runway()               # Paved runway (concrete/asphalt)
.with_soft_runway()               # Grass/dirt runway
.with_water_runway()              # Seaplane base
.with_lighted_runway()            # Night operations capable
.with_min_runway_length(5000)     # Min runway length in feet
```

### Filter by Services
```python
.with_fuel(avgas=True)            # Has AVGAS
.with_fuel(jet_a=True)            # Has Jet A
.with_fuel(avgas=True, jet_a=True) # Has both
.with_scheduled_service()         # Commercial airline service
.border_crossings()               # Official border crossing points
```

### Filter by Data
```python
.with_procedures()                # Has any procedures
.with_procedures("approach")      # Has approach procedures
.with_approach_type("ILS")        # Has ILS approaches
.with_aip_data()                  # Has AIP entries
.with_standardized_aip_data()     # Has standardized AIP
.by_source("uk_eaip")             # From specific data source
.by_sources(["uk_eaip", "france_eaip"])
```

### Grouping
```python
.group_by_country()               # → Dict[str, List[Airport]]
.group_by_continent()             # → Dict[str, List[Airport]]
.group_by_source()                # → Dict[str, List[Airport]]
.group_by_region()                # → Dict[str, List[Airport]]
```

---

## Procedures

### Access
```python
model.procedures                  # All procedures → ProcedureCollection
airport.procedures_query          # Airport's procedures → ProcedureCollection
```

### Filter by Type
```python
.approaches()                     # Approach procedures only
.departures()                     # SIDs only
.arrivals()                       # STARs only
.by_type("ILS")                   # Specific approach type
```

### Filter by Precision
```python
.precision_approaches()           # ILS only
.rnp_approaches()                 # RNP/RNAV only
.non_precision_approaches()       # VOR, NDB, LOC, etc.
.with_precision_better_than("VOR") # More precise than VOR
.by_precision_order()             # Sort by precision (best first)
.most_precise()                   # → single Procedure or None
```

### Filter by Runway/Source
```python
.by_runway("09L")                 # By runway identifier
.for_runway(runway_obj)           # By Runway object (matches either end)
.by_source("uk_eaip")             # From specific source
.by_authority("EGC")              # By authority code
```

### Grouping
```python
.group_by_runway()                # → Dict[str, List[Procedure]]
.group_by_type()                  # → Dict[str, List[Procedure]]
.group_by_approach_type()         # → Dict[str, List[Procedure]]
.group_by_source()                # → Dict[str, List[Procedure]]
```

---

## Terminal Operations

```python
.all()                            # → List[T]
.first()                          # → T or None
.last()                           # → T or None
.count()                          # → int
.exists()                         # → bool
.is_empty()                       # → bool
```

---

## Generic Methods (All Collections)

```python
.filter(lambda x: x.value > 10)   # Custom predicate
.where(ident="EGLL", iso_country="GB")  # Attribute match (AND)
.order_by(lambda x: x.name)       # Sort ascending
.order_by(lambda x: x.name, reverse=True)  # Sort descending
.take(10)                         # First N items
.skip(10)                         # Skip N items
.distinct_by(lambda x: x.country) # Remove duplicates by key
.map(lambda x: x.ident)           # Transform items
.to_dict(lambda x: x.ident)       # → Dict[key, T]
.group_by(lambda x: x.country)    # → Dict[key, List[T]]
```

---

## Set Operations

```python
# Union (OR) - items in either
airports.by_country("FR") | airports.by_country("DE")

# Intersection (AND) - items in both
airports.with_hard_runway() & airports.with_fuel(avgas=True)

# Difference (EXCLUDE) - items in first but not second
airports.with_runways() - airports.with_procedures()
```

---

## Iteration & Indexing

```python
for airport in model.airports.by_country("FR"):  # Direct iteration
    print(airport.name)

len(model.airports)               # Count
model.airports[0]                 # First item
model.airports[-1]                # Last item
model.airports[0:10]              # Slice → new collection
reversed(model.airports)          # Reverse iteration
```

---

## Common Patterns

### Find airport by ICAO
```python
airport = model.airports['EGLL']
# or safely:
airport = model.airports.get('EGLL')
```

### French airports with ILS and long runways
```python
result = model.airports \
    .by_country("FR") \
    .with_approach_type("ILS") \
    .with_min_runway_length(5000) \
    .all()
```

### Most precise approach for runway
```python
best = airport.procedures_query \
    .approaches() \
    .by_runway("09L") \
    .most_precise()
```

### Airports from multiple countries with hard runways
```python
result = (
    model.airports.by_country("FR") |
    model.airports.by_country("DE") |
    model.airports.by_country("BE")
) & model.airports.with_hard_runway()
```

### Count by country
```python
by_country = model.airports.with_procedures().group_by_country()
for country, airports in by_country.items():
    print(f"{country}: {len(airports)}")
```

---

## Airport Key Attributes

| Attribute | Type | Description |
|-----------|------|-------------|
| `ident` | `str` | ICAO code |
| `name` | `str?` | Airport name |
| `iso_country` | `str?` | Country code |
| `latitude_deg` | `float?` | Latitude |
| `longitude_deg` | `float?` | Longitude |
| `elevation_ft` | `str?` | Elevation |
| `has_hard_runway` | `bool?` | Has paved runway |
| `longest_runway_length_ft` | `int?` | Longest runway |
| `avgas` | `bool?` | Has AVGAS |
| `jet_a` | `bool?` | Has Jet A |
| `point_of_entry` | `bool?` | Border crossing |
| `runways` | `List[Runway]` | Runway list |
| `procedures` | `List[Procedure]` | Procedure list |
| `aip_entries` | `List[AIPEntry]` | AIP data |
| `sources` | `Set[str]` | Data sources |
| `navpoint` | `NavPoint?` | For distance calc |
| `procedures_query` | `ProcedureCollection` | Queryable procedures |

---

## Procedure Key Attributes

| Attribute | Type | Description |
|-----------|------|-------------|
| `airport_ident` | `str` | ICAO code |
| `name` | `str` | Procedure name |
| `procedure_type` | `str` | 'approach', 'departure', 'arrival' |
| `approach_type` | `str?` | 'ILS', 'RNAV', 'VOR', etc. |
| `runway_ident` | `str?` | Runway identifier |
| `source` | `str?` | Data source |
| `authority` | `str?` | Authority code |

---

## Runway Key Attributes

| Attribute | Type | Description |
|-----------|------|-------------|
| `airport_ident` | `str` | ICAO code |
| `le_ident` | `str?` | Low end identifier |
| `he_ident` | `str?` | High end identifier |
| `length_ft` | `float?` | Length in feet |
| `width_ft` | `float?` | Width in feet |
| `surface` | `str?` | Surface type |
| `lighted` | `bool?` | Has lighting |
| `closed` | `bool?` | Is closed |

---

## Precision Hierarchy

Most precise to least: **ILS > RNP > RNAV > VOR > NDB > LOC > LDA > SDF**
