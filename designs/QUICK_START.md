# Euro AIP Modern Query API - Quick Start

**Get started with the new queryable collections in 5 minutes**

---

## Installation

```bash
pip install --upgrade euro-aip
```

---

## The Basics

### Load Your Model

```python
from euro_aip.models import EuroAipModel

# Load your data
model = EuroAipModel.from_file("data/euro_aip.json")
# or however you load your model
```

### Two Main Entry Points

```python
model.airports    # AirportCollection - query airports
model.procedures  # ProcedureCollection - query procedures
```

---

## Common Patterns

### 1. Find Airports

```python
# By country
french_airports = model.airports.by_country("FR").all()

# By multiple countries
schengen = model.airports.by_countries(["FR", "DE", "ES", "IT"]).all()

# With runways
with_runways = model.airports.with_runways().all()

# With hard surface
paved = model.airports.with_hard_runway().all()

# Minimum runway length
jet_capable = model.airports.with_min_runway_length(5000).all()
```

### 2. Chain Filters

```python
# Find suitable airports for a mission
suitable = model.airports.by_country("FR") \
                         .with_hard_runway() \
                         .with_fuel(avgas=True, jet_a=True) \
                         .with_min_runway_length(3000) \
                         .with_procedures("approach") \
                         .all()
```

### 3. Query Procedures

```python
# All ILS approaches
ils_approaches = model.procedures.approaches().by_type("ILS").all()

# Procedures for a specific runway
rwy_09l = model.procedures.by_runway("09L").all()

# Chain them
ils_09l = model.procedures.approaches() \
                          .by_type("ILS") \
                          .by_runway("09L") \
                          .all()
```

### 4. Airport-Level Queries

```python
# Get an airport
heathrow = model.airports.where(ident="EGLL").first()

# Query its procedures
approaches = heathrow.procedures_query.approaches().all()
ils = heathrow.procedures_query.approaches().by_type("ILS").all()

# Get most precise approach for a runway
best = heathrow.procedures_query.approaches() \
                                .by_runway("09L") \
                                .most_precise()
```

### 5. Custom Filters

```python
# Use lambda for complex logic
long_runways = model.airports.filter(
    lambda a: a.longest_runway_length_ft and a.longest_runway_length_ft > 5000
).all()

# Combine with domain filters
complex = model.airports.by_country("GB") \
                        .with_procedures() \
                        .filter(lambda a: len(a.procedures) > 10) \
                        .all()
```

---

## Useful Methods

### Terminal Operations

```python
collection.all()        # Get all items as list
collection.first()      # Get first item or None
collection.count()      # Count items
collection.exists()     # Check if any items exist
```

### Grouping and Sorting

```python
# Group airports by country
by_country = model.airports.group_by_country()
french = by_country["FR"]

# Sort
sorted_airports = model.airports.order_by(lambda a: a.name or '').all()

# Take first N
top_10 = model.airports.order_by(lambda a: a.longest_runway_length_ft or 0, reverse=True).take(10).all()
```

### Iteration

```python
# You can iterate directly (no need for .all())
for airport in model.airports.by_country("FR"):
    print(f"{airport.ident}: {airport.name}")

# Or get as list
french_list = model.airports.by_country("FR").all()
```

---

## Quick Examples

### Example 1: Find Border Crossings with ILS

```python
entry_points = model.airports.border_crossings() \
                             .with_approach_type("ILS") \
                             .all()

for airport in entry_points:
    print(f"{airport.ident} - {airport.name}")
```

### Example 2: Find Suitable Alternates

```python
# Primary airport
primary = model.airports.where(ident="EGLL").first()

# Find nearby suitable alternates
alternates = model.airports.by_country("GB") \
                           .with_hard_runway() \
                           .with_min_runway_length(3000) \
                           .with_approach_type("ILS") \
                           .filter(lambda a: a.ident != "EGLL") \
                           .all()
```

### Example 3: Analyze Coverage

```python
# Count airports with ILS by country
for country in ["FR", "DE", "GB"]:
    total = model.airports.by_country(country).count()
    with_ils = model.airports.by_country(country).with_approach_type("ILS").count()

    print(f"{country}: {with_ils}/{total} ({100*with_ils/total:.1f}%)")
```

### Example 4: Group Procedures by Type

```python
# Get airport
heathrow = model.airports.where(ident="EGLL").first()

# Group procedures by type
by_type = heathrow.procedures_query.group_by_type()

print(f"Approaches: {len(by_type.get('approach', []))}")
print(f"Departures: {len(by_type.get('departure', []))}")
print(f"Arrivals: {len(by_type.get('arrival', []))}")
```

---

## Migrating from Old API

### Simple Replacements

| Old | New |
|-----|-----|
| `model.get_airport(icao)` | `model.airports.where(ident=icao).first()` |
| `model.get_airports_by_country(code)` | `model.airports.by_country(code).all()` |
| `model.get_airports_with_runways()` | `model.airports.with_runways().all()` |
| `airport.get_approaches()` | `airport.procedures_query.approaches().all()` |

### Before/After Examples

**Before:**
```python
french = model.get_airports_by_country("FR")
suitable = [a for a in french
            if a.has_hard_runway and
               a.longest_runway_length_ft and
               a.longest_runway_length_ft > 3000]
```

**After:**
```python
suitable = model.airports.by_country("FR") \
                         .with_hard_runway() \
                         .with_min_runway_length(3000) \
                         .all()
```

---

## Need More?

- **Complete Guide:** [modern_query_api_guide.md](modern_query_api_guide.md)
- **Migration Help:** [migration_guide.md](migration_guide.md)
- **Full Summary:** [REFACTORING_SUMMARY.md](REFACTORING_SUMMARY.md)

---

## Tips

1. **Chain naturally** - Filters combine with AND logic
2. **Use domain methods** - More readable than lambdas
3. **Terminal operations** - Remember `.all()`, `.first()`, `.count()`
4. **Iterate directly** - No need for `.all()` if just looping
5. **Type hints help** - Your IDE will autocomplete

---

## That's It!

You're ready to use the modern query API. Start with simple queries and gradually explore more advanced features.

Happy querying! ✈️
