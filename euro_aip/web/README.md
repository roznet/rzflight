# Euro AIP Airport Explorer Web Application

A comprehensive web application for exploring European airport data with interactive maps, filtering, and detailed information display.

## 🚀 Features

### **Interactive Map**
- **Leaflet.js** based interactive map
- Color-coded airport markers:
  - 🟢 Green: Airports with procedures
  - 🟡 Yellow: Airports without procedures  
  - 🔴 Red: Border crossing airports
- Click markers to view detailed airport information
- Popup information with basic airport details

### **Advanced Filtering**
- **Country filter**: Filter by ISO country codes
- **Procedure type filter**: Filter by approach, departure, arrival procedures
- **Approach type filter**: Filter by ILS, RNAV, VOR, NDB, etc.
- **Boolean filters**: Has procedures, has runways, has AIP data, border crossing only
- **Search functionality**: Search by ICAO code, airport name, or municipality

### **Detailed Airport Information**
- **Basic information**: ICAO, name, coordinates, country, municipality
- **Runway details**: Length, width, surface type, lighting
- **Procedures**: Grouped by type with color-coded badges
- **AIP data**: Standardized and raw field data organized by sections
- **Data sources**: Information about data provenance

### **Statistics and Charts**
- **Overview statistics**: Total airports, procedures, border crossings
- **Interactive charts**: Procedure distribution, country distribution
- **Real-time updates**: Charts update based on current filters

### **Responsive Design**
- **Bootstrap 5** responsive layout
- **Mobile-friendly** interface
- **Keyboard shortcuts** for power users

## 🏗️ Architecture

### **Backend (FastAPI)**
```
web/server/
├── main.py              # FastAPI application entry point
├── api/                 # API route modules
│   ├── airports.py      # Airport endpoints
│   ├── procedures.py    # Procedure endpoints
│   ├── filters.py       # Filter endpoints
│   └── statistics.py    # Statistics endpoints
└── requirements.txt     # Python dependencies
```

### **Frontend (Vanilla JavaScript)**
```
web/client/
├── index.html           # Main HTML page
├── js/                  # JavaScript modules
│   ├── api.js           # API client
│   ├── map.js           # Map functionality
│   ├── filters.js       # Filter management
│   ├── charts.js        # Chart functionality
│   └── app.js           # Main application
└── css/                 # Stylesheets (inline in HTML)
```

## 🛠️ Setup Instructions

### **Prerequisites**
- Python 3.8+
- `airports.db` file from your euro_aip project
- Modern web browser

### **1. Install Dependencies**
```bash
cd web
pip install -r requirements.txt
```

### **2. Configure Database Path**
Set the environment variable to point to your airports.db file:
```bash
export AIRPORTS_DB=/path/to/your/airports.db
```

Or modify the default path in `server/main.py`:
```python
db_path = os.getenv("AIRPORTS_DB", "airports.db")
```

### **3. Start the Server**
```bash
cd web/server
python main.py
```

The server will start on `http://localhost:8000`

### **4. Access the Application**
Open your browser and navigate to:
```
http://localhost:8000
```

## 📊 API Endpoints

### **Airports**
- `GET /api/airports/` - List airports with filtering
- `GET /api/airports/{icao}` - Get airport details
- `GET /api/airports/{icao}/aip-entries` - Get AIP entries
- `GET /api/airports/{icao}/procedures` - Get procedures
- `GET /api/airports/{icao}/runways` - Get runways
- `GET /api/airports/search/{query}` - Search airports

### **Procedures**
- `GET /api/procedures/` - List procedures with filtering
- `GET /api/procedures/approaches` - Get approach procedures
- `GET /api/procedures/departures` - Get departure procedures
- `GET /api/procedures/arrivals` - Get arrival procedures
- `GET /api/procedures/by-runway/{airport_icao}` - Get procedures by runway
- `GET /api/procedures/most-precise/{airport_icao}` - Get most precise approaches

### **Filters**
- `GET /api/filters/countries` - Available countries
- `GET /api/filters/procedure-types` - Available procedure types
- `GET /api/filters/approach-types` - Available approach types
- `GET /api/filters/aip-sections` - Available AIP sections
- `GET /api/filters/aip-fields` - Available AIP fields
- `GET /api/filters/all` - All filter options

