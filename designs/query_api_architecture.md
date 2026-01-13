# Euro AIP Query API - Architecture & Patterns

**Purpose:** Understand design philosophy, patterns, and conventions before implementing new features.

---

## Design Philosophy

The Query API follows these principles:

1. **Fluent & Chainable** - All filter methods return new collections, enabling method chaining
2. **Immutable** - Filtering creates new collections; originals are never modified
3. **Lazy-ish** - Collections wrap lists; terminal operations (`.all()`, `.first()`) execute
4. **Pythonic** - Supports iteration, indexing, slicing, `in` operator, `len()`, `reversed()`
5. **Composable** - Set operations (`|`, `&`, `-`) combine collections cleanly

---

## Class Hierarchy

```
QueryableCollection[T]          # Base class - generic filtering/grouping
    ├── AirportCollection       # Domain methods: by_country(), with_runways(), etc.
    └── ProcedureCollection     # Domain methods: approaches(), by_type(), etc.
```

**Key files:**
- `euro_aip/models/queryable_collection.py` - Base class
- `euro_aip/models/airport_collection.py` - Airport-specific filters
- `euro_aip/models/procedure_collection.py` - Procedure-specific filters

---

## Naming Conventions

### Filter Methods

| Prefix | Meaning | Examples |
|--------|---------|----------|
| `by_*` | Filter by exact attribute match | `by_country("FR")`, `by_type("ILS")`, `by_runway("09L")` |
| `with_*` | Filter by presence/capability | `with_runways()`, `with_fuel(avgas=True)`, `with_procedures()` |
| `in_*` | Filter by containment | `in_region("GB-ENG")` |

### Terminal Operations

| Method | Returns | Use When |
|--------|---------|----------|
| `.all()` | `List[T]` | Need all items as list |
| `.first()` | `Optional[T]` | Need single item or None |
| `.count()` | `int` | Need count without loading all |
| `.exists()` | `bool` | Check if any match |

### Grouping Methods

| Method | Returns | Example |
|--------|---------|---------|
| `group_by(fn)` | `Dict[str, List[T]]` | Custom grouping |
| `group_by_country()` | `Dict[str, List[Airport]]` | Pre-built country grouping |
| `group_by_type()` | `Dict[str, List[Procedure]]` | Pre-built type grouping |

---

## Adding New Features

### Adding a New Filter to AirportCollection

1. **Choose the right prefix** based on naming conventions above
2. **Return a new AirportCollection** - never mutate
3. **Handle None values** gracefully in predicates

```python
# Example: Adding with_customs() filter
def with_customs(self) -> 'AirportCollection':
    """Filter to airports with customs facilities."""
    return AirportCollection([
        a for a in self._items
        if a.has_customs  # Assumes has_customs attribute exists
    ])
```

### Adding a New Filter to ProcedureCollection

Same pattern - return new ProcedureCollection:

```python
def by_minimum_altitude(self, min_alt_ft: int) -> 'ProcedureCollection':
    """Filter procedures by minimum altitude."""
    return ProcedureCollection([
        p for p in self._items
        if p.minimum_altitude and p.minimum_altitude >= min_alt_ft
    ])
```

### Adding a New Grouping Method

Use the base `group_by()` method:

```python
def group_by_fuel_type(self) -> dict:
    """Group airports by available fuel type."""
    return self.group_by(lambda a:
        'both' if a.avgas and a.jet_a else
        'avgas' if a.avgas else
        'jet_a' if a.jet_a else
        'none'
    )
```

---

## Extending with New Entity Collections

To add a new collection type (e.g., `RunwayCollection`):

1. **Create class extending QueryableCollection**
2. **Add domain-specific filter methods** following naming conventions
3. **Override `__getitem__` if dict-style access makes sense**

```python
class RunwayCollection(QueryableCollection['Runway']):
    """Collection for querying runways."""

    def by_surface(self, surface: str) -> 'RunwayCollection':
        return RunwayCollection([
            r for r in self._items
            if r.surface and r.surface.upper() == surface.upper()
        ])

    def with_lighting(self) -> 'RunwayCollection':
        return RunwayCollection([
            r for r in self._items if r.lighted
        ])

    def with_min_length(self, min_ft: int) -> 'RunwayCollection':
        return RunwayCollection([
            r for r in self._items
            if r.length_ft and r.length_ft >= min_ft
        ])
```

---

## Set Operations Pattern

Collections support `|`, `&`, `-` for combining queries:

```python
# OR logic - union
french_or_german = airports.by_country("FR") | airports.by_country("DE")

# AND logic - intersection
premium = airports.with_hard_runway() & airports.with_fuel(avgas=True, jet_a=True)

# Exclusion - difference
no_procedures = airports.with_runways() - airports.with_procedures()
```

**Implementation note:** Set operations use `id()` for identity comparison, not value equality.

---

## Entry Points

The model provides two main collection entry points:

```python
model = EuroAipModel.from_file("data/euro_aip.json")

model.airports      # → AirportCollection (all airports)
model.procedures    # → ProcedureCollection (all procedures across all airports)
```

Individual airports provide procedure access:

```python
airport = model.airports['EGLL']
airport.procedures_query  # → ProcedureCollection (this airport's procedures)
```

---

## Key Patterns to Follow

### Pattern 1: Always Return New Collection
```python
# CORRECT
def by_country(self, code: str) -> 'AirportCollection':
    return AirportCollection([a for a in self._items if a.iso_country == code])

# WRONG - mutates in place
def by_country(self, code: str) -> 'AirportCollection':
    self._items = [a for a in self._items if a.iso_country == code]
    return self
```

### Pattern 2: Handle None Safely
```python
# CORRECT
def with_min_runway_length(self, min_ft: int) -> 'AirportCollection':
    return AirportCollection([
        a for a in self._items
        if a.longest_runway_length_ft and a.longest_runway_length_ft >= min_ft
    ])

# WRONG - crashes on None
def with_min_runway_length(self, min_ft: int) -> 'AirportCollection':
    return AirportCollection([
        a for a in self._items if a.longest_runway_length_ft >= min_ft
    ])
```

### Pattern 3: Case-Insensitive String Matching
```python
def by_type(self, approach_type: str) -> 'ProcedureCollection':
    approach_upper = approach_type.upper()  # Normalize once
    return ProcedureCollection([
        p for p in self._items
        if p.approach_type and p.approach_type.upper() == approach_upper
    ])
```

### Pattern 4: Boolean Flag Parameters
```python
def with_fuel(self, avgas: bool = False, jet_a: bool = False) -> 'AirportCollection':
    result = list(self._items)
    if avgas:
        result = [a for a in result if a.avgas]
    if jet_a:
        result = [a for a in result if a.jet_a]
    return AirportCollection(result)
```

---

## Testing New Features

When adding new filters, test:

1. **Empty collection** - should return empty, not crash
2. **None values** - should be handled gracefully
3. **Chaining** - should work with other filters
4. **Set operations** - should work with `|`, `&`, `-`

```python
def test_with_customs():
    # Empty collection
    empty = AirportCollection([])
    assert empty.with_customs().count() == 0

    # Chaining
    result = airports.by_country("FR").with_customs().with_hard_runway()
    assert all(a.iso_country == "FR" for a in result)

    # Set operations
    combined = airports.with_customs() | airports.border_crossings()
    assert combined.count() >= airports.with_customs().count()
```
