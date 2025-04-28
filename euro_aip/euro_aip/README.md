# Euro AIP

A Python library for parsing and processing European AIP (Aeronautical Information Publication) documents and airport data.

## Features

- Parse AIP documents from various European authorities
- Extract structured data from PDF documents
- Process airport and runway information
- Support for multiple languages (original and alternative text)
- Data persistence in multiple formats (JSON, CSV, SQLite)

## Installation

1. Create and activate a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install the package:
```bash
pip install -e .
```

## Usage

### Example Script

The library includes an example script `example/aip.py` that demonstrates the main functionality:

```bash
# Download and process World Airports data
python example/aip.py worldairports

# Parse AIP documents from Autorouter (requires credentials)
python example/aip.py autorouter -u username -p password EGKB LFAT 

# Parse France eAIP data from local directories
python example/aip.py france_eaip -r /path/to/eaip LFMD LFAT
```

The script supports three main commands:
- `worldairports`: Downloads and processes airport data from OurAirports
- `autorouter`: Downloads and parses AIP documents from Autorouter API
- `france_eaip`: Parses AIP documents from local France eAIP directories

Additional options:
- `-c, --cache-dir`: Directory to cache files (default: 'cache')
- `-v, --verbose`: Enable verbose output
- `-f, --force-refresh`: Force refresh of cached data

### Basic Example

```python
from euro_aip.parsers import AIPParserFactory
from euro_aip.models import AIPEntry, Airport, Runway
from euro_aip.sources import WorldAirportsSource

# Initialize the airport data source
airport_source = WorldAirportsSource(cache_dir='cache')

# Get airport database
db_info = airport_source.get_airport_database()

# Parse an AIP document
parser = AIPParserFactory.get_parser('LFC')  # For French AIP
with open('path/to/document.pdf', 'rb') as f:
    pdf_data = f.read()
    results = parser.parse(pdf_data, 'LFAT')  # Parse for Le Touquet airport

# Print results in a table format
AIPParserFactory.pretty_print_results(results)
```

### Data Models

The library provides three main data models:

1. `AIPEntry`: Stores parsed AIP information
   - Original and alternative language fields
   - Section information (admin, operational, handling, passenger)

2. `Airport`: Stores airport information
   - Basic airport details (name, location, etc.)
   - Relationships to runways and AIP entries

3. `Runway`: Stores runway information
   - Physical characteristics (length, width, surface)
   - End information (coordinates, headings, etc.)

### Data Persistence

The library supports multiple storage formats:

```python
from euro_aip.models.persistence import PersistenceManager

# Save to JSON
PersistenceManager.save_json(airports, 'airports.json')

# Save to CSV
PersistenceManager.save_csv(airports, 'airports.csv')

# Save to SQLite
PersistenceManager.save_sqlite(airports, 'airports.db', 'airports')

# Load from any format
airports = PersistenceManager.load_json('airports.json', Airport)
```

## Development

### Running Tests

```bash
pytest tests/
```

### Project Structure

```
euro_aip/
├── models/          # Data models and persistence
├── parsers/         # AIP document parsers
├── sources/         # Data sources (airports, runways)
└── tests/           # Test suite
```

## License

This project is licensed under the MIT License - see the LICENSE file for details. 