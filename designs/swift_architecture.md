# RZFlight Swift Architecture Guide

> Internal architecture documentation for contributors and maintainers.

---

## Package Structure

```
Sources/RZFlight/
├── Airport.swift           # Core airport model + extensions
├── AIPEntry.swift          # AIP entries + field catalog
├── AviationRemoteServices.swift  # AVWX API integration
├── Heading.swift           # Compass heading calculations
├── Heading+iOS.swift       # iOS-specific extensions (UIImage)
├── KnownAirports.swift     # Database layer + spatial queries
├── Log.swift               # OSLog categories
├── Metar.swift             # Weather data structure
├── Percent.swift           # Percentage calculations
├── Procedure.swift         # Flight procedures
├── Runway.swift            # Runway geometry
├── RunwayWindModel.swift   # Wind calculation engine
├── Speed.swift             # Wind speed handling

Resources/
└── aip_fields.csv          # AIP field standardization catalog
```

---

## Dependencies

| Package | Purpose | Used In |
|---------|---------|---------|
| FMDB | SQLite wrapper | KnownAirports, Airport, Procedure, AIPEntry, Runway |
| KDTree | Spatial indexing | KnownAirports (nearest queries) |
| Geomagnetism | Magnetic declination | Airport (heading conversions) |
| RZUtilsSwift | Utilities, Secrets | AviationRemoteServices, Metar |
| CoreLocation | Coordinates | Throughout |
| MapKit | Distance calculations | KnownAirports |
| AVFoundation | Text-to-speech | RunwayWindModel (iOS) |

---

## Database Schema

The package expects a SQLite database with these tables:

### airports
```sql
CREATE TABLE airports (
    icao_code TEXT PRIMARY KEY,
    name TEXT,
    latitude_deg REAL,
    longitude_deg REAL,
    elevation_ft INTEGER,
    iso_country TEXT,
    iso_region TEXT,
    continent TEXT,
    type TEXT,
    municipality TEXT,
    scheduled_service TEXT,
    gps_code TEXT,
    iata_code TEXT,
    local_code TEXT,
    home_link TEXT,
    wikipedia_link TEXT,
    keywords TEXT,
    sources TEXT,           -- Comma-separated list
    created_at TEXT,        -- ISO8601 format
    updated_at TEXT         -- ISO8601 format
);
```

### runways
```sql
CREATE TABLE runways (
    id INTEGER PRIMARY KEY,
    airport_icao TEXT,
    length_ft INTEGER,
    width_ft INTEGER,
    surface TEXT,
    lighted INTEGER,        -- Boolean 0/1
    closed INTEGER,         -- Boolean 0/1
    le_ident TEXT,
    le_latitude_deg REAL,
    le_longitude_deg REAL,
    le_elevation_ft REAL,
    le_heading_degT REAL,
    le_displaced_threshold_ft REAL,
    he_ident TEXT,
    he_latitude_deg REAL,
    he_longitude_deg REAL,
    he_elevation_ft REAL,
    he_heading_degT REAL,
    he_displaced_threshold_ft REAL
);
```

### procedures
```sql
CREATE TABLE procedures (
    id INTEGER PRIMARY KEY,
    airport_icao TEXT,
    name TEXT,
    procedure_type TEXT,    -- "approach", "departure", "arrival"
    approach_type TEXT,     -- "ILS", "RNAV", "RNP", "VOR", etc.
    runway_number TEXT,
    runway_letter TEXT,
    runway_ident TEXT,
    source TEXT,
    authority TEXT,
    raw_name TEXT
);
```

### aip_entries
```sql
CREATE TABLE aip_entries (
    id INTEGER PRIMARY KEY,
    airport_icao TEXT,
    section TEXT,           -- "admin", "operational", "handling", "passenger"
    field TEXT,
    value TEXT,
    std_field_id INTEGER,   -- FK to aip_fields catalog
    mapping_score REAL,
    alt_field TEXT,
    alt_value TEXT,
    source TEXT
);
```

### border_crossing_points
```sql
CREATE TABLE border_crossing_points (
    id INTEGER PRIMARY KEY,
    icao_code TEXT,
    matched_airport_icao TEXT,
    -- Additional fields as needed
);
```

---

