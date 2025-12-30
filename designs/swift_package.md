# RZFlight Swift Package

> A comprehensive Swift library for flight planning, aviation calculations, and airport data management.

**Platforms:** iOS 15+, macOS 12+
**Swift Version:** 5.5+
**Package Manager:** Swift Package Manager

## Installation

```swift
dependencies: [
    .package(url: "https://github.com/roznet/rzflight", from: "1.0.0")
]
```

## Architecture Overview

```
RZFlight
├── Data Models
│   ├── Airport          # Core airport data with runways, procedures, AIP
│   ├── Runway           # Runway geometry and configuration
│   ├── Procedure        # Approaches, departures, arrivals
│   ├── AIPEntry         # Aeronautical Information Publication entries
│   └── Metar            # Weather data structure
├── Calculation Models
│   ├── RunwayWindModel  # Wind calculations and component analysis
│   ├── Heading          # Compass heading arithmetic
│   ├── Speed            # Wind speed handling
│   └── Percent          # Percentage calculations
├── Database Layer
│   └── KnownAirports    # Airport database with spatial indexing
└── Remote Services
    └── AVWX             # Weather API integration
```

## Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| RZUtilsSwift | 1.0.27+ | Utilities and Secrets management |
| Geomagnetism | 1.0.0+ | Magnetic declination calculations |
| FMDB | 2.7.7+ | SQLite database wrapper |
| KDTree | 1.4.0+ | Spatial indexing for nearest queries |

---

## Core Data Models

### Airport

The central data structure representing an airport with all associated data.

```swift
struct Airport: Codable, Hashable, Equatable, Identifiable {
    var icao: String              // ICAO identifier (e.g., "LFPG")
    var name: String              // Airport name
    var latitude: Double          // Decimal degrees
    var longitude: Double         // Decimal degrees
    var elevation: Int            // Feet MSL
    var country: String           // ISO country code
    var continent: String         // Continent code
    var type: AirportType         // large, medium, small, closed, heliport
    var runways: [Runway]         // Associated runways
    var procedures: [Procedure]   // Approaches, departures, arrivals
    var aipEntries: [AIPEntry]    // AIP documentation entries
}
```

**Key Features:**
- Magnetic/true heading conversions using Geomagnetism library
- Best runway selection based on wind conditions
- Procedure filtering by type and runway
- Border crossing point detection
- Procedure visualization data for map overlays

**Common Operations:**

```swift
// Find best runway for current wind
let runway = airport.bestRunway(for: wind)

// Get all ILS approaches
let ils = airport.procedures.filter { $0.approachType == .ILS }

// Check if airport has precision approaches
let hasPrecision = airport.hasPrecisionApproach

// Get magnetic heading for a runway
let magneticHeading = airport.magneticHeading(for: runway)
```

### Runway

Represents a physical runway with both ends.

```swift
struct Runway: Codable {
    var lowEnd: RunwayEnd         // Lower numbered end
    var highEnd: RunwayEnd        // Higher numbered end
    var length: Int               // Length in feet
    var width: Int                // Width in feet
    var surface: String           // ASP, CON, GRS, etc.
    var lighted: Bool             // Has lighting
    var closed: Bool              // Closure status
}

struct RunwayEnd {
    var identifier: String        // "09", "27L", etc.
    var latitude: Double
    var longitude: Double
    var elevation: Int            // Feet MSL
    var trueHeading: Double       // True heading in degrees
    var displacedThreshold: Int   // Displaced threshold in feet
}
```

**Surface Types:**
- Hard: ASP (asphalt), CON (concrete), PEM (bitumen)
- Soft: GRS (grass), TRF (turf), GVL (gravel)

### Procedure

Flight procedures including approaches, departures, and arrivals.

```swift
struct Procedure: Codable, Hashable, Equatable, Identifiable {
    var id: String
    var name: String
    var type: ProcedureType       // approach, departure, arrival
    var approachType: ApproachType?  // ILS, RNAV, VOR, etc.
    var runway: String?           // Associated runway identifier
}

enum ProcedureType: String, Codable {
    case approach, departure, arrival
}

enum ApproachType: String, Codable {
    case ILS, RNAV, RNP, VOR, NDB, LOC, LDA, SDF, visual
}
```

