# RZFlight Swift API Reference

> Complete API documentation for library users.

**Platforms:** iOS 15+, macOS 12+
**Swift Version:** 5.5+

---

## Installation

```swift
dependencies: [
    .package(url: "https://github.com/roznet/rzflight", from: "1.0.0")
]
```

---

## Core Data Models

### Airport

The central data structure representing an airport with all associated data.

```swift
public struct Airport: Codable, Hashable, Equatable, Identifiable {
    // Identifiers
    public let icao: String              // ICAO code (e.g., "LFPG")
    public let name: String
    public let city: String
    public let country: String           // ISO country code
    public let continent: Continent      // AF, AN, AS, EU, NA, OC, SA
    public let type: AirportType         // large_airport, medium_airport, small_airport, closed, etc.
    public let elevation_ft: Int

    // Optional metadata
    public let isoRegion: String?
    public let iataCode: String?
    public let gpsCode: String?
    public let localCode: String?
    public let homeLink: String?
    public let wikipediaLink: String?
    public let sources: [String]
    public let createdAt: Date?
    public let updatedAt: Date?

    // Related data (loaded lazily)
    public var runways: [Runway]
    public var procedures: [Procedure]
    public var aipEntries: [AIPEntry]

    // Computed
    public var coord: CLLocationCoordinate2D
    public var id: String  // Same as icao
}
```

**Airport Types:**
```swift
public enum AirportType: String, Codable {
    case none, balloonport, closed, large_airport, medium_airport, seaplane_base, small_airport
}

public enum Continent: String, Codable {
    case none, AF, AN, AS, EU, NA, OC, SA
}
```

#### Runway Selection

```swift
// Get best runway for given wind direction
let bestHeading = airport.bestRunway(wind: Heading(degrees: 270))
```

#### Procedure Access

```swift
// Filtered procedure lists
airport.approaches      // All approach procedures
airport.departures      // All departure procedures
airport.arrivals        // All arrival procedures

// Procedures for specific runway
airport.procedures(for: runway)
airport.procedures(for: "27L")
airport.approaches(for: runway)

// Most precise approach
airport.mostPreciseApproach(for: runway)
airport.mostPreciseApproach(for: "27L")
airport.mostPreciseApproach(for: runwayEnd)
```

#### AIP Entry Access

```swift
// By section
airport.aipEntries(for: .operational)
airport.aipEntries(for: .admin)

// Standardized entries only
airport.standardizedAIPEntries

// Specific field lookup
airport.aipEntry(for: "Fuel", useStandardized: true)
```

#### Fuel Availability

```swift
// Check fuel types
airport.hasAvgas     // AVGAS / 100LL available
airport.hasJetA      // Jet-A / JetA1 available
```

#### Border Crossing

```swift
// Requires database context
airport.isBorderCrossing(db: database)
airport.hasCustoms(db: database)
```

#### Procedure Visualization

For map overlays, get procedure line data:

```swift
let result = airport.procedureLines(distanceNm: 10.0)
// Returns ProcedureLinesResult with:
//   - airportIdent: String
//   - procedureLines: [ProcedureLine]

// Each ProcedureLine contains:
struct ProcedureLine: Codable {
    let runwayEnd: String
    let startCoordinate: CLLocationCoordinate2D
    let endCoordinate: CLLocationCoordinate2D
    let approachType: Procedure.ApproachType
    let procedureName: String
    let precisionCategory: Procedure.PrecisionCategory
    let distanceNm: Double
}
```

#### Magnetic/True Heading Conversion

```swift
let magneticHeading = airport.magneticHeading(from: trueHeading)
let trueHeading = airport.trueHeading(from: magneticHeading)
```

---

### Runway

```swift
public struct Runway: Codable {
    public var length_ft: Int
    public var width_ft: Int
    public var surface: String           // "asphalt", "concrete", "grass", etc.
    public var lighted: Bool
    public var closed: Bool

    public var le: RunwayEnd             // Low-numbered end
    public var he: RunwayEnd             // High-numbered end

    // Computed properties
    public var hasCoordinates: Bool
    public var leCoordinate: CLLocationCoordinate2D?
    public var heCoordinate: CLLocationCoordinate2D?
    public var isHardSurface: Bool       // asphalt, concrete, paved, hard
    public var trueHeading1: Heading
    public var trueHeading2: Heading
}

public struct RunwayEnd: Codable {
    public let ident: String             // "09", "27L", etc.
    public let latitude: Double?
    public let longitude: Double?
    public let elevationFt: Double?
    public let headingTrue: Double
    public let displacedThresholdFt: Double?

    public var coordinate: CLLocationCoordinate2D?
}
```

