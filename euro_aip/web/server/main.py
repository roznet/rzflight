#!/usr/bin/env python3

import sys
import os
from pathlib import Path

# Add the euro_aip package to the path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.middleware.httpsredirect import HTTPSRedirectMiddleware
from contextlib import asynccontextmanager
import uvicorn
import logging
from datetime import datetime
import time

from euro_aip.storage.database_storage import DatabaseStorage
from euro_aip.models.euro_aip_model import EuroAipModel

# Import security configuration
from security_config import (
    ALLOWED_ORIGINS, ALLOWED_HOSTS, RATE_LIMIT_WINDOW, RATE_LIMIT_MAX_REQUESTS,
    FORCE_HTTPS, get_safe_db_path, SECURITY_HEADERS, LOG_LEVEL, LOG_FORMAT
)

# Import API routes
from api import airports, procedures, filters, statistics
from chat import ask as chat_ask

# Configure logging
logging.basicConfig(level=getattr(logging, LOG_LEVEL), format=LOG_FORMAT)
logger = logging.getLogger(__name__)

# Global database storage
db_storage = None
model = None

# Simple rate limiting storage
request_counts = {}

def check_rate_limit(client_ip: str) -> bool:
    """Simple rate limiting implementation."""
    global request_counts
    current_time = time.time()
    
    # Clean old entries
    request_counts = {ip: (count, timestamp) for ip, (count, timestamp) in request_counts.items() 
                     if current_time - timestamp < RATE_LIMIT_WINDOW}
    
    if client_ip not in request_counts:
        request_counts[client_ip] = (1, current_time)
        return True
    
    count, timestamp = request_counts[client_ip]
    
    if current_time - timestamp > RATE_LIMIT_WINDOW:
        request_counts[client_ip] = (1, current_time)
        return True
    
    if count >= RATE_LIMIT_MAX_REQUESTS:
        return False
    
    request_counts[client_ip] = (count + 1, timestamp)
    return True

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for FastAPI app."""
    global db_storage, model
    
    # Startup
    logger.info("Starting up Euro AIP Airport Explorer...")
    
    # Get database path from environment or use default
    db_path = get_safe_db_path()
    
    try:
        db_storage = DatabaseStorage(db_path)
        model = db_storage.load_model()
        logger.info(f"Loaded model with {len(model.airports)} airports")
        
        # All derived fields are now updated automatically in load_model()
        logger.info("Model loaded with all derived fields updated")
        
        # Make model available to API routes
        airports.set_model(model)
        procedures.set_model(model)
        filters.set_model(model)
        statistics.set_model(model)
        
        logger.info("Application startup complete")
        
    except Exception as e:
        logger.error(f"Failed to load database: {e}")
        raise
    
    yield
    
    # Shutdown
    logger.info("Shutting down Euro AIP Airport Explorer...")
    # Add any cleanup code here if needed

# Create FastAPI app with lifespan context manager
app = FastAPI(
    title="Euro AIP Airport Explorer",
    description="Interactive web application for exploring European airport data",
    version="1.0.0",
    lifespan=lifespan
)

# Add security headers middleware
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    
    # Add security headers
    for header, value in SECURITY_HEADERS.items():
        response.headers[header] = value
    
    return response

# Add request logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    
    client_ip = request.client.host if request.client else "unknown"
    logger.info(
        f"{request.method} {request.url.path} - "
        f"{response.status_code} - {process_time:.3f}s - {client_ip}"
    )
    return response

# Add rate limiting middleware
@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    client_ip = request.client.host if request.client else "unknown"
    
    if not check_rate_limit(client_ip):
        logger.warning(f"Rate limit exceeded for IP: {client_ip}")
        return JSONResponse(
            status_code=429,
            content={"detail": "Too many requests. Please try again later."}
        )
    
    response = await call_next(request)
    return response

# Add security middleware
app.add_middleware(
    TrustedHostMiddleware, 
    allowed_hosts=ALLOWED_HOSTS
)

# Force HTTPS in production
if FORCE_HTTPS:
    app.add_middleware(HTTPSRedirectMiddleware)

# Add CORS middleware with restricted origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(airports.router, prefix="/api/airports", tags=["airports"])
app.include_router(procedures.router, prefix="/api/procedures", tags=["procedures"])
app.include_router(filters.router, prefix="/api/filters", tags=["filters"])
app.include_router(statistics.router, prefix="/api/statistics", tags=["statistics"])
app.include_router(chat_ask.router, tags=["chat"])

# Serve static files for client assets
client_dir = Path(__file__).parent.parent / "client"
js_dir = client_dir / "js"

# Debug logging to verify paths
logger.info(f"Client directory: {client_dir}")
logger.info(f"JS directory: {js_dir}")
logger.info(f"JS directory exists: {js_dir.exists()}")

# Add cache control middleware for development
@app.middleware("http")
async def add_cache_control_headers(request: Request, call_next):
    response = await call_next(request)
    
    # Add cache control headers for JavaScript files in development
    if request.url.path.endswith('.js'):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    
    return response

# Mount static files
app.mount("/js", StaticFiles(directory=js_dir, html=True), name="js")

@app.get("/")
async def read_root():
    """Serve the main HTML page."""
    html_file = client_dir / "index.html"
    return FileResponse(str(html_file))

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat()
    }

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    ) 