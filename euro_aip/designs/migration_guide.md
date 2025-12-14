# Euro AIP Query API Migration Guide

**From Legacy Methods to Modern Collections**

Version: 2.0
Last Updated: December 2025

---

## Table of Contents

1. [Overview](#overview)
2. [Quick Reference](#quick-reference)
3. [Step-by-Step Migration](#step-by-step-migration)
4. [Common Patterns](#common-patterns)
5. [Automated Migration Tool](#automated-migration-tool)
6. [Testing Your Migration](#testing-your-migration)
7. [Troubleshooting](#troubleshooting)

---

## Overview

The Euro AIP library has been refactored to use a modern **queryable collection API** that provides:

- **Better composability** - Chain filters naturally
- **Consistent patterns** - Same approach for all queries
- **Type safety** - Full IDE autocomplete support
- **Less code** - Eliminate manual list comprehensions
- **Better performance** - Optimized query execution

### What Changed?

**Before:**
```python
# Multiple specific methods
model.get_airport(icao)
model.get_airports_by_country(country_code)
model.get_airports_with_procedures(procedure_type)
model.get_airports_with_runways()

# Manual filtering
french = model.get_airports_by_country("FR")
with_ils = [a for a in french if any(p.approach_type == "ILS" for p in a.procedures)]
```

**After:**
```python
# Unified collection API
model.airports.where(ident=icao).first()
model.airports.by_country(country_code).all()
model.airports.with_procedures(procedure_type).all()
model.airports.with_runways().all()

# Composable filters
with_ils = model.airports.by_country("FR").with_approach_type("ILS").all()
```

### Backward Compatibility

**All legacy methods still work** with deprecation warnings. You can migrate incrementally:

1. Run your existing code (warnings will appear)
2. Migrate one module at a time
3. Test thoroughly
4. Remove legacy method calls

---

## Quick Reference

### Airport Queries

| Legacy Method | Modern Equivalent | Notes |
|--------------|-------------------|-------|
| `model.get_airport(icao)` | `model.airports.where(ident=icao).first()` | Returns Optional[Airport] |
| `model.get_airports_by_country(code)` | `model.airports.by_country(code).all()` | Returns List[Airport] |
| `model.get_airports_by_source(src)` | `model.airports.by_source(src).all()` | |
| `model.get_airports_with_runways()` | `model.airports.with_runways().all()` | |
| `model.get_airports_with_procedures()` | `model.airports.with_procedures().all()` | |
| `model.get_airports_with_procedures("approach")` | `model.airports.with_procedures("approach").all()` | |
| `model.get_airports_with_aip_data()` | `model.airports.with_aip_data().all()` | |
| `model.get_airports_with_standardized_aip_data()` | `model.airports.with_standardized_aip_data().all()` | |

### Procedure Queries

| Legacy Method | Modern Equivalent | Notes |
|--------------|-------------------|-------|
| `model.get_all_approaches()` | `model.procedures.approaches().group_by(lambda p: ...)` | Returns Dict |
| `model.get_all_departures()` | `model.procedures.departures().all()` | Returns List |
| `model.get_approaches_by_runway(icao, rwy)` | See below | More flexible now |
| `airport.get_approaches()` | `airport.procedures_query.approaches().all()` | |
| `airport.get_most_precise_approach_for_runway(rwy)` | `airport.procedures_query.approaches().for_runway(rwy).most_precise()` | |

### Border Crossing Queries

| Legacy Method | Modern Equivalent | Notes |
|--------------|-------------------|-------|
| `model.get_border_crossing_airports()` | `model.airports.border_crossings().all()` | Cleaner! |

---

## Step-by-Step Migration

### Step 1: Install Updated Library

```bash
pip install --upgrade euro-aip
```

### Step 2: Run Your Tests

Run your existing test suite. You should see deprecation warnings but no failures:

```bash
pytest -v
```

Example warning:
```
DeprecationWarning: get_airports_by_country() is deprecated.
Use model.airports.by_country(code).all() instead.
```

### Step 3: Identify Usage Patterns

Search your codebase for legacy method calls:

```bash
# Find all legacy method calls
grep -r "get_airport\|get_airports_by\|get_airports_with" your_project/

# Count occurrences
grep -r "get_airports_by_country" your_project/ | wc -l
```

### Step 4: Migrate Module by Module

Start with the simplest cases:

#### Simple 1:1 Replacements

**Before:**
```python
def get_french_airports(model):
    return model.get_airports_by_country("FR")
```

**After:**
```python
def get_french_airports(model):
    return model.airports.by_country("FR").all()
```

#### Chained Filters

**Before:**
```python
def find_suitable_airports(model, country_code):
    airports = model.get_airports_by_country(country_code)
    with_runways = [a for a in airports if a.runways]
    with_hard = [a for a in with_runways if a.has_hard_runway]
    return [a for a in with_hard
            if a.longest_runway_length_ft and a.longest_runway_length_ft > 3000]
```

**After:**
```python
def find_suitable_airports(model, country_code):
    return model.airports.by_country(country_code) \
                         .with_runways() \
                         .with_hard_runway() \
                         .with_min_runway_length(3000) \
                         .all()
```

### Step 5: Test Each Migration

After migrating each module, run tests:

```bash
pytest tests/test_your_module.py -v
```

### Step 6: Enable Warnings as Errors (Optional)

Force migration by treating warnings as errors:

```python
import warnings
warnings.filterwarnings("error", category=DeprecationWarning)
```

---

## Common Patterns

### Pattern 1: Single Airport Lookup

**Before:**
```python
airport = model.get_airport("EGLL")
if airport:
    print(f"Found: {airport.name}")
```

**After:**
```python
airport = model.airports.where(ident="EGLL").first()
if airport:
    print(f"Found: {airport.name}")
```

**Or use dict access (internal only):**
```python
# If you absolutely need dict access
airport = model._airports.get("EGLL")
```

### Pattern 2: Country-Based Queries

**Before:**
```python
french_airports = model.get_airports_by_country("FR")
uk_airports = model.get_airports_by_country("GB")
all_airports = french_airports + uk_airports
```

**After:**
```python
all_airports = model.airports.by_countries(["FR", "GB"]).all()
```

### Pattern 3: Filtering with Conditions

**Before:**
```python
airports = model.get_airports_with_runways()
long_runways = [a for a in airports
                if a.longest_runway_length_ft and
                   a.longest_runway_length_ft > 5000]
```

**After:**
```python
long_runways = model.airports.with_min_runway_length(5000).all()
```

### Pattern 4: Complex Multi-Stage Filtering

**Before:**
```python
# Get French airports
french = model.get_airports_by_country("FR")

# Filter for those with runways
with_runways = [a for a in french if a.runways]

# Filter for hard surface
with_hard = [a for a in with_runways if a.has_hard_runway]

# Filter for ILS
with_ils = [a for a in with_hard
            if any(p.approach_type == "ILS" for p in a.procedures)]

# Filter for fuel
result = [a for a in with_ils if a.avgas and a.jet_a]
```

**After:**
```python
result = model.airports.by_country("FR") \
                       .with_runways() \
                       .with_hard_runway() \
                       .with_approach_type("ILS") \
                       .with_fuel(avgas=True, jet_a=True) \
                       .all()
```

### Pattern 5: Procedure Queries

**Before:**
```python
airport = model.get_airport("EGLL")
if airport:
    approaches = airport.get_approaches()
    ils_approaches = [p for p in approaches if p.approach_type == "ILS"]
    if ils_approaches:
        best = min(ils_approaches, key=lambda p: p.get_approach_precision())
```

**After:**
```python
airport = model.airports.where(ident="EGLL").first()
if airport:
    best = airport.procedures_query.approaches().by_type("ILS").most_precise()
```

### Pattern 6: Grouping Results

**Before:**
```python
all_airports = model.get_airports_by_country("FR")
by_region = {}
for airport in all_airports:
    region = airport.iso_region or 'unknown'
    if region not in by_region:
        by_region[region] = []
    by_region[region].append(airport)
```

**After:**
```python
by_region = model.airports.by_country("FR").group_by_region()
```

### Pattern 7: Existence Checks

**Before:**
```python
airports = model.get_airports_by_country("FR")
has_french_airports = len(airports) > 0
count = len(airports)
```

**After:**
```python
has_french_airports = model.airports.by_country("FR").exists()
count = model.airports.by_country("FR").count()
```

### Pattern 8: Custom Complex Filters

**Before:**
```python
def complex_filter(airport):
    return (airport.has_hard_runway and
            airport.longest_runway_length_ft and
            airport.longest_runway_length_ft > 4000 and
            len(airport.procedures) > 5 and
            airport.avgas and
            airport.jet_a)

suitable = [a for a in model.get_airports_by_country("FR")
            if complex_filter(a)]
```

**After:**
```python
suitable = model.airports.by_country("FR") \
                         .with_hard_runway() \
                         .with_min_runway_length(4000) \
                         .with_fuel(avgas=True, jet_a=True) \
                         .filter(lambda a: len(a.procedures) > 5) \
                         .all()
```

---

## Automated Migration Tool

Use this script to help automate migrations:

```python
#!/usr/bin/env python3
"""
Euro AIP Migration Helper

Scans your code and suggests modern replacements for legacy method calls.
"""

import re
import sys
from pathlib import Path


PATTERNS = [
    (r'\.get_airport\((.*?)\)',
     r'.airports.where(ident=\1).first()'),

    (r'\.get_airports_by_country\((.*?)\)',
     r'.airports.by_country(\1).all()'),

    (r'\.get_airports_by_source\((.*?)\)',
     r'.airports.by_source(\1).all()'),

    (r'\.get_airports_with_runways\(\)',
     r'.airports.with_runways().all()'),

    (r'\.get_airports_with_procedures\(\)',
     r'.airports.with_procedures().all()'),

    (r'\.get_airports_with_procedures\((.*?)\)',
     r'.airports.with_procedures(\1).all()'),

    (r'\.get_airports_with_aip_data\(\)',
     r'.airports.with_aip_data().all()'),

    (r'\.get_approaches\(\)',
     r'.procedures_query.approaches().all()'),

    (r'\.get_border_crossing_airports\(\)',
     r'.airports.border_crossings().all()'),
]


def migrate_line(line):
    """Apply migration patterns to a line of code."""
    original = line
    for pattern, replacement in PATTERNS:
        line = re.sub(pattern, replacement, line)

    if line != original:
        return line, True
    return line, False


def migrate_file(filepath, dry_run=True):
    """Migrate a Python file."""
    print(f"\nProcessing: {filepath}")

    with open(filepath, 'r') as f:
        lines = f.readlines()

    new_lines = []
    changes = []

    for i, line in enumerate(lines, 1):
        new_line, changed = migrate_line(line)
        new_lines.append(new_line)

        if changed:
            changes.append({
                'line_no': i,
                'old': line.rstrip(),
                'new': new_line.rstrip()
            })

    if changes:
        print(f"  Found {len(changes)} potential migrations:")
        for change in changes:
            print(f"    Line {change['line_no']}:")
            print(f"      - {change['old']}")
            print(f"      + {change['new']}")

        if not dry_run:
            with open(filepath, 'w') as f:
                f.writelines(new_lines)
            print(f"  ✓ File updated")
    else:
        print(f"  No migrations needed")

    return len(changes)


def main():
    import argparse

    parser = argparse.ArgumentParser(description='Migrate Euro AIP legacy code')
    parser.add_argument('paths', nargs='+', help='Files or directories to migrate')
    parser.add_argument('--apply', action='store_true',
                       help='Apply changes (default is dry-run)')

    args = parser.parse_args()

    total_changes = 0

    for path_str in args.paths:
        path = Path(path_str)

        if path.is_file() and path.suffix == '.py':
            total_changes += migrate_file(path, dry_run=not args.apply)
        elif path.is_dir():
            for pyfile in path.rglob('*.py'):
                total_changes += migrate_file(pyfile, dry_run=not args.apply)

    print(f"\n{'='*60}")
    print(f"Total potential migrations: {total_changes}")

    if not args.apply:
        print("\nThis was a DRY RUN. Use --apply to make changes.")
    else:
        print("\nChanges have been applied!")

    return 0


if __name__ == '__main__':
    sys.exit(main())
```

**Usage:**

```bash
# Dry run (see what would change)
python migrate_euro_aip.py your_project/

# Apply changes
python migrate_euro_aip.py --apply your_project/

# Single file
python migrate_euro_aip.py --apply your_project/queries.py
```

---

## Testing Your Migration

### Unit Test Example

Create a test to verify both APIs produce the same results:

```python
import unittest
from euro_aip.models import EuroAipModel


class TestMigration(unittest.TestCase):
    """Verify legacy and modern APIs produce identical results."""

    @classmethod
    def setUpClass(cls):
        cls.model = EuroAipModel.from_file("test_data/euro_aip.json")

    def test_get_airport(self):
        """Test single airport retrieval."""
        # Legacy
        legacy = self.model.get_airport("EGLL")

        # Modern
        modern = self.model.airports.where(ident="EGLL").first()

        self.assertEqual(legacy, modern)

    def test_get_by_country(self):
        """Test country filtering."""
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            legacy = self.model.get_airports_by_country("FR")

        modern = self.model.airports.by_country("FR").all()

        self.assertEqual(len(legacy), len(modern))
        self.assertEqual(set(a.ident for a in legacy),
                        set(a.ident for a in modern))

    def test_complex_query(self):
        """Test complex multi-stage filtering."""
        # Legacy approach
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            french = self.model.get_airports_by_country("FR")
            legacy = [a for a in french
                     if a.has_hard_runway and
                        a.longest_runway_length_ft and
                        a.longest_runway_length_ft > 3000]

        # Modern approach
        modern = self.model.airports.by_country("FR") \
                                    .with_hard_runway() \
                                    .with_min_runway_length(3000) \
                                    .all()

        self.assertEqual(len(legacy), len(modern))
        self.assertEqual(set(a.ident for a in legacy),
                        set(a.ident for a in modern))
```

### Integration Test Example

```python
def test_end_to_end_migration():
    """Test a complete workflow using the modern API."""
    model = EuroAipModel.from_file("test_data/euro_aip.json")

    # Find suitable alternates for EGLL
    primary = model.airports.where(ident="EGLL").first()
    assert primary is not None

    # Find nearby airports with ILS
    alternates = model.airports.by_country("GB") \
                               .with_hard_runway() \
                               .with_min_runway_length(3000) \
                               .with_approach_type("ILS") \
                               .filter(lambda a: a.ident != "EGLL") \
                               .all()

    assert len(alternates) > 0

    # Verify each alternate has required capabilities
    for airport in alternates:
        assert airport.has_hard_runway
        assert airport.longest_runway_length_ft >= 3000
        assert any(p.approach_type == "ILS"
                  for p in airport.procedures_query.approaches().all())
```

---

## Troubleshooting

### Issue: AttributeError on 'airports'

**Error:**
```
AttributeError: 'dict' object has no attribute 'by_country'
```

**Cause:** Direct dict access instead of property access

**Fix:**
```python
# Wrong
model._airports.by_country("FR")  # _airports is a dict

# Right
model.airports.by_country("FR")  # airports is a property
```

### Issue: Deprecation Warnings

**Error:**
```
DeprecationWarning: get_airports_by_country() is deprecated.
```

**Fix:** This is intentional. Update your code to use the modern API:

```python
# Old
airports = model.get_airports_by_country("FR")

# New
airports = model.airports.by_country("FR").all()
```

**Suppress temporarily:**
```python
import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)
```

### Issue: Wrong Return Type

**Problem:**
```python
# This returns AirportCollection, not List[Airport]
airports = model.airports.by_country("FR")
```

**Fix:** Add terminal operation:
```python
# Return list
airports = model.airports.by_country("FR").all()

# Or iterate directly
for airport in model.airports.by_country("FR"):
    print(airport.name)
```

### Issue: Empty Results

**Problem:**
```python
count = model.airports.by_country("FR").count()
assert count == 0  # Why?
```

**Debug:**
```python
# Check total airports
total = len(model._airports)
print(f"Total airports: {total}")

# Check country codes
countries = set(a.iso_country for a in model._airports.values())
print(f"Countries: {countries}")

# Verify filtering
all_airports = list(model._airports.values())
french = [a for a in all_airports if a.iso_country == "FR"]
print(f"French airports (manual): {len(french)}")
```

### Issue: Performance Degradation

**Problem:** Queries seem slower after migration

**Cause:** Not reusing collections

**Fix:**
```python
# Bad - queries model multiple times
for country in ["FR", "DE", "GB"]:
    airports = model.airports.by_country(country).all()
    process(airports)

# Good - query once, filter in memory
all_airports = model.airports.by_countries(["FR", "DE", "GB"])
by_country = all_airports.group_by_country()
for country, airports in by_country.items():
    process(airports)
```

---

## Migration Checklist

- [ ] Install updated euro-aip library
- [ ] Run existing tests to see deprecation warnings
- [ ] Identify all legacy method calls
- [ ] Create migration branch in git
- [ ] Migrate simple 1:1 replacements first
- [ ] Migrate complex filters
- [ ] Run tests after each migration
- [ ] Update documentation
- [ ] Code review
- [ ] Merge to main

---

## Support

If you encounter issues during migration:

1. Check this guide
2. Review the [Modern API Guide](modern_query_api_guide.md)
3. Check [GitHub Issues](https://github.com/yourusername/euro_aip/issues)
4. Ask in discussions

---

## Summary

The migration to the modern query API provides:

- ✅ **Cleaner code** - Less boilerplate
- ✅ **Better composability** - Chain filters naturally
- ✅ **Type safety** - IDE autocomplete
- ✅ **Consistency** - Same patterns everywhere
- ✅ **Performance** - Optimized queries
- ✅ **Future-proof** - Extensible design

The legacy API will be maintained for one major version cycle, giving you time to migrate at your own pace.
