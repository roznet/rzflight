# Database Quick Reference

**Purpose:** Quick SQLite queries for testing/verification, with equivalent euro_aip Python code.

---

## Database Location

```bash
# Sample database for testing
data/airports.db

# Or use the test sample
Tests/RZFlightTests/samples/airports_small.db
```

---

## Database Schema

### airports
```sql
CREATE TABLE airports (
    icao_code TEXT PRIMARY KEY,
    name TEXT,
    type TEXT,
    latitude_deg REAL,
    longitude_deg REAL,
    elevation_ft REAL,
    continent TEXT,
    iso_country TEXT,
    iso_region TEXT,
    municipality TEXT,
    scheduled_service TEXT,
    gps_code TEXT,
    iata_code TEXT,
    local_code TEXT,
    home_link TEXT,
    wikipedia_link TEXT,
    keywords TEXT,
    sources TEXT,
    created_at TEXT,
    updated_at TEXT
);
```

### runways
```sql
CREATE TABLE runways (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    airport_icao TEXT NOT NULL,
    le_ident TEXT,
    he_ident TEXT,
    length_ft REAL,
    width_ft REAL,
    surface TEXT,
    lighted INTEGER,
    closed INTEGER,
    le_latitude_deg REAL,
    le_longitude_deg REAL,
    le_elevation_ft REAL,
    le_heading_degT REAL,
    le_displaced_threshold_ft REAL,
    he_latitude_deg REAL,
    he_longitude_deg REAL,
    he_elevation_ft REAL,
    he_heading_degT REAL,
    he_displaced_threshold_ft REAL,
    created_at TEXT,
    updated_at TEXT
);
```

### procedures
```sql
CREATE TABLE procedures (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    airport_icao TEXT NOT NULL,
    name TEXT,
    procedure_type TEXT,
    approach_type TEXT,
    runway_ident TEXT,
    runway_letter TEXT,
    runway_number TEXT,
    source TEXT,
    authority TEXT,
    raw_name TEXT,
    created_at TEXT,
    updated_at TEXT
);
```

### aip_entries
```sql
CREATE TABLE aip_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    airport_icao TEXT,
    section TEXT,
    field TEXT,
    value TEXT,
    std_field TEXT,
    std_field_id INTEGER,
    mapping_score REAL,
    alt_field TEXT,
    alt_value TEXT,
    source TEXT,
    source_priority INTEGER DEFAULT 0,
    created_at TEXT,
    updated_at TEXT,
    FOREIGN KEY (airport_icao) REFERENCES airports (icao_code),
    UNIQUE(airport_icao, section, field, source)
);
```

---

## Quick Queries

### Count airports

**SQLite:**
```bash
sqlite3 data/airports.db "SELECT COUNT(*) FROM airports"
```

**Python:**
```python
model.airports.count()
```

### Count airports in France

**SQLite:**
```bash
sqlite3 data/airports.db "SELECT COUNT(*) FROM airports WHERE iso_country='FR'"
```

**Python:**
```python
model.airports.by_country("FR").count()
```

### Check if airport exists

**SQLite:**
```bash
sqlite3 data/airports.db "SELECT icao_code, name FROM airports WHERE icao_code='LFPG'"
```

**Python:**
```python
'LFPG' in model.airports
# or
model.airports.get('LFPG')
```

### Get airport details

**SQLite:**
```bash
sqlite3 -header data/airports.db "SELECT * FROM airports WHERE icao_code='EGLL'"
```

**Python:**
```python
airport = model.airports['EGLL']
print(airport.name, airport.iso_country, airport.elevation_ft)
```

### List airports by country

**SQLite:**
```bash
sqlite3 data/airports.db "SELECT icao_code, name FROM airports WHERE iso_country='FR' LIMIT 10"
```

**Python:**
```python
for a in model.airports.by_country("FR").take(10):
    print(a.ident, a.name)
```

### Count airports per country

**SQLite:**
```bash
sqlite3 data/airports.db "SELECT iso_country, COUNT(*) as cnt FROM airports GROUP BY iso_country ORDER BY cnt DESC"
```

**Python:**
```python
by_country = model.airports.group_by_country()
for country, airports in sorted(by_country.items(), key=lambda x: -len(x[1])):
    print(f"{country}: {len(airports)}")
```

---

## Runway Queries

### Get runways for airport

**SQLite:**
```bash
sqlite3 -header data/airports.db "SELECT le_ident, he_ident, length_ft, surface FROM runways WHERE airport_icao='EGLL'"
```

**Python:**
```python
airport = model.airports['EGLL']
for r in airport.runways:
    print(r.le_ident, r.he_ident, r.length_ft, r.surface)
```

### Find airports with long runways

**SQLite:**
```bash
sqlite3 data/airports.db "SELECT DISTINCT airport_icao FROM runways WHERE length_ft > 8000"
```

**Python:**
```python
model.airports.with_min_runway_length(8000).all()
```

