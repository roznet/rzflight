# Swift Briefing Module

> Native Swift models for flight briefings, loaded from Python-generated JSON

## Intent

Provide Swift models that:
- Decode JSON from Python's `euro_aip.briefing` module
- Enable native NOTAM filtering in iOS/macOS apps
- Follow existing RZFlight patterns (Codable, Array extensions)

**What should NOT change**: Python handles parsing and categorization. Swift is read-only consumer of that JSON.

## Architecture

```
Sources/RZFlight/Briefing/
├── Notam.swift           # Core NOTAM model (Codable)
├── NotamCategory.swift   # Category enum matching Python
├── Route.swift           # Route + RoutePoint models
├── Briefing.swift        # Container with load() methods
└── Notam+Queries.swift   # [Notam] filtering extensions
```

**Data flow:**
```
Python                          Swift
──────                          ─────
ForeFlightSource.parse(pdf)
        │
        ▼
CategorizationPipeline()
        │
        ▼
briefing.to_json()  ─────────▶  Briefing.load(from: url)
                                        │
                                        ▼
                                briefing.notams
                                   .forAirport("LFPG")
                                   .runwayRelated()
```

## Usage Examples

### Load and Query
```swift
// Load from JSON file
let briefing = try Briefing.load(from: fileURL)

// Or from JSON string/data
let briefing = try Briefing.load(from: jsonString)

// Filter NOTAMs - chainable like Airport filters
let critical = briefing.notams
    .forAirport("LFPG")
    .activeNow()
    .runwayRelated()
```

### Time Window Filtering
```swift
// Flight planning: NOTAMs active during flight
if let window = briefing.route?.flightWindow(bufferMinutes: 60) {
    let relevant = briefing.notams.activeDuring(window.start, to: window.end)
}

// Or use convenience property
let flightNotams = briefing.flightWindowNotams
```

### Category and Tag Filtering
```swift
// By ICAO category (from Q-code)
let obstacles = briefing.notams.byCategory(.obstacle)

// By custom tags (from Python categorization pipeline)
let cranes = briefing.notams.byCustomTag("crane")
let ilsIssues = briefing.notams.byCustomTag("ils")

// Combine filters
let departureIssues = briefing.notams
    .forAirport(briefing.departure ?? "")
    .activeNow()
    .runwayRelated()
```

### Spatial Filtering
```swift
// Within radius of a point
let nearby = briefing.notams.withinRadius(of: coordinate, nm: 50)

// Near specific airports with known coordinates
let coords = ["LFPG": lfpgCoord, "EGLL": egllCoord]
let terminal = briefing.notams.nearAirports(["LFPG", "EGLL"], radiusNm: 30, coordinates: coords)
```

## Key Models

### Notam
| Field | Type | Description |
|-------|------|-------------|
| `id` | `String` | NOTAM ID (e.g., "A1234/24") |
| `location` | `String` | Primary ICAO |
| `message` | `String` | E) line content |
| `qCode` | `String?` | 5-letter Q-code |
| `category` | `NotamCategory?` | ICAO category enum |
| `effectiveFrom/To` | `Date?` | Validity window |
| `isPermanent` | `Bool` | No end date |
| `coordinate` | `CLLocationCoordinate2D?` | Location (computed) |
| `customCategories` | `[String]` | From Python pipeline |
| `customTags` | `[String]` | From Python pipeline |

### Route
| Field | Type | Description |
|-------|------|-------------|
| `departure` | `String` | Departure ICAO |
| `destination` | `String` | Destination ICAO |
| `alternates` | `[String]` | Alternate ICAOs |
| `departureTime` | `Date?` | Planned departure |
| `flightLevel` | `Int?` | Cruise FL |

Methods: `allAirports`, `flightWindow(bufferMinutes:)`, `coordinate(for:)`

### Briefing
| Field | Type | Description |
|-------|------|-------------|
| `id` | `String` | UUID |
| `source` | `String` | "foreflight", etc. |
| `route` | `Route?` | Flight route |
| `notams` | `[Notam]` | All NOTAMs |

Convenience: `departureNotams`, `destinationNotams`, `flightWindowNotams`

## Filter Methods on [Notam]

| Category | Methods |
|----------|---------|
| **Location** | `forAirport(_:)`, `forAirports(_:)`, `forFir(_:)` |
| **Time** | `activeNow()`, `activeAt(_:)`, `activeDuring(_:to:)`, `permanent()`, `temporary()` |
| **Category** | `byCategory(_:)`, `runwayRelated()`, `navigationRelated()`, `airspaceRelated()` |
| **Q-code** | `byQCode(_:)`, `byQCodePrefix(_:)`, `byTrafficType(_:)`, `byScope(_:)` |
| **Custom** | `byCustomCategory(_:)`, `byCustomTag(_:)`, `byPrimaryCategory(_:)` |
| **Altitude** | `belowAltitude(_:)`, `aboveAltitude(_:)`, `inAltitudeRange(_:to:)` |
| **Content** | `containing(_:)`, `matching(_:)` |
| **Spatial** | `withinRadius(of:nm:)`, `nearAirports(_:radiusNm:coordinates:)` |
| **Grouping** | `groupedByAirport()`, `groupedByCategory()`, `groupedByPrimaryCategory()` |

## Key Choices

| Decision | Rationale |
|----------|-----------|
| Array extensions not wrapper class | Matches Airport+Fuel pattern, chainable |
| ISO8601 date decoding | Matches Python `.isoformat()` output |
| Coordinates as `CLLocationCoordinate2D` | Native iOS integration |
| `load(from:)` static methods | Convenient JSON loading |
| Categories/tags come from JSON | No Swift-side categorization needed |

## Patterns

- **CodingKeys with snake_case**: All keys map to Python's `to_dict()` format
- **Optional defaults**: Arrays default to `[]`, strings to `""`
- **Computed CLLocationCoordinate2D**: From `[lat, lon]` arrays
- **Chainable filters**: All return `[Notam]`, can chain further

## Gotchas

- **Dates require ISO8601**: Python uses `.isoformat()`, Swift needs `.iso8601` decoder
- **Coordinates can be nil**: Many NOTAMs lack coords, spatial filters skip them
- **Category enum must match Python**: `NotamCategory` raw values match Python's
- **No parsing in Swift**: All NOTAM text processing happens in Python

## References

- Python briefing: [briefing.md](./briefing.md), [briefing_models.md](./briefing_models.md)
- Swift patterns: [swift_architecture.md](./swift_architecture.md)
- Code: `Sources/RZFlight/Briefing/`
