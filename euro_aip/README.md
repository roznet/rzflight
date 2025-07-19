# Euro AIP Airport Explorer

A comprehensive web application for exploring European airports, their procedures, and AIP (Aeronautical Information Publication) data.

## Features

### Core Functionality
- **Airport Database**: Comprehensive database of European airports with detailed information
- **Interactive Map**: Visual exploration of airports using Leaflet.js
- **Advanced Filtering**: Filter airports by country, procedure types, runway characteristics, and more
- **AIP Data Integration**: Access to standardized AIP entries and field mappings
- **Procedure Analysis**: Detailed procedure information including approach types and precision rankings
- **Border Crossing Points**: Specialized data for border crossing airports
- **Statistics and Charts**: Visual analytics of airport and procedure distributions

### Route-Based Airport Search
- **Route Definition**: Enter space-separated ICAO codes to define a flight route
- **Distance-Based Search**: Find all airports within a specified distance (default 50nm) from the route
- **Visual Route Display**: Route is displayed on the map with special markers and a dashed line
- **Distance Indicators**: Airport markers show their distance from the route
- **Great Circle Calculations**: Accurate geographic distance calculations using the Haversine formula

#### How to Use Route Search
1. In the search box, enter ICAO codes separated by spaces (e.g., `LFPO LFOB LFST`)
2. Adjust the "Route Distance" field to set the search corridor width (default: 50nm)
3. Press Enter or click the search button
4. The map will display:
   - The route as a blue dashed line
   - Route airports as blue circle markers
   - Nearby airports with distance indicators
   - Distance information in airport popups

## Architecture

### Backend (FastAPI)
- **Models**: Domain models for airports, procedures, runways, and AIP data
- **API Endpoints**: RESTful API for data access and filtering
- **Database Storage**: SQLite-based storage with efficient querying
- **Security**: CORS, rate limiting, and input validation

### Frontend (Vanilla JavaScript)
- **Interactive Map**: Leaflet.js-based map with custom markers and layers
- **Real-time Filtering**: Dynamic filtering with immediate visual feedback
- **Responsive Design**: Bootstrap-based responsive layout
- **Chart Visualization**: Chart.js for statistical displays

### Core Library (`euro_aip`)
- **Data Models**: Comprehensive data structures for aviation data
- **Parsers**: Specialized parsers for different AIP sources
- **Sources**: Data source integrations (WorldAirports, Autorouter, etc.)
- **Utilities**: Geographic calculations, field standardization, and data processing

## Installation and Setup

### Prerequisites
- Python 3.8+
- Node.js (for development tools)

### Quick Start
1. Clone the repository
2. Install dependencies: `pip install -r requirements.txt`
3. Run the server: `cd web/server && python main.py`
4. Open http://localhost:8000 in your browser

### Development Setup
1. Create a virtual environment: `python -m venv venv`
2. Activate the environment: `source venv/bin/activate` (Linux/Mac) or `venv\Scripts\activate` (Windows)
3. Install dependencies: `pip install -r requirements.txt`
4. Run the development server: `cd web/server && python main.py`

## API Documentation

### Core Endpoints
- `GET /api/airports/` - List airports with filtering
- `GET /api/airports/{icao}` - Get detailed airport information
- `GET /api/airports/route-search` - Find airports near a route
- `GET /api/procedures/` - List procedures with filtering
- `GET /api/statistics/` - Get various statistics

### Route Search API
```
GET /api/airports/route-search?airports=LFPO,LFOB,LFST&distance_nm=50
```

**Parameters:**
- `airports`: Comma-separated list of ICAO airport codes
- `distance_nm`: Distance in nautical miles from the route (default: 50)

**Response:**
```json
{
  "route_airports": ["LFPO", "LFOB", "LFST"],
  "distance_nm": 50,
  "airports_found": 61,
  "airports": [
    {
      "airport": { /* airport data */ },
      "distance_nm": 3.59,
      "closest_segment": ["LFPO", "LFOB"]
    }
  ]
}
```

## Data Sources

- **WorldAirports**: Comprehensive airport database from OurAirports
- **Autorouter**: European AIP data and procedures
- **Border Crossing Data**: Specialized border crossing point information
- **Custom Parsers**: Specialized parsers for different European aviation authorities

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- **OurAirports**: For the comprehensive airport database
- **Autorouter**: For European AIP data
- **OpenStreetMap**: For map tiles
- **Leaflet.js**: For the interactive map functionality 