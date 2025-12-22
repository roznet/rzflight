# Euro AIP Library - Design Documentation

**Version:** 2.0
**Last Updated:** December 14, 2025

---

## 📚 Documentation Index

This directory contains the authoritative design and API documentation for the Euro AIP library.

---

## 🎯 Quick Navigation

### For New Users
Start here:
- **[Quick Start Guide](./QUICK_START.md)** - Get started in 5 minutes

### For API Reference
Complete references for querying and building models:

#### Query API (Reading Data)
- **[Query API Documentation](./models_query_api_documentation.md)** ⭐ PRIMARY
  - Complete reference for querying airports, procedures, and AIP data
  - Includes: Collections, filtering, set operations, dict-style access
  - All modern features: `|`, `&`, `-`, `reversed()`, etc.

#### Builder API (Writing Data)
- **[Builder API Guide](./builder_api_guide.md)** ⭐ PRIMARY
  - Complete reference for building and modifying models
  - Includes: Transactions, bulk operations, fluent builders
  - Modern, safe model construction

### For Migration
Upgrading from legacy API:
- **[Migration Guide](./migration_guide.md)**
  - Step-by-step migration from legacy methods to modern collections
  - Code examples and patterns

---

## 📖 Main Documentation Files

### 1. Query API Documentation
**File:** `models_query_api_documentation.md` (48KB)

**Use this when you need to:**
- Query airports, procedures, or AIP entries
- Filter and search data
- Understand collection methods
- Use set operations (`|`, `&`, `-`)
- Look up by ICAO code (`airports['EGLL']`)

**Key sections:**
- Core Collections
- Dict-Style Access
- Set Operations
- Airport Filters (by_country, with_runways, etc.)
- Procedure Filters
- Common Patterns (11 patterns)

---

### 2. Builder API Guide
**File:** `builder_api_guide.md` (18KB)

**Use this when you need to:**
- Add or modify airports, procedures, AIP entries
- Use transactions for atomic updates
- Perform bulk operations
- Build airports with fluent builder
- Understand validation

**Key sections:**
- Transaction API
- Bulk Operations
- Builder Pattern
- Validation
- Legacy vs Modern API comparison

---

### 3. Migration Guide
**File:** `migration_guide.md` (19KB)

**Use this when:**
- Upgrading from old API to modern collections
- Finding replacement methods
- Understanding breaking changes
- Need side-by-side examples

**Key sections:**
- Method mapping (old → new)
- Migration patterns
- Common scenarios
- Deprecation warnings

---

### 4. Quick Start Guide
**File:** `QUICK_START.md` (7KB)

**Use this when:**
- First time using the library
- Need quick examples
- Want to see common use cases
- Learning the basics

**Key sections:**
- Installation
- Basic querying
- Filtering
- Common patterns
- Quick reference

---

## 📁 History Directory

Implementation records and enhancement summaries are archived in `history/`:

- **BUILDER_API_IMPLEMENTATION_SUMMARY.md** - Builder API implementation record
- **REFACTORING_SUMMARY.md** - Query API refactoring summary
- **LEGACY_API_MIGRATION_COMPLETE.md** - Legacy API migration completion
- **LEGACY_API_MIGRATION_ANALYSIS.md** - Pre-migration analysis
- **DICT_STYLE_API_ENHANCEMENT.md** - Dict-style access enhancement
- **PYTHONIC_API_ENHANCEMENTS.md** - Set operations & reverse iteration
- **IMPLEMENTATION_COMPLETE.md** - Overall implementation summary

These are historical records useful for understanding design decisions and implementation timeline.

---

## 🔍 Finding What You Need