### **Statistics**
- `GET /api/statistics/overview` - Overview statistics
- `GET /api/statistics/by-country` - Statistics by country
- `GET /api/statistics/procedure-distribution` - Procedure distribution
- `GET /api/statistics/aip-data-distribution` - AIP data distribution
- `GET /api/statistics/runway-statistics` - Runway statistics
- `GET /api/statistics/data-quality` - Data quality metrics

## 🎯 Usage Guide

### **Basic Navigation**
1. **Load the application** - The map will show the first 100 airports
2. **Click on airport markers** - View detailed information in the right panel
3. **Use filters** - Apply filters to narrow down airports
4. **Search** - Use the search box to find specific airports

### **Filtering**
1. **Country filter**: Select a specific country (e.g., "FR" for France)
2. **Procedure filters**: Filter by procedure types or approach types
3. **Boolean filters**: Check boxes for specific characteristics
4. **Apply filters**: Click "Apply Filters" to update the map

### **Search**
- **ICAO codes**: Type "LFPO" to find Paris Orly
- **Airport names**: Type "Charles de Gaulle" to find CDG
- **Cities**: Type "Paris" to find all Paris airports
- **IATA codes**: Type "CDG" to find Charles de Gaulle

### **Keyboard Shortcuts**
- `Ctrl/Cmd + F`: Focus search box
- `Escape`: Clear search and reset filters

### **Global Functions**
Open browser console and use:
```javascript
// Get application info
AirportExplorer.showInfo()

// Export current state
AirportExplorer.exportState()

// Get map instance
AirportExplorer.getMap()

// Get filter manager
AirportExplorer.getFilters()
```

## 🔧 Customization

### **Adding New Filter Types**
1. Add new endpoint in `server/api/filters.py`
2. Update frontend filter UI in `client/index.html`
3. Add filter logic in `client/js/filters.js`

### **Customizing Map Markers**
Modify the `addAirport` method in `client/js/map.js` to change:
- Marker colors and sizes
- Popup content
- Click behavior

### **Adding New Charts**
1. Create new chart in `client/js/charts.js`
2. Add corresponding API endpoint
3. Update the main application to load chart data

### **Styling**
The application uses Bootstrap 5 with custom CSS. Modify styles in `client/index.html` or add external CSS files.

## 🐛 Troubleshooting

### **Common Issues**

**1. "API health check failed"**
- Ensure the FastAPI server is running
- Check that `airports.db` exists and is accessible
- Verify all dependencies are installed

**2. "No airports displayed"**
- Check database path configuration
- Verify database contains airport data
- Check browser console for JavaScript errors

**3. "Charts not loading"**
- Ensure Chart.js is loaded
- Check network requests in browser dev tools
- Verify API endpoints are responding

**4. "Map not displaying"**
- Check Leaflet.js is loaded
- Verify internet connection (for map tiles)
- Check browser console for errors

### **Debug Mode**
Enable debug logging by opening browser console and running:
```javascript
localStorage.setItem('debug', 'true');
location.reload();
```

### **Performance Tips**
- Use filters to limit the number of airports displayed
- The application loads 100 airports by default
- Increase the limit in the API calls for more airports
- Consider pagination for very large datasets

## 📈 Future Enhancements

### **Planned Features**
- **Export functionality**: Export filtered data to CSV/JSON
- **Advanced search**: Full-text search across all fields
- **Comparison mode**: Compare multiple airports side-by-side
- **Route planning**: Plan routes between airports
- **Real-time data**: Live updates from AIP sources
- **Mobile app**: Native mobile application

### **Technical Improvements**
- **Caching**: Implement Redis caching for better performance
- **Database optimization**: Add indexes for faster queries
- **API versioning**: Version the API for backward compatibility
- **Authentication**: Add user authentication and permissions
- **WebSocket**: Real-time updates for collaborative features

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## 📄 License

This project is part of the euro_aip package. See the main project license for details.

## 🆘 Support

For issues and questions:
1. Check the troubleshooting section
2. Review the browser console for errors
3. Check the FastAPI server logs
4. Open an issue in the main euro_aip repository

---

**Happy exploring!** 🛩️ 