# Modern Builder API Guide

**Version 2.0 - Modern, Safe Model Building**

This guide covers the modern builder API for constructing and modifying the EuroAipModel with transaction safety, bulk operations, and fluent builders.

---

## Table of Contents

1. [Overview](#overview)
2. [Transaction API](#transaction-api)
3. [Bulk Operations](#bulk-operations)
4. [Builder Pattern](#builder-pattern)
5. [Validation](#validation)
6. [Common Patterns](#common-patterns)
7. [Migration from Legacy API](#migration-from-legacy-api)

---

## Overview

The modern builder API provides three complementary approaches for building and modifying the model:

### 1. **Transaction API** - Safe, atomic updates
- Automatic rollback on error
- Batch operations with single derived field update
- Change tracking

### 2. **Bulk Operations** - Efficient batch processing
- Add multiple airports, procedures, or AIP entries at once
- Single validation and update pass
- Performance optimized

### 3. **Builder Pattern** - Fluent airport construction
- Chainable API for building complex airports
- Validation before committing
- Clear, self-documenting code

---

## Transaction API

### Basic Usage

The transaction API provides safe, atomic updates with automatic rollback on error:

```python
# Basic transaction
with model.transaction() as txn:
    txn.add_airport(airport)
    txn.add_aip_entries("EGLL", entries)
    # Auto-commits on success, auto-rollback on exception
```

### Multiple Operations

Group related operations in a single transaction:

```python
with model.transaction() as txn:
    # Add airports
    for airport in airports:
        txn.add_airport(airport)

    # Add procedures
    for icao, procedures in procedure_data.items():
        txn.add_procedures(icao, procedures)

    # Remove old data
    txn.remove_by_country("XX")

    # All validated and committed atomically
    # Derived fields updated once at end
```

### Transaction Methods

Available operations within a transaction:

```python
with model.transaction() as txn:
    # Individual operations
    txn.add_airport(airport, merge="update_existing")
    txn.add_aip_entries(icao, entries, standardize=True)
    txn.add_procedures(icao, procedures)
    txn.add_border_crossing_entry(entry)
    txn.remove_by_country(country_code)

    # Bulk operations
    txn.bulk_add_airports(airports, merge="update_existing")
    txn.bulk_add_aip_entries(entries_by_icao, standardize=True)
    txn.bulk_add_procedures(procedures_by_icao)
```

### Controlling Derived Field Updates

For performance, defer derived field updates:

```python
# Defer derived field updates during transaction
with model.transaction(auto_update_derived=False) as txn:
    txn.bulk_add_airports(many_airports)
    # No derived field updates during transaction

# Update manually when ready
model.update_all_derived_fields()  # Single pass over all data
```

### Change Tracking

Track what changed in a transaction:

```python
with model.transaction(track_changes=True) as txn:
    txn.bulk_add_airports(airports)
    txn.add_aip_entries("EGLL", entries)

    # Get change summary
    changes = txn.get_changes()
    print(f"Total operations: {changes['total_operations']}")
    print(f"Added airports: {changes['summary']['added_airports']}")
    print(f"Updated airports: {changes['summary']['updated_airports']}")
```

### Error Handling

Transactions automatically rollback on error:

```python
try:
    with model.transaction() as txn:
        txn.add_airport(airport1)
        txn.add_airport(invalid_airport)  # Validation error
        # Transaction rolls back - airport1 not added
except ModelValidationError as e:
    print(f"Transaction failed: {e}")
    # Model is in original state
```

---

## Bulk Operations

### Bulk Add Airports

Add multiple airports efficiently:

```python
# Simple bulk add
result = model.bulk_add_airports([airport1, airport2, airport3])
print(f"Added: {result['added']}, Updated: {result['updated']}")

# Skip existing airports
result = model.bulk_add_airports(
    airports,
    merge="skip_existing"
)

# Without derived field update (for performance)
result = model.bulk_add_airports(
    airports,
    update_derived=False
)
model.update_all_derived_fields()  # Update once at end
```

### Merge Strategies

Control how existing airports are handled:

```python
# Update existing (default) - merges new data into existing
model.bulk_add_airports(airports, merge="update_existing")

# Skip existing - only add new airports
model.bulk_add_airports(airports, merge="skip_existing")

# Replace - completely replace existing airports
model.bulk_add_airports(airports, merge="replace")
```

### Bulk Add AIP Entries

Add AIP entries for multiple airports:

```python
aip_data = {
    "EGLL": egll_entries,
    "LFPG": lfpg_entries,
    "EDDF": eddf_entries
}

result = model.bulk_add_aip_entries(aip_data, standardize=True)
print(f"Added {sum(result.values())} total entries to {len(result)} airports")
```

### Bulk Add Procedures

Add procedures for multiple airports:

```python
procedures_data = {
    "EGLL": egll_procedures,
    "LFPG": lfpg_procedures
}

result = model.bulk_add_procedures(procedures_data)
print(f"Added procedures to {len(result)} airports")
```

### Combining Bulk Operations with Transactions

For maximum safety and performance:

```python
# Load entire dataset transactionally
with model.transaction() as txn:
    # Bulk add base airports
    txn.bulk_add_airports(base_airports)

    # Bulk add AIP data
    txn.bulk_add_aip_entries(aip_data_by_icao)

    # Bulk add procedures
    txn.bulk_add_procedures(procedures_by_icao)

    # All validated and committed atomically
    # Derived fields updated once at end
```

---

## Builder Pattern

### Basic Airport Building

Use the builder for fluent airport construction:

```python
# Create builder
builder = model.airport_builder("EGLL")

# Add information
builder.with_basic_info(
    name="London Heathrow",
    latitude_deg=51.4700,
    longitude_deg=-0.4543,
    iso_country="GB",
    elevation_ft=83
)

builder.with_runways([runway1, runway2])
builder.with_aip_entries(aip_entries, standardize=True)
builder.with_procedures([ils_09l, ils_27r])
builder.with_sources(["uk_eaip", "worldairports"])

# Build without adding to model
airport = builder.build()

# Or commit directly to model
builder.commit()
```

### Method Chaining

Chain methods for concise code:

```python
airport = model.airport_builder("EGLL") \
    .with_basic_info(
        name="London Heathrow",
        latitude_deg=51.4700,
        longitude_deg=-0.4543,
        iso_country="GB"
    ) \
    .with_runways([runway1, runway2]) \
    .with_procedures([ils_09l, ils_27r]) \
    .with_aip_entries(aip_entries) \
    .with_sources(["uk_eaip"]) \
    .build()

# Or commit directly
model.airport_builder("EGLL") \
    .with_basic_info(...) \
    .with_runways(runways) \
    .commit()
```

### Builder Methods

Available builder methods:

```python
builder = model.airport_builder("EGLL")

# Basic info
builder.with_basic_info(
    name=None,
    latitude_deg=None,
    longitude_deg=None,
    elevation_ft=None,
    iso_country=None,
    iso_region=None,
    municipality=None,
    iata_code=None,
    **kwargs  # Additional fields
)

# Runways
builder.with_runway(runway)           # Add single runway
builder.with_runways([r1, r2])        # Add multiple runways

# Procedures
builder.with_procedure(procedure)     # Add single procedure
builder.with_procedures([p1, p2])     # Add multiple procedures

# AIP entries
builder.with_aip_entry(entry, standardize=True)
builder.with_aip_entries([e1, e2], standardize=True)

# Sources
builder.with_source("uk_eaip")
builder.with_sources(["uk_eaip", "worldairports"])

# Validate before building
validation = builder.validate()
if not validation.is_valid:
    print(validation.get_error_messages())

# Build airport object
airport = builder.build()

# Or commit directly to model
airport = builder.commit(update_derived=True)
```

### Validation Before Building

Validate before committing:

```python
builder = model.airport_builder("EGLL") \
    .with_basic_info(...) \
    .with_runways(runways)

# Validate
validation = builder.validate()
if not validation.is_valid:
    for error in validation.errors:
        print(f"Error: {error}")
else:
    # Safe to build
    airport = builder.build()
    model.add_airport(airport)
```

---

## Validation

### Validation Results

All builder operations return or use ValidationResult:

```python
from euro_aip.models import ValidationResult, ModelValidationError

# Validate an airport
validation = model._validate_airport(airport)

if validation.is_valid:
    print("Airport is valid")
else:
    print(f"Invalid: {len(validation.errors)} errors")
    for error in validation.errors:
        print(f"  - {error.field}: {error.message}")
```

### Validation Errors

Validation errors are raised when operations fail:

```python
try:
    result = model.bulk_add_airports(airports, validate=True)
except ModelValidationError as e:
    print(f"Validation failed: {e}")

    # Get detailed error information
    if e.details:
        for airport_error in e.details:
            print(f"Airport {airport_error['icao']}:")
            for error in airport_error['errors']:
                print(f"  - {error}")
```

### Validation Rules

Current validation checks:

1. **ICAO Code** - Must be exactly 4 characters
2. **Coordinates** - Latitude/longitude required for building
3. **Coordinate Ranges** - Valid lat/lon ranges
4. **Runways** - Must have le_ident

---

## Common Patterns

### Pattern 1: Loading Complete Dataset

Load a complete dataset safely:

```python
# Transaction ensures all-or-nothing
with model.transaction() as txn:
    # Load base airports
    txn.bulk_add_airports(base_airports)

    # Load AIP data
    txn.bulk_add_aip_entries(aip_entries_by_icao)

    # Load procedures
    txn.bulk_add_procedures(procedures_by_icao)

    # Load border crossings
    for entry in border_crossing_entries:
        txn.add_border_crossing_entry(entry)
```

### Pattern 2: Incremental Updates

Update the model incrementally:

```python
# Add new country data
with model.transaction() as txn:
    # Remove old data
    txn.remove_by_country("FR")

    # Add new data
    txn.bulk_add_airports(french_airports)
    txn.bulk_add_aip_entries(french_aip_data)
```

### Pattern 3: Building Complex Airports

Build airports with all components:

```python
def build_airport_from_data(icao: str, data: dict) -> Airport:
    """Build complete airport from data dictionary."""
    builder = model.airport_builder(icao)

    # Basic info
    builder.with_basic_info(**data['basic_info'])

    # Runways
    if 'runways' in data:
        builder.with_runways(data['runways'])

    # Procedures
    if 'procedures' in data:
        builder.with_procedures(data['procedures'])

    # AIP entries
    if 'aip_entries' in data:
        builder.with_aip_entries(data['aip_entries'])

    # Sources
    if 'sources' in data:
        builder.with_sources(data['sources'])

    return builder.commit()
```

### Pattern 4: Performance Optimization

Optimize for large datasets:

```python
# Defer derived field updates for performance
with model.transaction(auto_update_derived=False) as txn:
    # Load large dataset
    txn.bulk_add_airports(many_airports)
    txn.bulk_add_aip_entries(many_aip_entries)
    txn.bulk_add_procedures(many_procedures)

# Update derived fields once at the end
model.update_all_derived_fields()
```

### Pattern 5: Change Tracking for Logging

Track and log changes:

```python
import logging

logger = logging.getLogger(__name__)

with model.transaction(track_changes=True) as txn:
    txn.bulk_add_airports(airports)
    txn.bulk_add_aip_entries(aip_data)

    changes = txn.get_changes()
    logger.info(f"Model update: {changes['total_operations']} operations")
    logger.info(f"  Added airports: {len(changes['summary']['added_airports'])}")
    logger.info(f"  Updated airports: {len(changes['summary']['updated_airports'])}")
    logger.info(f"  Added AIP entries: {changes['summary']['added_aip_entries']}")
```

---

## Migration from Legacy API

### Old Way vs New Way

#### Adding Single Airport

```python
# Old way - implicit merge, manual derived update
model.add_airport(airport)
model.update_all_derived_fields()

# New way - transaction with automatic update
with model.transaction() as txn:
    txn.add_airport(airport)
```

#### Adding Multiple Airports

```python
# Old way - loop with manual updates
for airport in airports:
    model.add_airport(airport)
model.update_all_derived_fields()

# New way - bulk operation
model.bulk_add_airports(airports)

# Or in transaction
with model.transaction() as txn:
    txn.bulk_add_airports(airports)
```

#### Building Complex Airport

```python
# Old way - imperative construction
airport = Airport(ident="EGLL")
airport.name = "London Heathrow"
airport.latitude_deg = 51.4700
airport.longitude_deg = -0.4543
for runway in runways:
    airport.add_runway(runway)
for procedure in procedures:
    airport.add_procedure(procedure)
model.add_airport(airport)
model.update_all_derived_fields()

# New way - fluent builder
model.airport_builder("EGLL") \
    .with_basic_info(
        name="London Heathrow",
        latitude_deg=51.4700,
        longitude_deg=-0.4543
    ) \
    .with_runways(runways) \
    .with_procedures(procedures) \
    .commit()
```

#### Loading Complete Dataset

```python
# Old way - no transaction safety
for airport in airports:
    model.add_airport(airport)

for icao, entries in aip_data.items():
    model.add_aip_entries_to_airport(icao, entries)

for icao, procedures in procedure_data.items():
    airport = model.get_airport(icao)
    if airport:
        for procedure in procedures:
            airport.add_procedure(procedure)

model.update_all_derived_fields()

# New way - safe transaction
with model.transaction() as txn:
    txn.bulk_add_airports(airports)
    txn.bulk_add_aip_entries(aip_data)
    txn.bulk_add_procedures(procedure_data)
```

### Migration Strategy

1. **Keep existing code working** - Old API still works
2. **New code uses new API** - Start using transactions and builders
3. **Gradually refactor** - Update old code over time

---

## Best Practices

### 1. Use Transactions for Safety

Always use transactions for multi-step operations:

```python
# Good - atomic update
with model.transaction() as txn:
    txn.remove_by_country("XX")
    txn.bulk_add_airports(new_airports)

# Risky - model left inconsistent if second operation fails
model.remove_airports_by_country("XX")
model.bulk_add_airports(new_airports)  # If this fails, XX is empty!
```

### 2. Use Bulk Operations for Performance

Use bulk operations instead of loops:

```python
# Slow - validates and updates derived fields N times
for airport in airports:
    model.add_airport(airport)
    model.update_all_derived_fields()

# Fast - single validation and update pass
model.bulk_add_airports(airports)
```

### 3. Use Builder for Complex Objects

Use builder for constructing complex airports:

```python
# Clear and self-documenting
airport = model.airport_builder("EGLL") \
    .with_basic_info(...) \
    .with_runways(runways) \
    .with_procedures(procedures) \
    .build()

# vs imperative construction (harder to read)
airport = Airport(ident="EGLL")
airport.name = "..."
# ... many lines ...
```

### 4. Defer Derived Updates for Large Loads

Defer derived field updates for large datasets:

```python
# Efficient - single derived field update
with model.transaction(auto_update_derived=False) as txn:
    txn.bulk_add_airports(many_airports)
model.update_all_derived_fields()
```

### 5. Track Changes for Audit Logs

Use change tracking for audit logs:

```python
with model.transaction(track_changes=True) as txn:
    # ... operations ...
    changes = txn.get_changes()
    audit_log.record(changes)
```

---

## API Reference

### EuroAipModel Methods

```python
# Transaction
model.transaction(auto_update_derived=True, track_changes=False) -> ModelTransaction

# Builder
model.airport_builder(icao: str) -> AirportBuilder

# Bulk operations
model.bulk_add_airports(airports, merge="update_existing", validate=True, update_derived=True) -> dict
model.bulk_add_aip_entries(entries_by_icao, standardize=True) -> dict
model.bulk_add_procedures(procedures_by_icao) -> dict
```

### ModelTransaction Methods

```python
# Individual operations
txn.add_airport(airport, merge="update_existing")
txn.add_aip_entries(icao, entries, standardize=True)
txn.add_procedures(icao, procedures)
txn.add_border_crossing_entry(entry)
txn.remove_by_country(country_code)

# Bulk operations
txn.bulk_add_airports(airports, merge="update_existing")
txn.bulk_add_aip_entries(entries_by_icao, standardize=True)
txn.bulk_add_procedures(procedures_by_icao)

# Info
txn.get_changes() -> dict
```

### AirportBuilder Methods

```python
# Builder methods (all return self for chaining)
builder.with_basic_info(name=None, latitude_deg=None, ..., **kwargs)
builder.with_runway(runway)
builder.with_runways(runways)
builder.with_procedure(procedure)
builder.with_procedures(procedures)
builder.with_aip_entry(entry, standardize=True)
builder.with_aip_entries(entries, standardize=True)
builder.with_source(source)
builder.with_sources(sources)

# Validation and building
builder.validate() -> ValidationResult
builder.build() -> Airport
builder.commit(update_derived=True) -> Airport
```

---

## Summary

The modern builder API provides:

1. **Transaction API** - Safe, atomic updates with automatic rollback
2. **Bulk Operations** - Efficient batch processing
3. **Builder Pattern** - Fluent, self-documenting airport construction
4. **Validation** - Catch errors before they corrupt the model
5. **Performance** - Optimized for large datasets

Use these tools to build robust, maintainable model construction code.