## Data Loading Patterns

### Lazy Loading

Airport data is loaded lazily to minimize memory usage:

```swift
// Airport created with basic data only
var airport = airports.airport(icao: "LFPG")  // Loads runways by default

// Explicitly load additional data
_ = airport?.addProcedures(db: db)
_ = airport?.addAIPEntries(db: db)
_ = airport?.addExtendedData(db: db)  // All at once
```

### Selective Loading

For specific needs:

```swift
let airport = airports.airport(
    icao: "LFPG",
    ensureRunway: true,
    ensureProcedures: true,
    ensureAIP: false
)
```

### Bulk Loading

For operations on many airports, bulk loading is more efficient:

```swift
let airports = KnownAirports(db: db)
airports.loadAllProcedures()    // Single query for all procedures
airports.loadAllRunways()       // Single query for all runways
airports.loadAllAIPEntries()    // Single query for all AIP entries
airports.loadAllBorderCrossing()
airports.loadAllExtendedData()  // Everything at once
```

After bulk loading, airports in the `known` dictionary have their data populated.

---

## Spatial Indexing

`KnownAirports` uses a KDTree for efficient spatial queries:

```swift
// O(log n) nearest neighbor queries
let nearest = airports.nearestAirport(coord: location)
let nearestK = airports.nearest(coord: location, count: 10)

// With filtering during search
let nearestMatching = airports.nearestMatching(coord: location, needle: "Paris", count: 5)
```

The KDTree is built once at initialization from all airports in the database.

---

## Adding New Features

### Adding a New Airport Filter

1. Add computed property to `Airport` if needed:

```swift
// In Airport.swift
public var hasFeature: Bool {
    // Check aipEntries, procedures, or other data
    aipEntries.contains { ... }
}
```

2. Add array extension in `KnownAirports.swift`:

```swift
extension Array where Element == Airport {
    public func withFeature() -> [Airport] {
        filter { $0.hasFeature }
    }
}
```

### Adding a New AIP Field Check

1. If checking raw text in AIP entries:

```swift
// In Airport.swift
public var hasNewField: Bool {
    aipEntries.contains { entry in
        entry.value.uppercased().contains("KEYWORD")
    }
}
```

2. If using standardized fields, add to `aip_fields.csv` and use:

```swift
airport.aipEntry(for: "StandardFieldName", useStandardized: true)
```

### Adding a New Procedure Type

1. Add case to `ApproachType` enum in `Procedure.swift`:

```swift
public enum ApproachType: String, Codable, CaseIterable {
    // ... existing cases
    case newType = "NEW"

    public var precisionRank: Int {
        switch self {
        // ... add ranking
        }
    }

    public var precisionCategory: PrecisionCategory {
        switch self {
        // ... add categorization
        }
    }
}
```

### Adding a New Database Query

1. Add method to `KnownAirports`:

```swift
public func airportsWithNewCriteria(param: Type) -> [Airport] {
    // Option 1: Use KDTree for spatial queries
    let nearby = tree.nearestK(count, to: Airport.at(location: coord))

    // Option 2: Iterate known airports
    for (_, airport) in known {
        // Filter logic
    }

    // Option 3: Direct SQL query
    let query = "SELECT * FROM airports WHERE ..."
    if let res = db.executeQuery(query, withArgumentsIn: []) {
        while res.next() {
            // Process results
        }
    }
}
```

### Adding iOS-Specific Features

1. Create or edit `*+iOS.swift` file
2. Wrap in `#if os(iOS)`:

```swift
#if os(iOS)
import UIKit

extension YourType {
    public var iosFeature: UIImage? {
        // iOS-specific implementation
    }
}
#endif
```

---

## Codable Patterns

### Dual Format Support

Models support both internal (camelCase) and API (snake_case) formats:

```swift
enum CodingKeys: String, CodingKey {
    case city
    case municipality      // API format - for decoding only
    case isoRegion = "iso_region"
}

public init(from decoder: Decoder) throws {
    let container = try decoder.container(keyedBy: CodingKeys.self)

    // Try multiple keys for backwards compatibility
    self.city = try container.decodeIfPresent(String.self, forKey: .city)
        ?? container.decodeIfPresent(String.self, forKey: .municipality)
        ?? ""
}
```

