#!/usr/bin/env python3

from fastapi import APIRouter, Query, HTTPException
from typing import List, Optional, Dict, Any
from pydantic import BaseModel
import logging

from euro_aip.models.euro_aip_model import EuroAipModel

logger = logging.getLogger(__name__)

router = APIRouter()

# Global model reference
model: Optional[EuroAipModel] = None

def set_model(m: EuroAipModel):
    """Set the global model reference."""
    global model
    model = m

# Pydantic models for API responses
class ProcedureSummary(BaseModel):
    name: str
    procedure_type: str
    approach_type: Optional[str]
    runway_ident: Optional[str]
    authority: Optional[str]
    source: Optional[str]
    airport_ident: str
    airport_name: Optional[str]

@router.get("/", response_model=List[ProcedureSummary])
async def get_procedures(
    procedure_type: Optional[str] = Query(None, description="Filter by procedure type"),
    approach_type: Optional[str] = Query(None, description="Filter by approach type"),
    runway: Optional[str] = Query(None, description="Filter by runway identifier"),
    authority: Optional[str] = Query(None, description="Filter by authority"),
    source: Optional[str] = Query(None, description="Filter by source"),
    airport: Optional[str] = Query(None, description="Filter by airport ICAO"),
    limit: int = Query(100, description="Maximum number of procedures to return"),
    offset: int = Query(0, description="Number of procedures to skip")
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
            
            procedures.append(ProcedureSummary(
                name=procedure.name,
                procedure_type=procedure.procedure_type,
                approach_type=procedure.approach_type,
                runway_ident=procedure.runway_ident,
                authority=procedure.authority,
                source=procedure.source,
                airport_ident=airport.ident,
                airport_name=airport.name
            ))
    
    # Apply pagination
    procedures = procedures[offset:offset + limit]
    
    return procedures

@router.get("/approaches")
async def get_approaches(
    approach_type: Optional[str] = Query(None, description="Filter by approach type"),
    runway: Optional[str] = Query(None, description="Filter by runway identifier"),
    airport: Optional[str] = Query(None, description="Filter by airport ICAO"),
    limit: int = Query(100, description="Maximum number of approaches to return")
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
    runway: Optional[str] = Query(None, description="Filter by runway identifier"),
    airport: Optional[str] = Query(None, description="Filter by airport ICAO"),
    limit: int = Query(100, description="Maximum number of departures to return")
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
    runway: Optional[str] = Query(None, description="Filter by runway identifier"),
    airport: Optional[str] = Query(None, description="Filter by airport ICAO"),
    limit: int = Query(100, description="Maximum number of arrivals to return")
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
async def get_procedures_by_runway(airport_icao: str):
    """Get procedures organized by runway for a specific airport."""
    if not model:
        raise HTTPException(status_code=500, detail="Model not loaded")
    
    airport = model.get_airport(airport_icao.upper())
    if not airport:
        raise HTTPException(status_code=404, detail=f"Airport {airport_icao} not found")
    
    return airport.get_runway_procedures_summary()

@router.get("/most-precise/{airport_icao}")
async def get_most_precise_approaches(airport_icao: str):
    """Get the most precise approach for each runway at an airport."""
    if not model:
        raise HTTPException(status_code=500, detail="Model not loaded")
    
    airport = model.get_airport(airport_icao.upper())
    if not airport:
        raise HTTPException(status_code=404, detail=f"Airport {airport_icao} not found")
    
    most_precise = {}
    
    for runway in airport.runways:
        # Get most precise approach for the runway
        approach = airport.get_most_precise_approach_for_runway(runway)
        if approach:
            most_precise[runway.le_ident] = {
                "name": approach.name,
                "approach_type": approach.approach_type,
                "precision": approach.get_approach_precision(),
                "runway_ident": approach.runway_ident,
                "authority": approach.authority,
                "source": approach.source
            }
    
    return most_precise

@router.get("/statistics")
async def get_procedure_statistics():
    """Get procedure statistics across all airports."""
    if not model:
        raise HTTPException(status_code=500, detail="Model not loaded")
    
    total_procedures = 0
    procedure_types = {}
    approach_types = {}
    authorities = {}
    sources = {}
    
    for airport in model.airports.values():
        for procedure in airport.procedures:
            total_procedures += 1
            
            # Count procedure types
            proc_type = procedure.procedure_type.lower()
            if proc_type not in procedure_types:
                procedure_types[proc_type] = 0
            procedure_types[proc_type] += 1
            
            # Count approach types
            if procedure.is_approach() and procedure.approach_type:
                approach_type = procedure.approach_type.upper()
                if approach_type not in approach_types:
                    approach_types[approach_type] = 0
                approach_types[approach_type] += 1
            
            # Count authorities
            if procedure.authority:
                if procedure.authority not in authorities:
                    authorities[procedure.authority] = 0
                authorities[procedure.authority] += 1
            
            # Count sources
            if procedure.source:
                if procedure.source not in sources:
                    sources[procedure.source] = 0
                sources[procedure.source] += 1
    
    return {
        "total_procedures": total_procedures,
        "procedure_types": [
            {"type": proc_type, "count": count}
            for proc_type, count in sorted(procedure_types.items())
        ],
        "approach_types": [
            {"type": approach_type, "count": count}
            for approach_type, count in sorted(approach_types.items())
        ],
        "authorities": [
            {"authority": authority, "count": count}
            for authority, count in sorted(authorities.items())
        ],
        "sources": [
            {"source": source, "count": count}
            for source, count in sorted(sources.items())
        ]
    } 