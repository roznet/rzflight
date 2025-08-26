# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

### Testing
- `make test` - Run all tests with pytest
- `make test-cov` - Run tests with coverage report
- `make test-cov-html` - Run tests with HTML coverage report
- `pytest -v` - Direct pytest execution with verbose output

### Code Quality
- `black euro_aip/` - Format code with Black (line length: 88)
- `mypy euro_aip/` - Type checking
- `flake8 euro_aip/` - Linting

### Cleaning
- `make clean` - Clean cache files, coverage reports, and __pycache__ directories

### Installation
- `pip install -e .` - Install package in development mode
- `pip install -r requirements.txt` - Install basic dependencies
- `pip install -e .[dev]` - Install with development dependencies

## Architecture Overview

### Core Components
The codebase follows a modular architecture with clear separation of concerns:

**Models** (`euro_aip/models/`):
- `EuroAipModel`: Central data store managing airports, border crossing points, and metadata
- `Airport`: Core airport entity with ICAO codes, coordinates, runways, and AIP entries
- `Runway`: Runway information with surface types, dimensions, and lighting
- `AIPEntry`: Aeronautical Information Publication data entries
- `Procedure`: Approach and departure procedures
- `BorderCrossingEntry`: Border crossing point information
- `NavPoint`: Navigation points with coordinate calculations

**Data Sources** (`euro_aip/sources/`):
- `DatabaseSource`: Direct SQLite database access for precomputed data
- `AutorouterSource`: European AIP data via Autorouter API
- `FranceEAIPSource`: French official AIP documents
- `UKEAIPSource`: UK official AIP documents
- `WorldAirportsSource`: OurAirports comprehensive database
- `BorderCrossingSource`: Specialized border crossing data

**Parsers** (`euro_aip/parsers/`):
- `AIPParserFactory`: Creates country-specific AIP parsers (LEC, EBC, ESC, LFC, LIC, LKC, EKC, EGC)
- `ProcedureParserFactory`: Creates procedure parsers for different authorities
- Country-specific parsers handle PDF and HTML formats with dual-format support for UK (EGC)

**Storage** (`euro_aip/storage/`):
- `DatabaseStorage`: SQLite persistence layer
- Field definitions and standardization services

**Utilities** (`euro_aip/utils/`):
- `FieldStandardizationService`: Standardizes field names and values across sources
- Geographic calculations and coordinate transformations
- Fuzzy matching for airport names and data reconciliation
- Country mapping and runway classification

### Data Flow
1. **Sources** fetch raw data from APIs, databases, or documents
2. **Parsers** extract and structure AIP information by authority
3. **Models** provide typed representations of aviation data
4. **Storage** persists processed data to SQLite database
5. **Utilities** handle data standardization and geographic calculations

### Key Design Patterns
- **Factory Pattern**: AIP and procedure parser creation based on authority codes
- **Strategy Pattern**: Different parsing strategies for PDF vs HTML sources
- **Repository Pattern**: DatabaseSource provides data access abstraction
- **Builder Pattern**: ModelBuilder assembles EuroAipModel from multiple sources

## Key Files and Entry Points

### Main Scripts (`example/`)
- `aipexport.py`: Primary data export tool supporting JSON, CSV, and database formats
- `bordercrossingexport.py`: Export border crossing data
- `foreflight.py`: ForeFlight-compatible data export

### Database Schema
The SQLite database (`airports.db`) contains standardized tables for airports, runways, procedures, and border crossings with foreign key relationships.

### Web Application (`web/`)
- `web/server/main.py`: FastAPI server with REST endpoints
- `web/client/index.html`: Leaflet.js interactive map interface
- API endpoints include filtering, route search, and statistics

## Authority Codes and Parsers
The system supports multiple European aviation authorities:
- `EGC`: United Kingdom (dual HTML/PDF parsing)
- `LFC`: France
- `LEC`: Spain
- `EBC`: Belgium
- `ESC`: Sweden
- `LIC`: Italy
- `LKC`: Czech Republic
- `EKC`: Denmark

## Testing Strategy
Tests are organized by component in `tests/` with separate directories for models, parsers, sources, storage, and utils. The test suite includes integration tests for database operations and field standardization.