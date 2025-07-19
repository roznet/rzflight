#!/usr/bin/env python3

import sys
import os
from pathlib import Path

# Add the euro_aip package to the path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import logging

from euro_aip.storage.database_storage import DatabaseStorage
from euro_aip.models.euro_aip_model import EuroAipModel

# Import API routes
from api import airports, procedures, filters, statistics

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="Euro AIP Airport Explorer",
    description="Interactive web application for exploring European airport data",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify your frontend domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global database storage
db_storage = None
model = None

@app.on_event("startup")
async def startup_event():
    """Initialize database connection on startup."""
    global db_storage, model
    
    # Get database path from environment or use default
    db_path = os.getenv("AIRPORTS_DB", "airports.db")
    
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
        
    except Exception as e:
        logger.error(f"Failed to load database: {e}")
        raise

# Include API routes
app.include_router(airports.router, prefix="/api/airports", tags=["airports"])
app.include_router(procedures.router, prefix="/api/procedures", tags=["procedures"])
app.include_router(filters.router, prefix="/api/filters", tags=["filters"])
app.include_router(statistics.router, prefix="/api/statistics", tags=["statistics"])

# Serve static files for client assets
app.mount("/js", StaticFiles(directory="../client/js"), name="js")

@app.get("/")
async def read_root():
    """Serve the main HTML page."""
    return FileResponse("../client/index.html")

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "airports_count": len(model.airports) if model else 0,
        "database_path": db_storage.database_path if db_storage else None
    }

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    ) 