#!/usr/bin/env python3

from fastapi import APIRouter, Query, HTTPException, Request, Path, Body
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

def _matches_aip_field(airport: Airport, field_name: str, value: str = None, operator: str = "contains") -> bool:
    """
    Check if an airport matches AIP field criteria.
    
    Args:
        airport: Airport object to check
        field_name: Standardized AIP field name
        value: Value to search for (optional for not_empty operator)
        operator: Comparison operator
        
    Returns:
        True if airport matches the criteria
    """
    # Get all entries for this field
    field_entries = [entry for entry in airport.aip_entries if entry.std_field == field_name]
    
    if not field_entries:
        return False
    
    # Check each entry value
    for entry in field_entries:
        entry_value = entry.value.lower() if entry.value else ""
        search_value = value.lower() if value else ""
        
        if operator == "contains":
            if search_value in entry_value:
                return True
        elif operator == "equals":
            if entry_value == search_value:
                return True
        elif operator == "not_empty":
            if entry_value and entry_value not in ["nil", "none", "na", "n/a", ""]:
                return True
        elif operator == "starts_with":
            if entry_value.startswith(search_value):
                return True
        elif operator == "ends_with":
            if entry_value.endswith(search_value):
                return True
    
    return False

# API models are now imported from ../models

@router.get("/", response_model=List[AirportSummary])
async def get_airports(
    request: Request,
    country: Optional[str] = Query(None, description="Filter by ISO country code", max_length=3),
    has_procedures: Optional[bool] = Query(None, description="Filter airports with procedures"),
    has_aip_data: Optional[bool] = Query(None, description="Filter airports with AIP data"),
    has_hard_runway: Optional[bool] = Query(None, description="Filter airports with hard runways"),
    point_of_entry: Optional[bool] = Query(None, description="Filter border crossing airports"),
    # New AIP field filters
    aip_field: Optional[str] = Query(None, description="AIP standardized field name to filter by", max_length=100),
    aip_value: Optional[str] = Query(None, description="Value to search for in the AIP field", max_length=200),
    aip_operator: Optional[str] = Query("contains", description="Operator for AIP field filtering: contains, equals, not_empty, starts_with, ends_with", max_length=20),
    limit: int = Query(1000, description="Maximum number of airports to return", ge=1, le=10000),
    offset: int = Query(0, description="Number of airports to skip", ge=0, le=100000)
):
    """Get a list of airports with optional filtering."""
    if not model:
        raise HTTPException(status_code=500, detail="Model not loaded")
    
    # Validate offset against actual data size
    if offset >= len(model.airports):
        raise HTTPException(status_code=400, detail="Offset too large")
    
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
    
    # Apply AIP field filtering
    if aip_field:
        airports = [a for a in airports if _matches_aip_field(a, aip_field, aip_value, aip_operator)]
    
    # Always sort by longest runway length (descending) to prioritize larger airports
    # Airports without runway data will be sorted last
    airports.sort(key=lambda a: a.longest_runway_length_ft or 0, reverse=True)
    
    # Apply pagination
    airports = airports[offset:offset + limit]
    
    # Convert to response format using factory methods
    return [AirportSummary.from_airport(airport) for airport in airports]

