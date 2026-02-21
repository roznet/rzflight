# Swift Briefing Module

> Native Swift parsing and models for flight briefings

## Intent

Provide Swift capabilities for:
- **Native PDF parsing** - Parse ForeFlight PDFs directly in iOS/macOS (no server needed)
- **JSON loading** - Decode briefings from Python's `euro_aip.briefing` module
- **NOTAM filtering** - Chainable filter extensions matching Python's API
- **Cross-platform consistency** - Same parsing logic as Python, same JSON format

## Cross-Platform Consistency

**CRITICAL**: Swift and Python parsers MUST produce identical output.

Both implementations share:
- `q_codes.json` - Q-code meanings
- `document_references.json` - AIP supplement URL patterns

When modifying parsing:
1. Update BOTH `NotamParser.swift` AND `notam_parser.py`
2. Update BOTH `DocumentReferenceExtractor` implementations
3. Ensure JSON output matches

## Architecture

```
Sources/RZFlight/Briefing/
├── ForeFlightParser.swift        # Native PDF parsing (PDFKit)
├── NotamParser.swift             # NOTAM text parsing
├── QCodeLookup.swift             # Q-code meanings from JSON
├── DocumentReferenceExtractor.swift  # AIP supplement & AIC links
├── DocumentReference.swift       # Reference model
├── Notam.swift                   # Core NOTAM model (Codable)
├── NotamCategory.swift           # Category enum matching Python
├── Route.swift                   # Route + RoutePoint models
├── Briefing.swift                # Container with load/parse methods
├── Notam+Queries.swift           # [Notam] filtering extensions
└── Route+Geometry.swift         # Route projection & NOTAM classification

Resources/
├── q_codes.json                  # Shared with Python
└── document_references.json      # Shared with Python
```

**Two data paths:**
```
Option 1: Native Parsing (iOS/macOS)
────────────────────────────────────
ForeFlight PDF
      │
      ▼
ForeFlightParser.parse(url:)
      │
      ├─▶ NotamParser (Q-line, dates, location)
      ├─▶ QCodeLookup (human-readable meanings)
      └─▶ DocumentReferenceExtractor (AIP supplement & AIC links)
      │
      ▼
Briefing with [Notam]

Option 2: Load from Python JSON
───────────────────────────────
Python ForeFlightSource.parse()
      │
      ▼
briefing.to_json()
      │
      ▼
Briefing.load(from: jsonURL)
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
let obstacles = briefing.notams.byCategory(.otherInfo)  // Obstacles fall under OTHER_INFO

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
| `qCodeInfo` | `QCodeInfo?` | Parsed Q-code meanings |
| `category` | `NotamCategory?` | ICAO category enum |
| `effectiveFrom/To` | `Date?` | Validity window |
| `isPermanent` | `Bool` | No end date |
| `coordinate` | `CLLocationCoordinate2D?` | Location (computed) |
| `customCategories` | `[String]` | From categorization pipeline |
| `customTags` | `[String]` | From categorization pipeline |
| `documentReferences` | `[DocumentReference]` | AIP supplement links |

### QCodeInfo
| Field | Type | Description |
|-------|------|-------------|
| `qCode` | `String` | Raw Q-code (e.g., "QMRLC") |
| `subjectMeaning` | `String` | Subject meaning (e.g., "Runway") |
| `conditionMeaning` | `String` | Condition meaning (e.g., "Closed") |
| `displayText` | `String` | Combined (e.g., "Runway: Closed") |
| `shortText` | `String` | Short form (e.g., "RWY CLSD") |

### DocumentReference
| Field | Type | Description |
|-------|------|-------------|
| `type` | `String` | Document type: `"aip_supplement"`, `"aic"`, etc. |
| `identifier` | `String` | Reference ID (e.g., "SUP 059/2025", "AIC Y 148/2025") |
| `provider` | `String` | Provider ID (e.g., "uk_nats", "uk_nats_aic") |
| `providerName` | `String` | Human name |
| `searchURL` | `URL?` | Generic search page |
| `documentURLs` | `[URL]` | Direct PDF links |

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
| **Spatial** | `withinRadius(of:nm:)`, `nearAirports(_:radiusNm:coordinates:)` |
| **Grouping** | `groupedByAirport()`, `groupedByCategory()`, `groupedByPrimaryCategory()` |
| **Route** | `classifyForRoute(_:)`, `groupedByRouteSegment(route:)` |

## Key Choices

| Decision | Rationale |
|----------|-----------|
| Native PDF parsing | iOS apps can work offline without server |
| Shared JSON configs | `q_codes.json`, `document_references.json` ensure consistency |
| Array extensions not wrapper class | Matches Airport+Fuel pattern, chainable |
| ISO8601 date decoding | Matches Python `.isoformat()` output |
| Coordinates as `CLLocationCoordinate2D` | Native iOS integration |
| `load(from:)` and `parse(url:)` methods | Support both JSON and PDF input |

## Patterns

- **CodingKeys with snake_case**: All keys map to Python's `to_dict()` format
- **Optional defaults**: Arrays default to `[]`, strings to `""`
- **Computed CLLocationCoordinate2D**: From `[lat, lon]` arrays
- **Chainable filters**: All return `[Notam]`, can chain further
- **Bundle.module resources**: Load JSON configs from package bundle

## Gotchas

- **Keep parsers in sync**: Swift NotamParser must match Python NotamParser output
- **Shared config files**: `q_codes.json` and `document_references.json` must be identical
- **Dates require ISO8601**: Python uses `.isoformat()`, Swift needs `.iso8601` decoder
- **Coordinates can be nil**: Many NOTAMs lack coords, spatial filters skip them
- **Category enum must match Python**: `NotamCategory` raw values match Python's

## References

- Python briefing: [briefing.md](./briefing.md), [briefing_models.md](./briefing_models.md)
- Swift patterns: [swift_architecture.md](./swift_architecture.md)
- Code: `Sources/RZFlight/Briefing/`