**Precision Categories:**
- **Precision:** ILS
- **RNAV:** RNAV, RNP
- **Non-Precision:** VOR, NDB, LOC, LDA, SDF, visual

### AIPEntry

Aeronautical Information Publication entries for airport documentation.

```swift
struct AIPEntry: Codable, Hashable, Equatable, Identifiable {
    var id: String
    var section: AIPSection
    var field: String
    var value: String
    var alternativeValue: String?
    var mappingScore: Double      // Confidence score for field mapping
}

enum AIPSection: String, Codable {
    case admin, operational, handling, passenger
}
```

**Field Standardization:**
- Built-in catalog system (`aip_fields.csv`)
- Automatic field name normalization
- Alternative value support for ambiguous entries

---

## Calculation Models

### RunwayWindModel

Primary wind calculation engine for runway operations.

```swift
class RunwayWindModel {
    var windDirection: Heading    // Wind coming from
    var windSpeed: Speed          // Wind speed in knots
    var gustSpeed: Speed?         // Gust speed if present
    var runwayHeading: Heading    // Runway magnetic heading

    var crosswindComponent: Speed { get }
    var headwindComponent: Speed { get }
    var crosswindPercent: Percent { get }
    var headwindPercent: Percent { get }
}
```

**Key Methods:**

```swift
// Calculate wind components
let crosswind = model.crosswindComponent
let headwind = model.headwindComponent

// Update from METAR
model.update(from: metar)

// Text-to-speech announcements (iOS)
model.speakWindCheck()
model.speakClearance(runway: "27L", altitude: 3000)

// Random wind for testing
model.randomizeWind()
```

### Heading

Circular arithmetic for compass headings with automatic 0-360 normalization.

```swift
struct Heading: Equatable, CustomStringConvertible {
    var degrees: Double           // 0-360 degrees

    init(degrees: Double)
    init(runway: String)          // From runway identifier ("27", "09L")

    var runway: String { get }    // "27", "09", etc.
    var opposing: Heading { get } // 180 degrees opposite

    func direction(to other: Heading) -> Direction
    func crosswindComponent(windSpeed: Speed) -> Speed
    func headwindComponent(windSpeed: Speed) -> Speed
}

enum Direction {
    case left, right, ahead, behind
}
```

**Property Wrapper:**

```swift
@HeadingStorage(key: "lastRunway", defaultValue: 270)
var runwayHeading: Heading
```

### Speed

Wind speed handling in knots.

```swift
struct Speed {
    var knots: Int                // Rounded integer storage
    var knotsDouble: Double       // Double precision access

    static func * (speed: Speed, percent: Percent) -> Speed
}
```

**Property Wrapper:**

```swift
@SpeedStorage(key: "lastWindSpeed", defaultValue: 10)
var windSpeed: Speed
```

### Percent

Percentage representation for wind component calculations.

```swift
struct Percent {
    var value: Double             // 0.0 to 1.0
    var displayString: String     // "45%"
}
```

---

## Database Layer

### KnownAirports

Airport database management with spatial indexing.

```swift
class KnownAirports {
    init(database: FMDatabase)

    // Query methods
    func airport(icao: String) -> Airport?
    func airports(country: String) -> [Airport]
    func nearestAirports(to: CLLocationCoordinate2D, count: Int) -> [Airport]
    func airports(within: Double, of: CLLocationCoordinate2D) -> [Airport]

    // Bulk loading
    func loadRunways(for airports: [Airport])
    func loadProcedures(for airports: [Airport])
    func loadAIPEntries(for airports: [Airport])

    // Advanced queries
    func airports(withApproachType: ApproachType) -> [Airport]
    func airports(withPrecisionApproach: Bool) -> [Airport]
    func airportsAlongRoute(from: Airport, to: Airport, corridor: Double) -> [Airport]
    func borderCrossingPoints(from: Airport, to: Airport) -> [BorderCrossingPoint]
}
```

**Filtering Extensions:**

```swift
extension Array where Element == Airport {
    func withMinRunwayLength(_ length: Int) -> [Airport]
    func withHardSurface() -> [Airport]
    func withLighting() -> [Airport]
    func inCountry(_ country: String) -> [Airport]
    func withProcedureType(_ type: ProcedureType) -> [Airport]
}
```

**Set Operations:**

```swift
let french = airports.inCountry("FR")
let german = airports.inCountry("DE")
let both = french.union(german)
let ilsOnly = airports.filter { $0.hasApproachType(.ILS) }
```