@router.get("/route-search")
async def get_airports_near_route(
    request: Request,
    airports: str = Query(..., description="Comma-separated list of ICAO airport codes defining the route", max_length=200),
    distance_nm: float = Query(50.0, description="Distance in nautical miles from the route", ge=0.1, le=500.0),
    country: Optional[str] = Query(None, description="Filter by ISO country code", max_length=3),
    has_procedures: Optional[bool] = Query(None, description="Filter airports with procedures"),
    has_aip_data: Optional[bool] = Query(None, description="Filter airports with AIP data"),
    has_hard_runway: Optional[bool] = Query(None, description="Filter airports with hard runways"),
    point_of_entry: Optional[bool] = Query(None, description="Filter border crossing airports"),
    # New AIP field filters
    aip_field: Optional[str] = Query(None, description="AIP standardized field name to filter by", max_length=100),
    aip_value: Optional[str] = Query(None, description="Value to search for in the AIP field", max_length=200),
    aip_operator: Optional[str] = Query("contains", description="Operator for AIP field filtering: contains, equals, not_empty, starts_with, ends_with", max_length=20)
):
    """Find airports within a specified distance from a route defined by airport ICAO codes, with optional filtering."""
    if not model:
        raise HTTPException(status_code=500, detail="Model not loaded")
    
    # Parse airport codes
    try:
        route_airports = [code.strip().upper() for code in airports.split(',') if code.strip()]
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid airport codes format: {str(e)}")
    
    if len(route_airports) < 1:
        raise HTTPException(status_code=400, detail="Route must contain at least 1 airport")
    
    # Validate airport codes
    for icao in route_airports:
        if len(icao) != 4:
            raise HTTPException(status_code=400, detail=f"Invalid ICAO code: {icao}")
        if not model.get_airport(icao):
            raise HTTPException(status_code=404, detail=f"Airport {icao} not found")
    
    # Find airports near the route
    nearby_airports = model.find_airports_near_route(route_airports, distance_nm)
    
    # Apply additional filters
    filtered_airports = []
    for item in nearby_airports:
        airport = item['airport']
        
        # Apply country filter
        if country and airport.iso_country != country:
            continue
            
        # Apply procedures filter
        if has_procedures is not None:
            has_procs = bool(airport.procedures)
            if has_procs != has_procedures:
                continue
                
        # Apply AIP data filter
        if has_aip_data is not None:
            has_aip = bool(airport.aip_entries)
            if has_aip != has_aip_data:
                continue
                
        # Apply hard runway filter
        if has_hard_runway is not None:
            if airport.has_hard_runway != has_hard_runway:
                continue
                
        # Apply border crossing filter
        if point_of_entry is not None:
            if airport.point_of_entry != point_of_entry:
                continue
        
        # Apply AIP field filtering
        if aip_field and not _matches_aip_field(airport, aip_field, aip_value, aip_operator):
            continue
        
        # Airport passed all filters
        filtered_airports.append(item)
    
    # Convert to response format
    result = []
    for item in filtered_airports:
        airport = item['airport']
        airport_summary = AirportSummary.from_airport(airport)
        
        result.append({
            'airport': airport_summary.dict(),
            'distance_nm': item['distance_nm'],
            'closest_segment': item['closest_segment']
        })
    
    return {
        'route_airports': route_airports,
        'distance_nm': distance_nm,
        'airports_found': len(result),
        'total_nearby': len(nearby_airports),
        'filters_applied': {
            'country': country,
            'has_procedures': has_procedures,
            'has_aip_data': has_aip_data,
            'has_hard_runway': has_hard_runway,
            'point_of_entry': point_of_entry,
            'aip_field': aip_field,
            'aip_value': aip_value,
            'aip_operator': aip_operator
        },
        'airports': result
    }

@router.get("/aip-filter-presets")
async def get_aip_filter_presets(request: Request):
    """Get predefined AIP filter presets for common use cases."""
    presets = [
        {
            "id": "hotels",
            "name": "Hotels Available",
            "description": "Airports with hotel information",
            "field": "Hotels",
            "operator": "not_empty",
            "value": None,
            "icon": "🏨"
        },
        {
            "id": "restaurants", 
            "name": "Restaurants Available",
            "description": "Airports with restaurant information",
            "field": "Restaurants",
            "operator": "not_empty",
            "value": None,
            "icon": "🍽️"
        },
        {
            "id": "avgas",
            "name": "AVGAS Available",
            "description": "Airports with AVGAS fuel",
            "field": "Fuel and oil types",
            "operator": "contains",
            "value": "avgas",
            "icon": "⛽"
        },
        {
            "id": "jet_a",
            "name": "Jet A Available",
            "description": "Airports with Jet A fuel",
            "field": "Fuel and oil types",
            "operator": "contains", 
            "value": "jet a",
            "icon": "✈️"
        },
        {
            "id": "customs",
            "name": "Customs Available",
            "description": "Airports with customs facilities",
            "field": "Customs and immigration",
            "operator": "not_empty",
            "value": None,
            "icon": "🛂"
        },
        {
            "id": "deicing",
            "name": "De-icing Available",
            "description": "Airports with de-icing facilities",
            "field": "De-icing facilities",
            "operator": "not_empty",
            "value": None,
            "icon": "❄️"
        },
        {
            "id": "hangar",
            "name": "Hangar Space",
            "description": "Airports with hangar space for visiting aircraft",
            "field": "Hangar space for visiting aircraft",
            "operator": "not_empty",
            "value": None,
            "icon": "🏭"
        },
        {
            "id": "medical",
            "name": "Medical Facilities",
            "description": "Airports with medical facilities",
            "field": "Medical facilities",
            "operator": "not_empty",
            "value": None,
            "icon": "🏥"
        }
    ]
    
    return presets