---

### Procedure

```swift
public struct Procedure: Codable, Hashable, Equatable, Identifiable {
    public let name: String
    public let procedureType: ProcedureType
    public let approachType: ApproachType?
    public let runwayNumber: String?
    public let runwayLetter: String?
    public let runwayIdent: String?
    public let source: String?
    public let authority: String?

    // Computed
    public var fullRunwayIdent: String?   // e.g., "13L"
    public var isApproach: Bool
    public var isDeparture: Bool
    public var isArrival: Bool
    public var precisionCategory: PrecisionCategory

    // Methods
    public func matches(runway: Runway) -> Bool
    public func matches(runwayIdent: String) -> Bool
    public func isMorePreciseThan(_ other: Procedure) -> Bool
}
```

**Enums:**
```swift
public enum ProcedureType: String, Codable {
    case approach, departure, arrival
}

public enum ApproachType: String, Codable {
    case ils = "ILS"
    case rnp = "RNP"
    case rnav = "RNAV"
    case vor = "VOR"
    case ndb = "NDB"
    case loc = "LOC"
    case lda = "LDA"
    case sdf = "SDF"

    public var precisionRank: Int        // 1 = most precise (ILS)
    public var precisionCategory: PrecisionCategory
}

public enum PrecisionCategory: String, Codable {
    case precision      // ILS
    case rnav           // RNAV, RNP
    case nonPrecision   // VOR, NDB, LOC, etc.
}
```

---

### AIPEntry

Aeronautical Information Publication entries.

```swift
public struct AIPEntry: Codable, Hashable, Equatable, Identifiable {
    public let ident: String             // Airport ICAO
    public let section: Section
    public let field: String             // Raw field name
    public let value: String
    public let standardField: AIPField?  // Standardized field (if mapped)
    public let mappingScore: Double?
    public let altField: String?
    public let altValue: String?
    public let source: String?

    // Computed
    public var isStandardized: Bool
    public var effectiveFieldName: String  // Standard name or raw
    public var effectiveValue: String      // Alt value or main value
    public var displayDescription: String
}

public enum Section: String, Codable {
    case admin, operational, handling, passenger

    public var displayName: String       // "Administrative", etc.
}
```

**Field Standardization:**
```swift
// Configure custom field catalog (e.g., for testing)
AIPEntry.AIPFieldCatalog.setOverrideURL(customURL)

// Lookup standardized field
let field = AIPEntry.AIPFieldCatalog.field(for: fieldId)
```

---

## Calculation Models

### RunwayWindModel

Primary wind calculation engine.

```swift
public class RunwayWindModel: NSObject {
    public var runwayHeading: Heading
    public var windHeading: Heading
    public var windSpeed: Speed
    public var windGust: Speed?
    public var windSource: String?
    public var windSourceDate: Date?

    // Computed wind components
    public var crossWindComponent: Percent
    public var crossWindSpeed: Speed
    public var headWindComponent: Percent
    public var headWindSpeed: Speed
    public var directWindDirection: Heading.Direction
    public var crossWindDirection: Heading.Direction
    public var windRunwayOffset: Heading

    // Display strings
    public var windDisplay: String       // "270 @ 15"
    public var announce: String          // "2 7 0 at 1 5"
    public var windcheck: String         // "Wind: 2 7 0 at 1 5"
    public var clearance: String         // Full ATC clearance
}
```

**Initialization:**
```swift
// Default
let model = RunwayWindModel()

// With specific values
let model = RunwayWindModel(
    runway: Heading(roundedHeading: 270),
    wind: Heading(roundedHeading: 250),
    speed: Speed(roundedSpeed: 15),
    gust: Speed(roundedSpeed: 22)
)
```

