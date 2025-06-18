# Euro AIP

A Python library for parsing and processing European AIP (Aeronautical Information Publication) documents and airport data from multiple sources.

## Features

- **Multiple Data Sources**: Support for various European AIP sources
  - Autorouter API (requires credentials)
  - France eAIP (local HTML/PDF files)
  - UK eAIP (local HTML/PDF files)
  - World Airports database
  - Point de Passage journal processing
- **Flexible Parser System**: Automatic format detection (HTML/PDF) with dual-format parsing
- **Structured Data Extraction**: Parse AIP documents into organized data structures
- **Caching System**: Efficient caching with refresh control options
- **Database Integration**: SQLite database support for data persistence
- **Multi-language Support**: Handle original and alternative language content

## Installation

1. Create and activate a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  
```

2. Install the package:
```bash
pip install -e .
```

## Usage

### Command Line Interface

The library includes a comprehensive command-line interface `example/aip.py` that supports multiple data sources:

```bash
# Download and process World Airports data
python example/aip.py worldairports

# Parse AIP documents from Autorouter (requires credentials)
python example/aip.py autorouter -u username -p password EGKB LFAT 

# Parse France eAIP data from local directories
python example/aip.py france_eaip -r /path/to/france_eaip LFMD LFAT

# Parse UK eAIP data from local directories
python example/aip.py uk_eaip -r /path/to/uk_eaip EGLL EGKB

# Process Point de Passage journal PDF
python example/aip.py pointdepassage -j /path/to/journal.pdf

# Query the database
python example/aip.py querydb -w "runway_length > 2000"
```

### Available Commands

| Command | Description | Required Arguments |
|---------|-------------|-------------------|
| `autorouter` | Download and parse AIP documents from Autorouter API | `-u username -p password` |
| `france_eaip` | Parse France eAIP data from local directories | `-r root_dir` |
| `uk_eaip` | Parse UK eAIP data from local directories | `-r root_dir` |
| `worldairports` | Download and process World Airports database | None |
| `pointdepassage` | Process Point de Passage journal PDF | `-j journal_path` |
| `querydb` | Query the database with SQL WHERE clause | `-w where_clause` |

### Command Line Options

- `-c, --cache-dir`: Directory to cache files (default: 'cache')
- `-r, --root-dir`: Root directory for eAIP data (required for france_eaip and uk_eaip)
- `-u, --username`: Autorouter username (required for autorouter)
- `-p, --password`: Autorouter password (required for autorouter)
- `-d, --database`: SQLite database file (default: 'airports.db')
- `-j, --journal-path`: Path to Point de Passage journal PDF file
- `-w, --where`: SQL WHERE clause for database query
- `-v, --verbose`: Enable verbose output
- `-f, --force-refresh`: Force refresh of cached data
- `-n, --never-refresh`: Never refresh cached data if it exists

### Data Sources

#### Autorouter API
Downloads AIP documents and procedures from the Autorouter API.
```bash
python example/aip.py autorouter -u your_username -p your_password EGKB LFAT
```

#### France eAIP
Parses France eAIP data from local directories. Download from [SIA website](https://www.sia.aviation-civile.gouv.fr/produits-numeriques-en-libre-disposition/eaip.html).
```bash
python example/aip.py france_eaip -r /path/to/france_eaip LFMD LFAT
```

#### UK eAIP
Parses UK eAIP data from local directories. Download from [NATS website](https://nats-uk.ead-it.com/cms-nats/opencms/en/Publications/AIP/).
```bash
python example/aip.py uk_eaip -r /path/to/uk_eaip EGLL EGKB
```

#### World Airports
Downloads and processes airport data from OurAirports database.
```bash
python example/aip.py worldairports
```

#### Point de Passage
Processes Point de Passage journal PDF files. Download from [Legifrance](https://www.legifrance.gouv.fr/jorf/id/JORFTEXT000043547009).
```bash
python example/aip.py pointdepassage -j /path/to/journal.pdf
```

### Programmatic Usage

```python
from euro_aip.parsers import AIPParserFactory
from euro_aip.sources import UKEAIPSource, FranceEAIPSource

# Initialize UK eAIP source
uk_source = UKEAIPSource(cache_dir='cache', root_dir='/path/to/uk_eaip')

# Get available airports
airports = uk_source.find_available_airports()

# Get airport AIP data (automatically detects HTML/PDF format)
airport_data = uk_source.get_airport_aip('EGLL')

# Get procedures
procedures = uk_source.get_procedures('EGLL')

# Use different parser types
parser = AIPParserFactory.get_parser('EGC', 'html')  # HTML only
parser = AIPParserFactory.get_parser('EGC', 'pdf')   # PDF only
parser = AIPParserFactory.get_parser('EGC', 'dual')  # Both formats
parser = AIPParserFactory.get_parser('EGC', 'auto')  # Auto-detect (default)
```

### Parser System

The library supports a flexible parser system with automatic format detection:

- **HTML Parsers**: Parse HTML-based AIP documents
- **PDF Parsers**: Parse PDF-based AIP documents  
- **Dual Parsers**: Automatically detect and parse both HTML and PDF formats
- **Auto Mode**: System chooses the best available parser

```python
# Check parser availability
info = AIPParserFactory.get_parser_info('EGC')
# Returns: {'html': True, 'pdf': True, 'dual': True}

# Get specific parser type
html_parser = AIPParserFactory.get_parser('EGC', 'html')
pdf_parser = AIPParserFactory.get_parser('EGC', 'pdf')
dual_parser = AIPParserFactory.get_parser('EGC', 'dual')
```

### Data Models

The library provides structured data models for parsed information:

- **AIP Data**: Structured airport information from AIP documents
- **Procedures**: Approach and departure procedures
- **Airport Database**: Comprehensive airport information from World Airports

### Caching

All sources support intelligent caching:

```python
# Force refresh cached data
source.set_force_refresh()

# Never refresh if cached data exists
source.set_never_refresh()

# Normal caching behavior (default)
# Uses cached data if not expired, fetches new data if expired
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
├── parsers/         # AIP document parsers (HTML, PDF, dual-format)
├── sources/         # Data sources (Autorouter, eAIP, World Airports)
├── storage/         # Storage backends
├── utils/           # Utility functions
└── tests/           # Test suite
```

### Adding New Sources

To add a new data source:

1. Create a new source class inheriting from `CachedSource`
2. Implement required methods (`find_available_airports`, `fetch_airport_aip`, etc.)
3. Register the source in `euro_aip/sources/__init__.py`
4. Add a corresponding `run_` method in `example/aip.py`

### Adding New Parsers

To add a new parser:

1. Create a parser class inheriting from `AIPParser`
2. Register it with `AIPParserFactory.register_html_parser()` or `register_pdf_parser()`
3. For dual-format support, both HTML and PDF parsers can be registered for the same authority

## License

This project is licensed under the MIT License - see the LICENSE file for details. 