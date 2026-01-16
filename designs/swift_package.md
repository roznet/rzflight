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

## Documentation

| Document | Audience | Contents |
|----------|----------|----------|
| [API Reference](swift_api_reference.md) | Library users | Complete public API, types, methods, usage examples |
| [Architecture Guide](swift_architecture.md) | Contributors | Internal structure, database schema, how to add features |

## Quick Overview

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

## Key Features

- **Wind Calculations** - Crosswind/headwind components, best runway selection
- **Spatial Queries** - Find nearest airports, airports along route, within bounding box
- **Procedure Data** - Approach types, precision categories, runway matching
- **AIP Integration** - Standardized field catalog, fuel availability, border crossings
- **METAR Support** - AVWX API integration, wind model updates
- **iOS Extras** - Text-to-speech clearances, SF Symbol direction indicators

## Quick Start

```swift
import RZFlight
import FMDB

// Load database
let db = FMDatabase(path: databasePath)
db.open()
let airports = KnownAirports(db: db)

// Find airport and load data
var airport = airports.airport(icao: "LFPG", ensureProcedures: true, ensureAIP: true)!

// Calculate wind
let model = RunwayWindModel()
model.windHeading = Heading(roundedHeading: 270)
model.windSpeed = Speed(roundedSpeed: 15)
model.runwayHeading = airport.bestRunway(wind: model.windHeading)

print("Crosswind: \(model.crossWindSpeed.descriptionWithUnit)")

// Filter airports
let filtered = airports.nearest(coord: airport.coord, count: 50)
    .withAvgas()
    .withPrecisionApproaches()
    .inCountry("FR")
```

## Testing

```bash
swift test
```