### Count airports by surface type

**SQLite:**
```bash
sqlite3 data/airports.db "SELECT surface, COUNT(DISTINCT airport_icao) FROM runways GROUP BY surface"
```

**Python:**
```python
hard = model.airports.with_hard_runway().count()
soft = model.airports.with_soft_runway().count()
print(f"Hard: {hard}, Soft: {soft}")
```

---

## Procedure Queries

### Count procedures by type

**SQLite:**
```bash
sqlite3 data/airports.db "SELECT procedure_type, COUNT(*) FROM procedures GROUP BY procedure_type"
```

**Python:**
```python
by_type = model.procedures.group_by_type()
for ptype, procs in by_type.items():
    print(f"{ptype}: {len(procs)}")
```

### Find airports with ILS

**SQLite:**
```bash
sqlite3 data/airports.db "SELECT DISTINCT airport_icao FROM procedures WHERE approach_type='ILS'"
```

**Python:**
```python
model.airports.with_approach_type("ILS").all()
```

### Get procedures for airport

**SQLite:**
```bash
sqlite3 -header data/airports.db "SELECT name, procedure_type, approach_type, runway_ident FROM procedures WHERE airport_icao='EGLL'"
```

**Python:**
```python
airport = model.airports['EGLL']
for p in airport.procedures_query.all():
    print(p.name, p.procedure_type, p.approach_type, p.runway_ident)
```

### Count approach types

**SQLite:**
```bash
sqlite3 data/airports.db "SELECT approach_type, COUNT(*) FROM procedures WHERE procedure_type='approach' GROUP BY approach_type ORDER BY COUNT(*) DESC"
```

**Python:**
```python
by_approach = model.procedures.approaches().group_by_approach_type()
for atype, procs in sorted(by_approach.items(), key=lambda x: -len(x[1])):
    print(f"{atype}: {len(procs)}")
```

---

## AIP Queries

### Get fuel information

**SQLite:**
```bash
sqlite3 data/airports.db "SELECT value FROM aip_entries WHERE airport_icao='EGLL' AND std_field_id=402"
```

**Python:**
```python
airport = model.airports['EGLL']
fuel = airport.get_aip_entry_for_field(402)
print(fuel.value if fuel else "No fuel info")
```

### Count standardized fields

**SQLite:**
```bash
sqlite3 data/airports.db "SELECT COUNT(*) FROM aip_entries WHERE std_field IS NOT NULL"
```

**Python:**
```python
stats = model.get_field_mapping_statistics()
print(f"Mapped: {stats['mapped_fields']}")
```

---

## Loading Model from Database (Preferred)

```python
from euro_aip.storage.database_storage import DatabaseStorage

# Initialize storage and load model
storage = DatabaseStorage("data/airports.db")
model = storage.load_model()

# Now use the query API
french = model.airports.by_country("FR").all()
```

## Direct Database Access (Python)

For quick database queries without loading the full model:

```python
from euro_aip.sources.database import DatabaseSource

db = DatabaseSource("data/airports.db")

# Get database info
info = db.get_database_info()
for table in info['tables']:
    print(f"{table['name']}: {table['row_count']} rows")

# Get airports with SQL where clause
airports = db.get_airports(where="iso_country='FR'")

# Get airports with runways
airports = db.get_airports_with_runways(where="iso_country='GB'")

# Get airports by ICAO list
airports = db.get_airports_by_icao_list(['EGLL', 'LFPG', 'EDDF'])

# Raw SQL
with db.get_connection() as conn:
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM airports WHERE iso_country='DE'")
    print(cursor.fetchone()[0])
```

## DatabaseStorage Methods

```python
storage = DatabaseStorage("data/airports.db")

# Load full model
model = storage.load_model()

# Save model back to database
storage.save_model(model)

# Get database info
info = storage.get_database_info()

# Get changes for an airport (last 30 days)
changes = storage.get_changes_for_airport("EGLL", days=30)

# Border crossing data
bc_stats = storage.get_border_crossing_statistics()
bc_by_country = storage.get_border_crossing_by_country("FR")
```

---

## When to Use Which

| Task | Use |
|------|-----|
| Quick count/check | SQLite directly |
| Verify data exists | SQLite or `'ICAO' in model.airports` |
| Complex filtering | euro_aip Python API |
| Chained queries | euro_aip Python API |
| One-off data exploration | SQLite |
| Integration/application | euro_aip Python API |
| Debugging data issues | SQLite (see raw data) |

---

## Useful SQLite Commands

```bash
# List all tables
sqlite3 data/airports.db ".tables"

# Show schema
sqlite3 data/airports.db ".schema airports"

# Enable headers
sqlite3 -header data/airports.db "SELECT..."

# Column mode (prettier output)
sqlite3 -header -column data/airports.db "SELECT..."

# Export to CSV
sqlite3 -header -csv data/airports.db "SELECT * FROM airports WHERE iso_country='FR'" > french_airports.csv
```
