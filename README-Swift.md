# RZFlight Swift Package

The RZFlight Swift package provides a comprehensive set of tools for aviation calculations and data management in Swift applications.

## Features

### Wind and Runway Calculations
- Crosswind and headwind component calculations
- Runway selection based on wind conditions
- Wind direction and speed handling
- Magnetic and true heading conversions
- Wind gust handling

### Airport Information
- Airport data management (ICAO, name, location, elevation)
- Runway information (length, width, surface, headings)
- Airport search and matching
- Nearest airport finding
- French PPL airport filtering

### Weather Integration
- METAR data parsing and handling
- Wind information processing
- Weather data age tracking
- Remote weather service integration (AVWX)

### Data Structures
- Heading calculations and conversions
- Speed handling with units
- Percentage calculations
- Geographic coordinate management
- Magnetic declination calculations

## Installation

### Swift Package Manager

Add the package to your Xcode project:

```swift
dependencies: [
    .package(url: "https://github.com/yourusername/rzflight.git", from: "1.0.0")
]
```

### Manual Installation

1. Clone the repository
2. Add the package to your Xcode project
3. Link against the RZFlight framework

## Usage

### Wind Calculations Example

```swift
import RZFlight

// Create a runway wind model
let model = RunwayWindModel(
    runway: Heading(roundedHeading: 240),
    wind: Heading(roundedHeading: 190),
    speed: Speed(roundedSpeed: 10)
)

// Get wind components
let crosswind = model.crossWindComponent
let headwind = model.headWindComponent
print("Crosswind: \(crosswind.description)")
print("Headwind: \(headwind.description)")
```

### Airport Information Example

```swift
// Get airport information
let airport = Airport(icao: "LFBO")
print("Name: \(airport.name)")
print("Location: \(airport.coord)")
print("Runways: \(airport.runways.count)")

// Find best runway for wind
let windHeading = Heading(roundedHeading: 190)
let bestRunway = airport.bestRunway(wind: windHeading)
print("Best runway: \(bestRunway.runwayDescription)")
```

## Requirements

- iOS 13.0+ / macOS 10.15+
- Swift 5.0+
- Xcode 12.0+

## Contributing

Contributions are welcome! Please read our [Contributing Guidelines](CONTRIBUTING.md) for details on our code of conduct and the process for submitting pull requests.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details. 