### FMResultSet Initialization

All database-backed models have an `init(res: FMResultSet)`:

```swift
public init(res: FMResultSet) {
    self.field = res.string(forColumn: "column_name") ?? ""
    self.optionalField = res.columnIsNull("column") ? nil : res.double(forColumn: "column")
}
```

---

## Wind Calculation Math

### Crosswind Component

```swift
crosswind = windSpeed * sin(windAngle - runwayAngle)
```

### Headwind Component

```swift
headwind = windSpeed * cos(windAngle - runwayAngle)
```

### Great Circle Calculations

For procedure visualization lines:

```swift
// Earth radius: 3440.065 nautical miles
let lat2 = asin(sin(lat1) * cos(d/R) + cos(lat1) * sin(d/R) * cos(bearing))
let lon2 = lon1 + atan2(sin(bearing) * sin(d/R) * cos(lat1),
                        cos(d/R) - sin(lat1) * sin(lat2))
```

---

## Remote Service Integration

### AVWX API

Token stored via `RZUtilsSwift.Secrets`:

```swift
// Token lookup
guard let token = Secrets.shared["avwx"] else { return }

// API call pattern
var request = URLRequest(url: url)
request.setValue("BEARER \(token)", forHTTPHeaderField: "Authorization")
```

### Adding New Remote Services

1. Add struct inside `AviationRemoteService`:

```swift
struct NewService {
    public static func fetch(param: Type, callback: @escaping (Result?) -> Void) {
        guard let url = URL(string: "https://..."),
              let token = Secrets.shared["service_key"] else {
            callback(nil)
            return
        }

        var request = URLRequest(url: url)
        // Configure request

        let task = URLSession.shared.dataTask(with: request) { data, response, error in
            // Handle response
            // Use Logger.web for logging
        }
        task.resume()
    }
}
```

---

## Testing

### Test Database

Tests should use an in-memory or temporary database:

```swift
let db = FMDatabase()  // In-memory
db.open()
// Create tables and insert test data
```

### Test Airports

Create test airports with known values:

```swift
let testAirport = Airport(location: CLLocationCoordinate2D(latitude: 48.8566, longitude: 2.3522), icao: "TEST")
```

### AIP Field Catalog Override

For testing standardization:

```swift
AIPEntry.AIPFieldCatalog.setOverrideURL(testCsvUrl)
// Run tests
AIPEntry.AIPFieldCatalog.setOverrideURL(nil)  // Reset
```

---

## File Locations Quick Reference

| To modify... | Edit file |
|--------------|-----------|
| Airport properties | `Airport.swift` |
| Airport filters (Array extensions) | `Airport.swift` (fuel) or `KnownAirports.swift` (others) |
| Database queries | `KnownAirports.swift` |
| Runway data | `Runway.swift` |
| Procedure types/precision | `Procedure.swift` |
| AIP field catalog | `Resources/aip_fields.csv` + `AIPEntry.swift` |
| Wind calculations | `RunwayWindModel.swift`, `Heading.swift` |
| Remote API calls | `AviationRemoteServices.swift` |
| iOS-specific features | `*+iOS.swift` files |

---

## Common Patterns

### Adding Data to Airport from Database

```swift
// In Airport.swift
public mutating func addNewData(db: FMDatabase) -> Airport {
    if self.newData.isEmpty {
        self.newData = Self.loadNewData(for: self.icao, db: db)
    }
    return self
}

private static func loadNewData(for icao: String, db: FMDatabase) -> [NewType] {
    let res = db.executeQuery("SELECT * FROM new_table WHERE airport_icao = ?", withArgumentsIn: [icao])
    var items: [NewType] = []
    if let res = res {
        while res.next() {
            items.append(NewType(res: res))
        }
    }
    return items
}
```

### Border Crossing Pattern

Uses cached Set for efficient lookups:

```swift
// Lazy load once
private func loadBorderCrossingICAOs() {
    if borderCrossingICAOs != nil { return }
    // Load from DB into Set<String>
}

// O(1) lookup
private func isBorderCrossingICAO(_ icao: String) -> Bool {
    loadBorderCrossingICAOs()
    return borderCrossingICAOs?.contains(icao) ?? false
}
```