**Update from METAR:**
```swift
model.setupFrom(metar: metar, airport: airport)
model.setupFrom(metar: metar, icao: "LFPG")

// Check if already refreshed (within 10 minutes)
if !model.alreadyRefreshed(icao: "LFPG") {
    // Fetch new METAR
}
```

**Modify Wind:**
```swift
model.randomizeWind()
model.rotateWind(degree: 10)
model.increaseWind(speed: 5, maximumSpeed: 75)
model.opposingRunway()
model.rotateHeading(degree: 10)
```

**Text-to-Speech (iOS only):**
```swift
model.speak(which: .clearance) {
    // Completion handler
}
model.speak(which: .windcheck)
```

---

### Heading

Compass heading with automatic 0-360 normalization.

```swift
public struct Heading: Equatable {
    public var heading: Double           // 0-360 degrees
    public var roundedHeading: Int

    // Display
    public var description: String       // "270" (or "360" for 0)
    public var descriptionWithUnit: String  // "270°"
    public var runwayDescription: String // "27"

    public var opposing: Heading         // 180° opposite

    // Direction relative to another heading
    func directDirection(to other: Heading) -> Direction
    func crossDirection(to other: Heading) -> Direction

    // Wind components
    func crossWindComponent(with other: Heading) -> Percent
    func headWindComponent(with other: Heading) -> Percent

    mutating func rotate(degree: Int)
}

public enum Direction {
    case left, right, ahead, behind

    var arrow: String      // Unicode arrows
    var description: String // "Left", "Right", etc.
    var image: UIImage?    // SF Symbols (iOS only)
}
```

**Initialization:**
```swift
Heading(roundedHeading: 270)
Heading(heading: 273.5)
Heading(runwayDescription: "27")
Heading(description: "270")
```

**Property Wrapper:**
```swift
@HeadingStorage(key: "lastRunway", defaultValue: Heading(roundedHeading: 270))
var savedHeading: Heading
```

---

### Speed

Wind speed in knots.

```swift
public struct Speed {
    public var speed: Double
    public var roundedSpeed: Int

    public var description: String         // "15"
    public var descriptionWithUnit: String // "15kts"

    mutating func increase(speed: Int)
    mutating func cap(at: Int)

    static func * (speed: Speed, percent: Percent) -> Speed
}
```

**Property Wrapper:**
```swift
@SpeedStorage(key: "lastWindSpeed", defaultValue: Speed(roundedSpeed: 10))
var savedSpeed: Speed
```

---

### Percent

```swift
public struct Percent {
    public var percent: Double   // 0.0 to 1.0 (1.0 = 100%)
    public var description: String  // "45%"

    public init(percent: Double)     // 0.45 for 45%
    public init(rounded: Int)        // 45 for 45%
}
```

---

## Database Layer

### KnownAirports

Airport database with spatial indexing (KDTree).

```swift
public class KnownAirports {
    public init(db: FMDatabase, where: String? = nil)

    // Single airport queries
    public func airport(icao: String, ensureRunway: Bool = true) -> Airport?
    public func airport(icao: String,
                       ensureRunway: Bool = true,
                       ensureProcedures: Bool = false,
                       ensureAIP: Bool = false) -> Airport?
    public func airportWithExtendedData(icao: String) -> Airport?

    // Nearest queries (uses KDTree)
    public func nearestAirport(coord: CLLocationCoordinate2D) -> Airport?
    public func nearest(coord: CLLocationCoordinate2D, count: Int) -> [Airport]
    public func nearestMatching(coord: CLLocationCoordinate2D, needle: String, count: Int) -> [Airport]

    // Search
    public func matching(needle: String) -> [Airport]
    public func airportsWithinBox(minCoord: CLLocationCoordinate2D, maxCoord: CLLocationCoordinate2D) -> [Airport]

    // Approach queries
    public func airportsWithApproach(_ approachType: Procedure.ApproachType,
                                    near coord: CLLocationCoordinate2D,
                                    within distanceKm: Double,
                                    limit: Int = 10) -> [Airport]
    public func airportsWithPrecisionApproaches(near coord: CLLocationCoordinate2D,
                                               within distanceKm: Double,
                                               limit: Int = 10) -> [Airport]

    // AIP queries
    public func airportsWithAIPField(_ fieldName: String, useStandardized: Bool = true) -> [Airport]

    // Border crossing
    public func airportsWithBorderCrossing() -> [Airport]
    public func airportsWithBorderCrossing(near coord: CLLocationCoordinate2D,
                                          within distanceKm: Double,
                                          limit: Int = 10) -> [Airport]

    // Route queries
    public func airportsNearRoute(_ routeAirports: [String], within distanceNm: Double) -> [Airport]

    // Bulk loading (efficient for large operations)
    public func loadAllRunways()
    public func loadAllProcedures()
    public func loadAllAIPEntries()
    public func loadAllBorderCrossing()
    public func loadAllExtendedData()   // Loads everything
}
```