### "I want to query airports by country"
→ [Query API Documentation](./models_query_api_documentation.md#airport-filters)
```python
french = model.airports.by_country("FR")
```

### "I want to add airports to a model"
→ [Builder API Guide](./builder_api_guide.md#bulk-operations)
```python
result = model.bulk_add_airports(airports, merge="update_existing")
```

### "I want to combine results from multiple queries"
→ [Query API Documentation](./models_query_api_documentation.md#set-operations)
```python
western = airports.by_country("FR") | airports.by_country("DE")
```

### "I want to make atomic changes with rollback"
→ [Builder API Guide](./builder_api_guide.md#transaction-api)
```python
with model.transaction() as txn:
    txn.add_airport(airport)
    txn.bulk_add_procedures(procedures)
```

### "I have legacy code using get_airports_by_country()"
→ [Migration Guide](./migration_guide.md)
```python
# Old
airports = model.get_airports_by_country("FR")

# New
airports = model.airports.by_country("FR").all()
```

### "I want to look up an airport by ICAO code"
→ [Query API Documentation](./models_query_api_documentation.md#dict-style-access)
```python
heathrow = model.airports['EGLL']  # Dict-style (fastest)
# or
heathrow = model.airports.where(ident='EGLL').first()  # Query API
```

---

## 🎓 Learning Path

**For beginners:**
1. Read [Quick Start Guide](./QUICK_START.md)
2. Skim [Query API Documentation](./models_query_api_documentation.md) - Common Patterns
3. Try examples in your code

**For building/populating models:**
1. Read [Builder API Guide](./builder_api_guide.md) - Overview
2. Focus on Bulk Operations section
3. Review Transaction API for complex updates

**For migrating existing code:**
1. Read [Migration Guide](./migration_guide.md) - Introduction
2. Find your methods in the mapping table
3. Follow migration patterns for your use case

---

## 📊 API Overview

### Query API (Reading)

**Core Concept:** Fluent, chainable collections

```python
# Method chaining
suitable = model.airports \
    .by_country("FR") \
    .with_hard_runway() \
    .with_min_runway_length(3000) \
    .all()

# Dict-style access
heathrow = model.airports['EGLL']

# Set operations
multi = airports.by_country("FR") | airports.by_country("DE")
```

### Builder API (Writing)

**Core Concepts:** Transactions, bulk operations, builders

```python
# Transaction
with model.transaction() as txn:
    txn.add_airport(airport)

# Bulk
result = model.bulk_add_airports(airports)

# Builder
airport = model.airport_builder("EGLL") \
    .with_basic_info(name="Heathrow") \
    .commit()
```

---

## 🔗 Related Documentation

### In the Repository
- `README.md` - Project overview and installation
- `euro_aip/models/` - Source code with inline documentation
- `tests/` - Example usage in test files

### External
- Python type hints for IDE autocomplete
- Docstrings in all public methods

---

## 🤝 Contributing

When adding new documentation:
1. Update this README with links
2. Use clear section headers
3. Include code examples
4. Add to appropriate section (Query/Builder/Migration)

When deprecating features:
1. Document in Migration Guide
2. Add deprecation warnings in code
3. Keep migration guide updated

---

## 📝 Document Conventions

All design documents follow these conventions:

**Headers:**
- Clear date and version at top
- Status indicator (✅ Complete, ⚠️ Draft, ❌ Obsolete)

**Code Examples:**
- Use realistic airport codes (EGLL, LFPG, EDDF)
- Include output/results where helpful
- Show both old and new approaches in migration docs

**Sections:**
- Table of Contents for long documents
- Progressive disclosure (simple → complex)
- Common patterns near end

---

## 📅 Version History

### Version 2.0 (December 2025)
- Modern Query API with queryable collections
- Modern Builder API with transactions and bulk operations
- Dict-style access enhancement
- Set operations (`|`, `&`, `-`)
- Reverse iteration support
- Improved `__repr__` with preview

### Version 1.x (Legacy)
- Individual `get_*` methods
- Direct dict manipulation
- No transactions or bulk operations

---

## ✅ Documentation Quality Checklist

All primary documentation maintains:
- ✅ Clear examples
- ✅ Complete API coverage
- ✅ Migration paths from legacy
- ✅ Type hints in examples
- ✅ Common patterns section
- ✅ Updated for latest features

---

**Need help?** Start with the [Quick Start Guide](./QUICK_START.md) or jump directly to:
- [Query API Docs](./models_query_api_documentation.md) for reading data
- [Builder API Docs](./builder_api_guide.md) for writing data
