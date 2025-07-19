#!/usr/bin/env python3

from fastapi import APIRouter, Query, HTTPException, Request, Path
from typing import List, Optional, Dict, Any
import logging

from euro_aip.models.euro_aip_model import EuroAipModel
from .models import ProcedureSummary

logger = logging.getLogger(__name__)

router = APIRouter()

# Global model reference
model: Optional[EuroAipModel] = None

def set_model(m: EuroAipModel):
    """Set the global model reference."""
    global model
    model = m

# API models are now imported from ../models

@router.get("/", response_model=List[ProcedureSummary])
async def get_procedures(
    request: Request,
    procedure_type: Optional[str] = Query(None, description="Filter by procedure type", max_length=50),
    approach_type: Optional[str] = Query(None, description="Filter by approach type", max_length=50),
    runway: Optional[str] = Query(None, description="Filter by runway identifier", max_length=10),
    authority: Optional[str] = Query(None, description="Filter by authority", max_length=100),
    source: Optional[str] = Query(None, description="Filter by source", max_length=100),
    airport: Optional[str] = Query(None, description="Filter by airport ICAO", max_length=4, min_length=4),
    limit: int = Query(100, description="Maximum number of procedures to return", ge=1, le=1000),
    offset: int = Query(0, description="Number of procedures to skip", ge=0, le=10000)
):
    """Get a list of procedures with optional filtering."""
    if not model:
        raise HTTPException(status_code=500, detail="Model not loaded")
    
    procedures = []
    
    for airport in model.airports.values():
        for procedure in airport.procedures:
            # Apply filters
            if procedure_type and procedure.procedure_type.lower() != procedure_type.lower():
                continue
            
            if approach_type and procedure.approach_type and procedure.approach_type.upper() != approach_type.upper():
                continue
            
            if runway and not procedure.matches_runway(runway):
                continue
            
            if authority and procedure.authority != authority:
                continue
            
            if source and procedure.source != source:
                continue
            
            if airport and airport.ident != airport:
                continue
            
            procedures.append(ProcedureSummary.from_procedure(procedure, airport))
    
    # Apply pagination
    procedures = procedures[offset:offset + limit]
    
    return procedures

@router.get("/approaches")
async def get_approaches(
    request: Request,
    approach_type: Optional[str] = Query(None, description="Filter by approach type", max_length=50),
    runway: Optional[str] = Query(None, description="Filter by runway identifier", max_length=10),
    airport: Optional[str] = Query(None, description="Filter by airport ICAO", max_length=4, min_length=4),
    limit: int = Query(100, description="Maximum number of approaches to return", ge=1, le=1000)
):
    """Get all approach procedures with optional filtering."""
    if not model:
        raise HTTPException(status_code=500, detail="Model not loaded")
    
    approaches = []
    
    for airport in model.airports.values():
        airport_approaches = airport.get_approaches()
        
        for procedure in airport_approaches:
            # Apply filters
            if approach_type and procedure.approach_type and procedure.approach_type.upper() != approach_type.upper():
                continue
            
            if runway and not procedure.matches_runway(runway):
                continue
            
            if airport and airport.ident != airport:
                continue
            
            approaches.append({
                "name": procedure.name,
                "approach_type": procedure.approach_type,
                "runway_ident": procedure.runway_ident,
                "authority": procedure.authority,
                "source": procedure.source,
                "airport_ident": airport.ident,
                "airport_name": airport.name,
                "precision": procedure.get_approach_precision()
            })
    
    # Apply limit
    approaches = approaches[:limit]
    
    return approaches

