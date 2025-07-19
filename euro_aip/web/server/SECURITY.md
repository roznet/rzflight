# Security Features - Euro AIP Airport Explorer

This document outlines the security measures implemented in the Euro AIP Airport Explorer web application.

## 🔒 Security Measures Implemented

### 1. CORS (Cross-Origin Resource Sharing) Protection
- **Restricted Origins**: Only specific domains are allowed to make requests
- **Methods**: Limited to GET and POST requests
- **Credentials**: Enabled for authenticated requests

**Configuration**: `security_config.py`
```python
ALLOWED_ORIGINS = [
    "https://maps.flyfun.aero",
    "https://flyfun.aero",
    "http://localhost:3000",
    "http://localhost:8000",
    "http://127.0.0.1:8000"
]
```

### 2. Trusted Hosts Protection
- **Host Validation**: Only requests from trusted hosts are accepted
- **Prevents**: Host header attacks and DNS rebinding

**Configuration**: `security_config.py`
```python
ALLOWED_HOSTS = [
    "maps.flyfun.aero",
    "flyfun.aero", 
    "localhost",
    "127.0.0.1",
    "localhost:8000",
    "127.0.0.1:8000"
]
```

### 3. Rate Limiting
- **Requests per minute**: 100 requests per IP address
- **Window**: 60-second sliding window
- **Response**: 429 Too Many Requests when limit exceeded

**Configuration**: `security_config.py`
```python
RATE_LIMIT_WINDOW = 60  # 1 minute
RATE_LIMIT_MAX_REQUESTS = 100  # 100 requests per minute
```

### 4. Input Validation
- **Parameter Limits**: All query parameters have length and value constraints
- **Type Validation**: Pydantic models ensure proper data types
- **Range Validation**: Numeric parameters have min/max bounds

**Examples**:
```python
limit: int = Field(Query(1000), ge=1, le=10000)
icao: str = Field(..., max_length=4, min_length=4)
distance_nm: float = Field(Query(10.0), ge=0.1, le=100.0)
```

### 5. Security Headers
- **X-Content-Type-Options**: `nosniff` - Prevents MIME type sniffing
- **X-Frame-Options**: `DENY` - Prevents clickjacking
- **X-XSS-Protection**: `1; mode=block` - XSS protection
- **Referrer-Policy**: `strict-origin-when-cross-origin`
- **Content-Security-Policy**: Restricts resource loading

**Configuration**: `security_config.py`
```python
SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "X-XSS-Protection": "1; mode=block",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Content-Security-Policy": "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data: https:; font-src 'self' https:;"
}
```

### 6. HTTPS Enforcement
- **Production**: Automatically redirects HTTP to HTTPS
- **Development**: HTTPS not enforced for local development

**Configuration**: `security_config.py`
```python
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
FORCE_HTTPS = ENVIRONMENT == "production"
```

### 7. Database Path Security
- **Path Validation**: Database path is validated to prevent path traversal
- **Production**: Database must be in allowed directory

**Configuration**: `security_config.py`
```python
def get_safe_db_path() -> str:
    db_path = os.getenv("AIRPORTS_DB", "airports.db")
    
    if ENVIRONMENT == "production":
        allowed_dir = "/var/www/euro-aip"
        if not db_path.startswith(allowed_dir):
            db_path = f"{allowed_dir}/airports.db"
    
    return db_path
```

### 8. Request Logging
- **Comprehensive Logging**: All requests are logged with timing and IP
- **Security Events**: Rate limit violations and suspicious activity logged

**Log Format**:
```
2024-01-01 12:00:00 - main - INFO - GET /api/airports/ - 200 - 0.123s - 127.0.0.1
```

### 9. Health Endpoint Security
- **Minimal Information**: Only exposes safe information
- **No Sensitive Data**: Database paths, counts, or internal state not exposed

**Safe Response**:
```json
{
    "status": "healthy",
    "timestamp": "2024-01-01T12:00:00Z"
}
```

## 🛡️ Security Testing

Run the security test suite to verify all measures are working:

```bash
cd web/server
python test_security.py
```

The test suite checks:
- CORS headers
- Security headers
- Input validation
- Rate limiting
- Trusted hosts
- Health endpoint security
- API endpoint functionality

## 🔧 Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `ENVIRONMENT` | Environment (development/production) | `development` |
| `AIRPORTS_DB` | Database path | `airports.db` |
| `LOG_LEVEL` | Logging level | `INFO` |
| `API_KEY_REQUIRED` | Require API key authentication | `false` |
| `API_KEY` | API key for authentication | `""` |

### Production Deployment

1. **Set Environment**:
   ```bash
   export ENVIRONMENT=production
   ```

2. **Configure Database Path**:
   ```bash
   export AIRPORTS_DB=/var/www/euro-aip/airports.db
   ```

3. **Set Log Level**:
   ```bash
   export LOG_LEVEL=WARNING
   ```

4. **Optional: Enable API Key Authentication**:
   ```bash
   export API_KEY_REQUIRED=true
   export API_KEY=your-secret-api-key
   ```

## 🚨 Security Best Practices

### For Developers

1. **Never commit sensitive data** to version control
2. **Use environment variables** for configuration
3. **Validate all inputs** at API boundaries
4. **Log security events** for monitoring
5. **Keep dependencies updated** regularly

### For Production

1. **Use HTTPS only** in production
2. **Configure proper CORS** for your domain
3. **Monitor logs** for suspicious activity
4. **Regular security audits** of the application
5. **Keep the server updated** with security patches

### For API Users

1. **Use HTTPS** for all requests
2. **Respect rate limits** (100 requests/minute)
3. **Validate responses** before processing
4. **Handle errors gracefully** (429, 422, etc.)

## 🔍 Monitoring and Alerting

### Key Metrics to Monitor

1. **Rate Limit Violations**: High number of 429 responses
2. **Invalid Input**: High number of 422 responses
3. **Trusted Host Violations**: Requests from untrusted hosts
4. **Response Times**: Unusual latency patterns
5. **Error Rates**: High 4xx/5xx response rates

### Log Analysis

Monitor these log patterns:
- `Rate limit exceeded for IP:`
- `Invalid host` or `TrustedHostMiddleware`
- `422` status codes with validation errors
- Unusual request patterns

## 📞 Security Contact

For security issues or questions:
- Review this documentation
- Check the security test suite
- Monitor application logs
- Consider implementing additional measures based on your threat model

## 🔄 Security Updates

This security implementation is designed to be:
- **Configurable**: Easy to adjust for different environments
- **Testable**: Comprehensive test suite included
- **Maintainable**: Centralized configuration
- **Extensible**: Easy to add new security measures

Regular security reviews and updates are recommended. 