---

## Array Filter Extensions

Chainable filters for `[Airport]`:

```swift
airports
    .inCountry("FR")
    .withRunwayLength(minimumFeet: 3000)
    .withRunwayLength(minimumFeet: 3000, maximumFeet: 8000)
    .withHardRunways()
    .withLightedRunways()
    .withProcedures()
    .withApproaches()
    .withPrecisionApproaches()
    .withAvgas()
    .withJetA()
    .matching("Paris")
    .borderCrossingOnly(db: database)
```

---

## Remote Services

### AVWX Integration

Weather API for METAR data. Requires API token via `Secrets.shared["avwx"]`.

```swift
// Fetch METAR (callback-based)
AviationRemoteService.AVWX.metar(icao: "LFPG") { metar, icao in
    if let metar = metar {
        model.setupFrom(metar: metar, icao: icao)
    }
}

// Get station info
AviationRemoteService.AVWX.at(icao: "LFPG") { airport in
    // Airport data from AVWX
}

// Find nearby stations
AviationRemoteService.AVWX.near(coord: coordinate, count: 5, reporting: true) { airports in
    // List of nearby airports with weather reporting
}
```

### Metar

```swift
public struct Metar: Decodable {
    var time: Time
    var wind_direction: Value
    var wind_speed: Value
    var gust_speed: Value?

    var ageInMinutesIfLessThanOneHour: Int?  // nil if > 1 hour old

    static func metar(json: Data) throws -> Metar
}
```

---

## Coordinate Extensions

```swift
extension CLLocationCoordinate2D {
    /// Calculate point at bearing and distance (great circle)
    func pointFromBearingDistance(bearing: Double, distanceNm: Double) -> CLLocationCoordinate2D
}
```

---

## iOS-Specific Features

### Direction Images

```swift
// SF Symbol images for wind direction indicators
let image = Heading.Direction.left.image   // arrow.left
let image = Heading.Direction.right.image  // arrow.right
let image = Heading.Direction.ahead.image  // arrow.down
let image = Heading.Direction.behind.image // arrow.up
```

### Text-to-Speech

See `RunwayWindModel.speak(which:completion:)` above.

---

## Usage Examples

### Basic Wind Calculation

```swift
let model = RunwayWindModel()
model.runwayHeading = Heading(roundedHeading: 270)
model.windHeading = Heading(roundedHeading: 250)
model.windSpeed = Speed(roundedSpeed: 15)

print("Crosswind: \(model.crossWindSpeed.descriptionWithUnit)")  // "5kts"
print("Headwind: \(model.headWindSpeed.descriptionWithUnit)")    // "14kts"
print("Direction: \(model.crossWindDirection.description)")      // "Left"
```

### Find Airports with Fuel

```swift
let db = FMDatabase(path: databasePath)
let airports = KnownAirports(database: db)
airports.loadAllAIPEntries()

let avgasAirports = airports.matching(needle: "")
    .inCountry("FR")
    .withAvgas()
```

### Route Planning

```swift
// Find airports along route with border crossing
let route = ["LFPG", "EGLL"]
let nearRoute = airports.airportsNearRoute(route, within: 50.0)
    .borderCrossingOnly(db: db.db)
    .withPrecisionApproaches()
```

### Best Runway with Weather

```swift
AviationRemoteService.AVWX.metar(icao: airport.icao) { metar, _ in
    guard let metar = metar else { return }

    let windHeading = Heading(roundedHeading: metar.wind_direction.value)
    let bestRunway = airport.bestRunway(wind: windHeading)

    print("Use runway \(bestRunway.runwayDescription)")
}
```