@router.get("/departures")
async def get_departures(
    request: Request,
    runway: Optional[str] = Query(None, description="Filter by runway identifier", max_length=10),
    airport: Optional[str] = Query(None, description="Filter by airport ICAO", max_length=4, min_length=4),
    limit: int = Query(100, description="Maximum number of departures to return", ge=1, le=1000)
):
    """Get all departure procedures with optional filtering."""
    if not model:
        raise HTTPException(status_code=500, detail="Model not loaded")
    
    departures = []
    
    for airport in model.airports.values():
        airport_departures = airport.get_departures()
        
        for procedure in airport_departures:
            # Apply filters
            if runway and not procedure.matches_runway(runway):
                continue
            
            if airport and airport.ident != airport:
                continue
            
            departures.append({
                "name": procedure.name,
                "runway_ident": procedure.runway_ident,
                "authority": procedure.authority,
                "source": procedure.source,
                "airport_ident": airport.ident,
                "airport_name": airport.name
            })
    
    # Apply limit
    departures = departures[:limit]
    
    return departures

@router.get("/arrivals")
async def get_arrivals(
    request: Request,
    runway: Optional[str] = Query(None, description="Filter by runway identifier", max_length=10),
    airport: Optional[str] = Query(None, description="Filter by airport ICAO", max_length=4, min_length=4),
    limit: int = Query(100, description="Maximum number of arrivals to return", ge=1, le=1000)
):
    """Get all arrival procedures with optional filtering."""
    if not model:
        raise HTTPException(status_code=500, detail="Model not loaded")
    
    arrivals = []
    
    for airport in model.airports.values():
        airport_arrivals = airport.get_arrivals()
        
        for procedure in airport_arrivals:
            # Apply filters
            if runway and not procedure.matches_runway(runway):
                continue
            
            if airport and airport.ident != airport:
                continue
            
            arrivals.append({
                "name": procedure.name,
                "runway_ident": procedure.runway_ident,
                "authority": procedure.authority,
                "source": procedure.source,
                "airport_ident": airport.ident,
                "airport_name": airport.name
            })
    
    # Apply limit
    arrivals = arrivals[:limit]
    
    return arrivals

@router.get("/by-runway/{airport_icao}")
async def get_procedures_by_runway(
    request: Request,
    airport_icao: str = Path(..., description="ICAO airport code", max_length=4, min_length=4)
):
    """Get procedures organized by runway for a specific airport."""
    if not model:
        raise HTTPException(status_code=500, detail="Model not loaded")
    
    airport = model.get_airport(airport_icao.upper())
    if not airport:
        raise HTTPException(status_code=404, detail=f"Airport {airport_icao} not found")
    
    return airport.get_runway_procedures_summary()

@router.get("/most-precise/{airport_icao}")
async def get_most_precise_approaches(
    request: Request,
    airport_icao: str = Path(..., description="ICAO airport code", max_length=4, min_length=4)
):
    """Get the most precise approach for each runway at an airport."""
    if not model:
        raise HTTPException(status_code=500, detail="Model not loaded")
    
    airport = model.get_airport(airport_icao.upper())
    if not airport:
        raise HTTPException(status_code=404, detail=f"Airport {airport_icao} not found")
    
    return airport.get_most_precise_approaches()

@router.get("/statistics")
async def get_procedure_statistics(request: Request):
    """Get statistics about procedures across all airports."""
    if not model:
        raise HTTPException(status_code=500, detail="Model not loaded")
    
    total_procedures = 0
    procedure_types = {}
    approach_types = {}
    airports_with_procedures = 0
    
    for airport in model.airports.values():
        if airport.procedures:
            airports_with_procedures += 1
            
        for procedure in airport.procedures:
            total_procedures += 1
            
            # Count procedure types
            proc_type = procedure.procedure_type
            procedure_types[proc_type] = procedure_types.get(proc_type, 0) + 1
            
            # Count approach types
            if procedure.approach_type:
                app_type = procedure.approach_type
                approach_types[app_type] = approach_types.get(app_type, 0) + 1
    
    return {
        "total_procedures": total_procedures,
        "airports_with_procedures": airports_with_procedures,
        "procedure_types": procedure_types,
        "approach_types": approach_types,
        "average_procedures_per_airport": total_procedures / len(model.airports) if model.airports else 0
    } 