@router.get("/{icao}", response_model=AirportDetail)
async def get_airport_detail(
    request: Request,
    icao: str = Path(..., description="ICAO airport code", max_length=4, min_length=4)
):
    """Get detailed information about a specific airport."""
    if not model:
        raise HTTPException(status_code=500, detail="Model not loaded")
    
    airport = model.get_airport(icao.upper())
    if not airport:
        raise HTTPException(status_code=404, detail=f"Airport {icao} not found")
    
    return AirportDetail.from_airport(airport)

@router.get("/{icao}/aip-entries", response_model=List[AIPEntryResponse])
async def get_airport_aip_entries(
    request: Request,
    icao: str = Path(..., description="ICAO airport code", max_length=4, min_length=4),
    section: Optional[str] = Query(None, description="Filter by AIP section", max_length=100),
    std_field: Optional[str] = Query(None, description="Filter by standardized field name", max_length=100)
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
    request: Request,
    icao: str = Path(..., description="ICAO airport code", max_length=4, min_length=4),
    procedure_type: Optional[str] = Query(None, description="Filter by procedure type", max_length=50),
    runway: Optional[str] = Query(None, description="Filter by runway identifier", max_length=10)
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
async def get_airport_runways(
    request: Request,
    icao: str = Path(..., description="ICAO airport code", max_length=4, min_length=4)
):
    """Get runways for a specific airport."""
    if not model:
        raise HTTPException(status_code=500, detail="Model not loaded")
    
    airport = model.get_airport(icao.upper())
    if not airport:
        raise HTTPException(status_code=404, detail=f"Airport {icao} not found")
    
    return [r.to_dict() for r in airport.runways]

@router.get("/{icao}/procedure-lines")
async def get_airport_procedure_lines(
    request: Request,
    icao: str = Path(..., description="ICAO airport code", max_length=4, min_length=4),
    distance_nm: float = Query(10.0, description="Distance in nautical miles for procedure lines", ge=0.1, le=100.0)
):
    """Get procedure lines for an airport."""
    if not model:
        raise HTTPException(status_code=500, detail="Model not loaded")
    
    airport = model.get_airport(icao.upper())
    if not airport:
        raise HTTPException(status_code=404, detail=f"Airport {icao} not found")
    
    return airport.get_procedure_lines(distance_nm)

@router.post("/bulk/procedure-lines")
async def get_bulk_procedure_lines(
    request: Request,
    airports: List[str] = Body(..., description="List of ICAO airport codes", max_items=100),
    distance_nm: float = Body(10.0, description="Distance in nautical miles for procedure lines", ge=0.1, le=100.0)
):
    """Get procedure lines for multiple airports in a single request."""
    if not model:
        raise HTTPException(status_code=500, detail="Model not loaded")
    
    if len(airports) > 100:
        raise HTTPException(status_code=400, detail="Maximum 100 airports allowed per request")
    
    result = {}
    
    for icao in airports:
        airport = model.get_airport(icao.upper())
        if airport:
            try:
                procedure_lines = airport.get_procedure_lines(distance_nm)
                result[icao.upper()] = procedure_lines
            except Exception as e:
                # Log error but continue with other airports
                print(f"Error getting procedure lines for {icao}: {e}")
                result[icao.upper()] = {"procedure_lines": [], "error": str(e)}
        else:
            result[icao.upper()] = {"procedure_lines": [], "error": "Airport not found"}
    
    return result

@router.get("/search/{query}")
async def search_airports(
    request: Request,
    query: str = Path(..., description="Search query", max_length=100, min_length=1),
    limit: int = Query(20, description="Maximum number of results", ge=1, le=100)
):
    """Search airports by name or ICAO code."""
    if not model:
        raise HTTPException(status_code=500, detail="Model not loaded")
    
    query = query.upper()
    results = []
    
    for airport in model.airports.values():
        if (query in airport.ident or 
            (airport.name and query in airport.name.upper()) or 
            (airport.iata_code and query in airport.iata_code)):
            results.append(AirportSummary.from_airport(airport))
            if len(results) >= limit:
                break
    
    return results 