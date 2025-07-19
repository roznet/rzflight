#!/usr/bin/env python3

from fastapi import APIRouter, Query, HTTPException
from typing import List, Optional, Dict, Any
import logging

from euro_aip.models.euro_aip_model import EuroAipModel
from euro_aip.models.airport import Airport
from .models import AirportSummary, AirportDetail, AIPEntryResponse

logger = logging.getLogger(__name__)

router = APIRouter()

# Global model reference
model: Optional[EuroAipModel] = None

def set_model(m: EuroAipModel):
    """Set the global model reference."""
    global model
    model = m

# API models are now imported from ../models

@router.get("/", response_model=List[AirportSummary])
async def get_airports(
    country: Optional[str] = Query(None, description="Filter by ISO country code"),
    has_procedures: Optional[bool] = Query(None, description="Filter airports with procedures"),
    has_aip_data: Optional[bool] = Query(None, description="Filter airports with AIP data"),
    has_hard_runway: Optional[bool] = Query(None, description="Filter airports with hard runways"),
    point_of_entry: Optional[bool] = Query(None, description="Filter border crossing airports"),
    limit: int = Query(1000, description="Maximum number of airports to return"),
    offset: int = Query(0, description="Number of airports to skip")
):
    """Get a list of airports with optional filtering."""
    if not model:
        raise HTTPException(status_code=500, detail="Model not loaded")
    
    airports = list(model.airports.values())
    
    # Apply filters
    if country:
        airports = [a for a in airports if a.iso_country == country]
    
    if has_procedures is not None:
        airports = [a for a in airports if bool(a.procedures) == has_procedures]
    
    if has_aip_data is not None:
        airports = [a for a in airports if bool(a.aip_entries) == has_aip_data]
    
    if has_hard_runway is not None:
        airports = [a for a in airports if a.has_hard_runway == has_hard_runway]
    
    if point_of_entry is not None:
        airports = [a for a in airports if a.point_of_entry == point_of_entry]
    
    # Always sort by longest runway length (descending) to prioritize larger airports
    # Airports without runway data will be sorted last
    airports.sort(key=lambda a: a.longest_runway_length_ft or 0, reverse=True)
    
    # Apply pagination
    airports = airports[offset:offset + limit]
    
    # Convert to response format using factory methods
    return [AirportSummary.from_airport(airport) for airport in airports]

@router.get("/{icao}", response_model=AirportDetail)
async def get_airport_detail(icao: str):
    """Get detailed information about a specific airport."""
    if not model:
        raise HTTPException(status_code=500, detail="Model not loaded")
    
    airport = model.get_airport(icao.upper())
    if not airport:
        raise HTTPException(status_code=404, detail=f"Airport {icao} not found")
    
    return AirportDetail.from_airport(airport)

@router.get("/{icao}/aip-entries", response_model=List[AIPEntryResponse])
async def get_airport_aip_entries(
    icao: str,
    section: Optional[str] = Query(None, description="Filter by AIP section"),
    std_field: Optional[str] = Query(None, description="Filter by standardized field name")
):
    """Get AIP entries for a specific airport."""
    if not model:
        raise HTTPException(status_code=500, detail="Model not loaded")
    
    airport = model.get_airport(icao.upper())
    if not airport:
        raise HTTPException(status_code=404, detail=f"Airport {icao} not found")
    
    entries = airport.aip_entries
    
    # Apply filters
    if section:
        entries = [e for e in entries if e.section == section]
    
    if std_field:
        entries = [e for e in entries if e.std_field == std_field]
    
    return [AIPEntryResponse.from_aip_entry(e) for e in entries]

@router.get("/{icao}/procedures")
async def get_airport_procedures(
    icao: str,
    procedure_type: Optional[str] = Query(None, description="Filter by procedure type"),
    runway: Optional[str] = Query(None, description="Filter by runway identifier")
):
    """Get procedures for a specific airport."""
    if not model:
        raise HTTPException(status_code=500, detail="Model not loaded")
    
    airport = model.get_airport(icao.upper())
    if not airport:
        raise HTTPException(status_code=404, detail=f"Airport {icao} not found")
    
    procedures = airport.procedures
    
    # Apply filters
    if procedure_type:
        procedures = airport.get_procedures_by_type(procedure_type)
    
    if runway:
        procedures = airport.get_procedures_by_runway(runway)
    
    return [p.to_dict() for p in procedures]

@router.get("/{icao}/runways")
async def get_airport_runways(icao: str):
    """Get runways for a specific airport."""
    if not model:
        raise HTTPException(status_code=500, detail="Model not loaded")
    
    airport = model.get_airport(icao.upper())
    if not airport:
        raise HTTPException(status_code=404, detail=f"Airport {icao} not found")
    
    return [r.to_dict() for r in airport.runways]

@router.get("/search/{query}")
async def search_airports(
    query: str,
    limit: int = Query(20, description="Maximum number of results")
):
    """Search airports by ICAO code, name, or municipality."""
    if not model:
        raise HTTPException(status_code=500, detail="Model not loaded")
    
    query = query.upper()
    results = []
    
    for airport in model.airports.values():
        # Search by ICAO code
        if query in airport.ident:
            results.append(airport)
            continue
        
        # Search by name
        if airport.name and query in airport.name.upper():
            results.append(airport)
            continue
        
        # Search by municipality
        if airport.municipality and query in airport.municipality.upper():
            results.append(airport)
            continue
        
        # Search by IATA code
        if airport.iata_code and query in airport.iata_code.upper():
            results.append(airport)
            continue
    
    # Convert to summary format using factory methods
    return [AirportSummary.from_airport(airport) for airport in results[:limit]] 