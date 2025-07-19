#!/usr/bin/env python3

from fastapi import APIRouter, Query, HTTPException
from typing import List, Optional, Dict, Any
from pydantic import BaseModel
import logging

from euro_aip.models.euro_aip_model import EuroAipModel
from euro_aip.models.airport import Airport

logger = logging.getLogger(__name__)

router = APIRouter()

# Global model reference
model: Optional[EuroAipModel] = None

def set_model(m: EuroAipModel):
    """Set the global model reference."""
    global model
    model = m

# Pydantic models for API responses
class AirportSummary(BaseModel):
    ident: str
    name: Optional[str]
    latitude_deg: Optional[float]
    longitude_deg: Optional[float]
    iso_country: Optional[str]
    municipality: Optional[str]
    point_of_entry: Optional[bool]
    has_procedures: bool
    has_runways: bool
    has_aip_data: bool
    procedure_count: int
    runway_count: int
    aip_entry_count: int

class AirportDetail(BaseModel):
    ident: str
    name: Optional[str]
    type: Optional[str]
    latitude_deg: Optional[float]
    longitude_deg: Optional[float]
    elevation_ft: Optional[str]
    continent: Optional[str]
    iso_country: Optional[str]
    iso_region: Optional[str]
    municipality: Optional[str]
    scheduled_service: Optional[str]
    gps_code: Optional[str]
    iata_code: Optional[str]
    local_code: Optional[str]
    home_link: Optional[str]
    wikipedia_link: Optional[str]
    keywords: Optional[str]
    point_of_entry: Optional[bool]
    avgas: Optional[bool]
    jet_a: Optional[bool]
    sources: List[str]
    runways: List[Dict[str, Any]]
    procedures: List[Dict[str, Any]]
    aip_entries: List[Dict[str, Any]]
    created_at: str
    updated_at: str

class AIPEntryResponse(BaseModel):
    ident: str
    section: str
    field: str
    value: str
    std_field: Optional[str]
    std_field_id: Optional[int]
    mapping_score: Optional[float]
    alt_field: Optional[str]
    alt_value: Optional[str]
    source: Optional[str]
    created_at: str

@router.get("/", response_model=List[AirportSummary])
async def get_airports(
    country: Optional[str] = Query(None, description="Filter by ISO country code"),
    has_procedures: Optional[bool] = Query(None, description="Filter airports with procedures"),
    has_runways: Optional[bool] = Query(None, description="Filter airports with runways"),
    has_aip_data: Optional[bool] = Query(None, description="Filter airports with AIP data"),
    point_of_entry: Optional[bool] = Query(None, description="Filter border crossing airports"),
    limit: int = Query(100, description="Maximum number of airports to return"),
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
    
    if has_runways is not None:
        airports = [a for a in airports if bool(a.runways) == has_runways]
    
    if has_aip_data is not None:
        airports = [a for a in airports if bool(a.aip_entries) == has_aip_data]
    
    if point_of_entry is not None:
        airports = [a for a in airports if a.point_of_entry == point_of_entry]
    
    # Apply pagination
    airports = airports[offset:offset + limit]
    
    # Convert to response format
    result = []
    for airport in airports:
        result.append(AirportSummary(
            ident=airport.ident,
            name=airport.name,
            latitude_deg=airport.latitude_deg,
            longitude_deg=airport.longitude_deg,
            iso_country=airport.iso_country,
            municipality=airport.municipality,
            point_of_entry=airport.point_of_entry,
            has_procedures=bool(airport.procedures),
            has_runways=bool(airport.runways),
            has_aip_data=bool(airport.aip_entries),
            procedure_count=len(airport.procedures),
            runway_count=len(airport.runways),
            aip_entry_count=len(airport.aip_entries)
        ))
    
    return result

@router.get("/{icao}", response_model=AirportDetail)
async def get_airport_detail(icao: str):
    """Get detailed information about a specific airport."""
    if not model:
        raise HTTPException(status_code=500, detail="Model not loaded")
    
    airport = model.get_airport(icao.upper())
    if not airport:
        raise HTTPException(status_code=404, detail=f"Airport {icao} not found")
    
    return AirportDetail(
        ident=airport.ident,
        name=airport.name,
        type=airport.type,
        latitude_deg=airport.latitude_deg,
        longitude_deg=airport.longitude_deg,
        elevation_ft=airport.elevation_ft,
        continent=airport.continent,
        iso_country=airport.iso_country,
        iso_region=airport.iso_region,
        municipality=airport.municipality,
        scheduled_service=airport.scheduled_service,
        gps_code=airport.gps_code,
        iata_code=airport.iata_code,
        local_code=airport.local_code,
        home_link=airport.home_link,
        wikipedia_link=airport.wikipedia_link,
        keywords=airport.keywords,
        point_of_entry=airport.point_of_entry,
        avgas=airport.avgas,
        jet_a=airport.jet_a,
        sources=list(airport.sources),
        runways=[r.to_dict() for r in airport.runways],
        procedures=[p.to_dict() for p in airport.procedures],
        aip_entries=[e.to_dict() for e in airport.aip_entries],
        created_at=airport.created_at.isoformat(),
        updated_at=airport.updated_at.isoformat()
    )

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
    
    return [AIPEntryResponse(
        ident=e.ident,
        section=e.section,
        field=e.field,
        value=e.value,
        std_field=e.std_field,
        std_field_id=e.std_field_id,
        mapping_score=e.mapping_score,
        alt_field=e.alt_field,
        alt_value=e.alt_value,
        source=e.source,
        created_at=e.created_at.isoformat()
    ) for e in entries]

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
    
    # Convert to summary format and limit results
    result_summaries = []
    for airport in results[:limit]:
        result_summaries.append(AirportSummary(
            ident=airport.ident,
            name=airport.name,
            latitude_deg=airport.latitude_deg,
            longitude_deg=airport.longitude_deg,
            iso_country=airport.iso_country,
            municipality=airport.municipality,
            point_of_entry=airport.point_of_entry,
            has_procedures=bool(airport.procedures),
            has_runways=bool(airport.runways),
            has_aip_data=bool(airport.aip_entries),
            procedure_count=len(airport.procedures),
            runway_count=len(airport.runways),
            aip_entry_count=len(airport.aip_entries)
        ))
    
    return result_summaries 