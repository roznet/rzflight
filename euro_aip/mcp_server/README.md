# Euro AIP Airport Database MCP Server

This MCP (Model Context Protocol) server provides access to the Euro AIP airport database for LLM clients like ChatGPT and Claude.

## Features

The server provides the following tools:

### 1. Airport Search (`search_airports`)
- Search airports by name, ICAO code, or city
- Filter by country, customs, fuel types, restaurants, runway type
- Returns detailed facility information

### 2. Airport Details (`get_airport_details`)
- Get comprehensive information about a specific airport
- Includes facilities, runways, procedures, and special status

### 3. Route-Based Search (`find_airports_near_route`)
- Find airports within a specified distance from a flight route
- Perfect for planning fuel stops or customs stops
- Filter by facilities needed

### 4. Closest Airport (`find_closest_airport`)
- Find the nearest airport to a location or city
- Automatically suggests nearest customs airport if needed
- Filter by runway type and customs availability

### 5. Airport Procedures (`get_airport_procedures`)
- Get instrument procedures for specific airports
- Filter by procedure type (approach, departure, arrival)
- Filter by runway

### 6. Border Crossing Airports (`get_border_crossing_airports`)
- List all airports that serve as border crossing points
- Filter by country and customs availability

### 7. Statistics (`get_airport_statistics`)
- Get database statistics
- Filter by country

## Setup

### Prerequisites
- Python 3.8+
- Euro AIP airport database (`airports.db`)
- MCP-compatible client (ChatGPT, Claude, etc.)

### Installation

1. **Install dependencies:**
```bash
cd mcp_server
pip install -r requirements.txt
```

2. **Set database path:**
```bash
export AIRPORTS_DB=/path/to/your/airports.db
```

3. **Test the server:**
```bash
python main.py
```

## Usage Examples

### Example 1: Route Planning with Customs Stop
```
I am flying from EGTF to LFMD, I would like to do a stop for customs that is well positioned on the route, that has AVGAS and a restaurant.
```

**Tools used:**
- `find_airports_near_route` with route [EGTF, LFMD], distance 50nm, has_customs=true, has_avgas=true, has_restaurant=true

### Example 2: Closest Airport to Destination
```
I want to go to Beaune, which is the closest airport for a small airplane? Does it have customs and if not, which airport do you recommend to stop first?
```

**Tools used:**
- `find_closest_airport` with location="Beaune", has_hard_runway=true
- If no customs, automatically finds nearest customs airport

### Example 3: Airport Information
```
What facilities does LFMD have? What procedures are available?
```

**Tools used:**
- `get_airport_details` with icao_code="LFMD"
- `get_airport_procedures` with icao_code="LFMD"

## Configuration

### Environment Variables
- `AIRPORTS_DB`: Path to the airport database file (default: `airports.db`)

### MCP Client Configuration

For ChatGPT:
1. Go to Settings > Beta features
2. Enable "Model Context Protocol"
3. Add server configuration:
```json
{
  "mcpServers": {
    "euro-aip-airports": {
      "command": "python",
      "args": ["/path/to/mcp_server/main.py"],
      "env": {
        "AIRPORTS_DB": "/path/to/airports.db"
      }
    }
  }
}
```

For Claude:
1. Use Claude Desktop or API with MCP support
2. Configure similar to ChatGPT

## Deployment Options

### Local Development
- Run directly with Python
- Use for testing and development
- No authentication required

### Production Deployment

#### Option 1: Docker Container
```dockerfile
FROM python:3.9-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["python", "main.py"]
```

#### Option 2: Cloud Deployment
- Deploy to AWS Lambda, Google Cloud Functions, or Azure Functions
- Use serverless architecture for cost efficiency
- Implement proper authentication and rate limiting

#### Option 3: Traditional Server
- Deploy to VPS or cloud VM
- Use systemd service for auto-restart
- Implement monitoring and logging

## Cost Considerations

### Token Usage Optimization
1. **Response Length**: Keep responses concise but informative
2. **Caching**: Implement caching for frequently requested data
3. **Pagination**: Limit results to reduce token usage
4. **Smart Filtering**: Use specific filters to reduce data transfer

### Cost Allocation
1. **User Tracking**: Implement user ID tracking in requests
2. **Usage Metrics**: Track tool calls per user
3. **Billing Integration**: Connect to billing system for cost allocation
4. **Rate Limiting**: Implement per-user rate limits

## Security Considerations

### Authentication
- Implement API key authentication
- Use OAuth2 for user authentication
- Validate user permissions

### Rate Limiting
- Implement per-user rate limits
- Use sliding window rate limiting
- Monitor for abuse

### Data Privacy
- Log minimal user data
- Implement data retention policies
- Comply with GDPR/privacy regulations

## Monitoring and Logging

### Metrics to Track
- Tool call frequency
- Response times
- Error rates
- User usage patterns

### Logging
- Log all tool calls with user context
- Track performance metrics
- Monitor for errors and exceptions

## Future Enhancements

### Planned Features
1. **Geocoding Integration**: Better location-based searches
2. **Weather Integration**: Real-time weather data
3. **Flight Planning**: Complete flight planning capabilities
4. **Real-time Data**: Live airport status updates
5. **Multi-language Support**: Support for multiple languages

### Performance Improvements
1. **Database Optimization**: Index optimization and query tuning
2. **Caching Layer**: Redis or similar for frequently accessed data
3. **CDN Integration**: For static data delivery
4. **Load Balancing**: For high-traffic scenarios

## Troubleshooting

### Common Issues

1. **Database not found**
   - Check `AIRPORTS_DB` environment variable
   - Verify database file exists and is readable

2. **Import errors**
   - Ensure euro_aip package is in Python path
   - Check all dependencies are installed

3. **MCP connection issues**
   - Verify MCP client configuration
   - Check server is running and accessible

### Debug Mode
Enable debug logging:
```bash
export LOG_LEVEL=DEBUG
python main.py
```

## Support

For issues and questions:
1. Check the troubleshooting section
2. Review the logs for error messages
3. Verify your configuration
4. Contact support with detailed error information