---

## Remote Services

### AVWX Integration

Weather API integration for METAR data.

```swift
struct AVWX {
    static func metar(
        icao: String,
        token: String,
        completion: @escaping (Result<Metar, Error>) -> Void
    )

    static func at(
        icao: String,
        token: String,
        completion: @escaping (Result<AVWXAirport, Error>) -> Void
    )

    static func near(
        latitude: Double,
        longitude: Double,
        token: String,
        completion: @escaping (Result<[AVWXStation], Error>) -> Void
    )
}
```

**Usage:**

```swift
AVWX.metar(icao: "LFPG", token: apiToken) { result in
    switch result {
    case .success(let metar):
        windModel.update(from: metar)
    case .failure(let error):
        print("METAR fetch failed: \(error)")
    }
}
```

### Metar

Weather observation data structure.

```swift
struct Metar: Codable {
    var windDirection: Int?       // Degrees (nil if variable)
    var windSpeed: Int            // Knots
    var gustSpeed: Int?           // Knots (nil if no gusts)
    var timestamp: Date           // Observation time

    var age: TimeInterval { get } // Seconds since observation
    var isStale: Bool { get }     // > 90 minutes old
}
```

---

## iOS-Specific Features

### Text-to-Speech

```swift
// Wind announcements
windModel.speakWindCheck()
// "Wind two seven zero at fifteen gusting twenty-two"

// ATC-style clearance
windModel.speakClearance(runway: "27L", altitude: 3000)
// "Runway two seven left, cleared for takeoff, climb three thousand"
```

### UIImage Extensions

```swift
// Wind direction indicator
let image = heading.uiImage  // SF Symbol arrow rotated to heading
```

---

## Example Usage

### Basic Wind Calculation

```swift
let wind = RunwayWindModel()
wind.windDirection = Heading(degrees: 270)
wind.windSpeed = Speed(knots: 15)
wind.runwayHeading = Heading(runway: "27")

print("Crosswind: \(wind.crosswindComponent.knots) kts")
print("Headwind: \(wind.headwindComponent.knots) kts")
```

### Airport Query

```swift
let db = try FMDatabase(path: databasePath)
let airports = KnownAirports(database: db)

// Find airports near Paris with ILS
let paris = CLLocationCoordinate2D(latitude: 48.8566, longitude: 2.3522)
let nearby = airports.nearestAirports(to: paris, count: 20)
    .withPrecisionApproach()
    .withMinRunwayLength(6000)

for airport in nearby {
    print("\(airport.icao): \(airport.name)")
}
```

### Best Runway Selection

```swift
let metar = try await AVWX.metar(icao: "LFPG", token: token)
let wind = RunwayWindModel()
wind.update(from: metar)

if let bestRunway = airport.bestRunway(for: wind) {
    print("Best runway: \(bestRunway.identifier)")
}
```

---

## Database Schema

The package expects a SQLite database with these tables:

```sql
CREATE TABLE airports (
    icao TEXT PRIMARY KEY,
    name TEXT,
    latitude REAL,
    longitude REAL,
    elevation INTEGER,
    country TEXT,
    continent TEXT,
    type TEXT
);

CREATE TABLE runways (
    id INTEGER PRIMARY KEY,
    airport_icao TEXT,
    low_ident TEXT, low_lat REAL, low_lon REAL, low_elev INTEGER, low_hdg REAL,
    high_ident TEXT, high_lat REAL, high_lon REAL, high_elev INTEGER, high_hdg REAL,
    length INTEGER, width INTEGER, surface TEXT, lighted INTEGER, closed INTEGER
);

CREATE TABLE procedures (
    id TEXT PRIMARY KEY,
    airport_icao TEXT,
    name TEXT,
    type TEXT,
    approach_type TEXT,
    runway TEXT
);

CREATE TABLE aip_entries (
    id TEXT PRIMARY KEY,
    airport_icao TEXT,
    section TEXT,
    field TEXT,
    value TEXT,
    alternative_value TEXT,
    mapping_score REAL
);
```

---

## Testing

```swift
// Test support utilities
import RZFlightTests

let testAirport = TestSupport.sampleAirport(icao: "TEST")
let testRunway = TestSupport.sampleRunway()
```

Run tests:
```bash
swift test
```
