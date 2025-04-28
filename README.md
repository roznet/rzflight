# RZFlight

RZFlight is a collection of libraries for flight planning and aviation data processing. It consists of two main components:

## Swift Package: RZFlight

A Swift library for flight planning and aviation data management. This package provides:

- Aviation data structures and models
- Integration with various aviation data sources
- Utilities for flight calculations and conversions

For detailed information about the Swift package, see [README-Swift.md](README-Swift.md).

## Python Package: euro_aip

A Python library for parsing and processing European AIP (Aeronautical Information Publication) documents. This package provides:

- Parsers for different European AIP formats
- Extraction of airport information
- Processing of aviation documentation
- Integration with flight planning systems

For detailed information about the Python package, see [euro_aip/README.md](euro_aip/README.md).

## Installation

### Swift Package

Add the package to your Xcode project using Swift Package Manager:

```swift
dependencies: [
    .package(url: "https://github.com/yourusername/rzflight.git", from: "1.0.0")
]
```

### Python Package

Install using pip:

```bash
pip install euro-aip
```

## Contributing

Contributions are welcome! Please read our [Contributing Guidelines](CONTRIBUTING.md) for details on our code of conduct and the process for submitting pull requests.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Airport and Metar information

It can retrieve information for web services

## Runway, heading and speed

It can do different calculations on runway, heading and speed



