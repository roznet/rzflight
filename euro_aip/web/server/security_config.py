#!/usr/bin/env python3

"""
Security configuration for the Euro AIP Airport Explorer.
"""

import os
from typing import List

# CORS Configuration
ALLOWED_ORIGINS = [
    "https://maps.flyfun.aero",
    "https://flyfun.aero",
    "http://localhost:3000",
    "http://localhost:8000",
    "http://127.0.0.1:8000"
]

# Trusted Hosts Configuration
ALLOWED_HOSTS = [
    "maps.flyfun.aero",
    "flyfun.aero", 
    "localhost",
    "127.0.0.1",
    "localhost:8000",
    "127.0.0.1:8000"
]

# Rate Limiting Configuration
RATE_LIMIT_WINDOW = 60  # 1 minute
RATE_LIMIT_MAX_REQUESTS = 100  # 100 requests per minute

# Input Validation Limits
MAX_QUERY_LENGTH = 100
MAX_ICAO_LENGTH = 4
MIN_ICAO_LENGTH = 4
MAX_COUNTRY_LENGTH = 3
MAX_PROCEDURE_TYPE_LENGTH = 50
MAX_RUNWAY_LENGTH = 10
MAX_AUTHORITY_LENGTH = 100
MAX_SOURCE_LENGTH = 100
MAX_SECTION_LENGTH = 100
MAX_STD_FIELD_LENGTH = 100

# Pagination Limits
MAX_LIMIT = 10000
MIN_LIMIT = 1
MAX_OFFSET = 100000
MIN_OFFSET = 0

# Distance Limits
MIN_DISTANCE_NM = 0.1
MAX_DISTANCE_NM = 100.0

# Environment Configuration
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
FORCE_HTTPS = ENVIRONMENT == "production"

# Database Security
def get_safe_db_path() -> str:
    """Get a safe database path with validation."""
    db_path = os.getenv("AIRPORTS_DB", "airports.db")
    
    # In production, ensure database is in a safe location
    if ENVIRONMENT == "production":
        # Ensure database is within allowed directory
        allowed_dir = "/var/www/euro-aip"
        if not db_path.startswith(allowed_dir):
            db_path = f"{allowed_dir}/airports.db"
    
    return db_path

# Security Headers
SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "X-XSS-Protection": "1; mode=block",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Content-Security-Policy": "default-src 'self'; script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://unpkg.com https://cdnjs.cloudflare.com; style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://unpkg.com https://cdnjs.cloudflare.com; img-src 'self' data: https: https://*.tile.openstreetmap.org; font-src 'self' https: https://cdnjs.cloudflare.com; connect-src 'self' https:;"
}

# Logging Configuration
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

# API Security
API_KEY_REQUIRED = os.getenv("API_KEY_REQUIRED", "false").lower() == "true"
API_KEY = os.getenv("API_KEY", "")

# Session Security
SESSION_SECRET_KEY = os.getenv("SESSION_SECRET_KEY", "your-secret-key-change-in-production")
SESSION_COOKIE_SECURE = ENVIRONMENT == "production"
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax" 