#!/usr/bin/env python3

from fastapi import APIRouter, HTTPException, Request
from typing import Dict, Any, List
import logging

from euro_aip.models.euro_aip_model import EuroAipModel

logger = logging.getLogger(__name__)

router = APIRouter()

# Global model reference
model: EuroAipModel = None

def set_model(m: EuroAipModel):
    """Set the global model reference."""
    global model
    model = m

@router.get("/overview")
async def get_overview_statistics(request: Request):
    """Get overview statistics for the entire model."""
    if not model:
        raise HTTPException(status_code=500, detail="Model not loaded")
    
    return model.get_statistics()

@router.get("/by-country")
async def get_statistics_by_country(request: Request):
    """Get airport statistics grouped by country."""
    if not model:
        raise HTTPException(status_code=500, detail="Model not loaded")
    
    countries = {}
    
    for airport in model.airports.values():
        country = airport.iso_country or "Unknown"
        
        if country not in countries:
            countries[country] = {
                "total_airports": 0,
                "airports_with_procedures": 0,
                "airports_with_runways": 0,
                "airports_with_aip_data": 0,
                "border_crossing_airports": 0,
                "total_procedures": 0,
                "total_runways": 0,
                "total_aip_entries": 0
            }
        
        countries[country]["total_airports"] += 1
        
        if airport.procedures:
            countries[country]["airports_with_procedures"] += 1
            countries[country]["total_procedures"] += len(airport.procedures)
        
        if airport.runways:
            countries[country]["airports_with_runways"] += 1
            countries[country]["total_runways"] += len(airport.runways)
        
        if airport.aip_entries:
            countries[country]["airports_with_aip_data"] += 1
            countries[country]["total_aip_entries"] += len(airport.aip_entries)
        
        if airport.point_of_entry:
            countries[country]["border_crossing_airports"] += 1
    
    return [
        {"country": country, **stats}
        for country, stats in sorted(countries.items())
    ]

@router.get("/procedure-distribution")
async def get_procedure_distribution(request: Request):
    """Get procedure type distribution statistics."""
    if not model:
        raise HTTPException(status_code=500, detail="Model not loaded")
    
    procedure_types = {}
    approach_types = {}
    
    for airport in model.airports.values():
        for procedure in airport.procedures:
            # General procedure types
            proc_type = procedure.procedure_type.lower()
            if proc_type not in procedure_types:
                procedure_types[proc_type] = 0
            procedure_types[proc_type] += 1
            
            # Approach types
            if procedure.is_approach() and procedure.approach_type:
                approach_type = procedure.approach_type.upper()
                if approach_type not in approach_types:
                    approach_types[approach_type] = 0
                approach_types[approach_type] += 1
    
    return {
        "procedure_types": [
            {"type": proc_type, "count": count}
            for proc_type, count in sorted(procedure_types.items())
        ],
        "approach_types": [
            {"type": approach_type, "count": count}
            for approach_type, count in sorted(approach_types.items())
        ]
    }

@router.get("/aip-data-distribution")
async def get_aip_data_distribution(request: Request):
    """Get AIP data distribution statistics."""
    if not model:
        raise HTTPException(status_code=500, detail="Model not loaded")
    
    sections = {}
    fields = {}
    sources = {}
    
    for airport in model.airports.values():
        for entry in airport.aip_entries:
            # Sections
            section = entry.section
            if section not in sections:
                sections[section] = 0
            sections[section] += 1
            
            # Standardized fields
            if entry.std_field:
                field = entry.std_field
                if field not in fields:
                    fields[field] = 0
                fields[field] += 1
            
            # Sources
            if entry.source:
                source = entry.source
                if source not in sources:
                    sources[source] = 0
                sources[source] += 1
    
    return {
        "sections": [
            {"section": section, "count": count}
            for section, count in sorted(sections.items())
        ],
        "fields": [
            {"field": field, "count": count}
            for field, count in sorted(fields.items())
        ],
        "sources": [
            {"source": source, "count": count}
            for source, count in sorted(sources.items())
        ]
    }

@router.get("/runway-statistics")
async def get_runway_statistics(request: Request):
    """Get runway statistics."""
    if not model:
        raise HTTPException(status_code=500, detail="Model not loaded")
    
    lengths = []
    surfaces = {}
    lighting = {}
    widths = []
    
    for airport in model.airports.values():
        for runway in airport.runways:
            # Lengths
            if runway.length_ft:
                lengths.append(runway.length_ft)
            
            # Widths
            if runway.width_ft:
                widths.append(runway.width_ft)
            
            # Surfaces
            if runway.surface:
                surface = runway.surface.lower()
                if surface not in surfaces:
                    surfaces[surface] = 0
                surfaces[surface] += 1
            
            # Lighting
            if runway.lighted is not None:
                lighting_status = "lighted" if runway.lighted else "unlighted"
                if lighting_status not in lighting:
                    lighting[lighting_status] = 0
                lighting[lighting_status] += 1
    
    return {
        "lengths": {
            "min": min(lengths) if lengths else None,
            "max": max(lengths) if lengths else None,
            "average": sum(lengths) / len(lengths) if lengths else None,
            "count": len(lengths),
            "distribution": get_length_distribution(lengths) if lengths else []
        },
        "widths": {
            "min": min(widths) if widths else None,
            "max": max(widths) if widths else None,
            "average": sum(widths) / len(widths) if widths else None,
            "count": len(widths)
        },
        "surfaces": [
            {"surface": surface, "count": count}
            for surface, count in sorted(surfaces.items())
        ],
        "lighting": [
            {"lighting": lighting_status, "count": count}
            for lighting_status, count in sorted(lighting.items())
        ]
    }

def get_length_distribution(lengths: List[int]) -> List[Dict[str, Any]]:
    """Get runway length distribution in categories."""
    if not lengths:
        return []
    
    # Define length categories
    categories = [
        {"name": "Short (< 3000 ft)", "min": 0, "max": 3000},
        {"name": "Medium (3000-6000 ft)", "min": 3000, "max": 6000},
        {"name": "Long (6000-9000 ft)", "min": 6000, "max": 9000},
        {"name": "Very Long (> 9000 ft)", "min": 9000, "max": float('inf')}
    ]
    
    distribution = []
    for category in categories:
        count = sum(1 for length in lengths if category["min"] <= length < category["max"])
        if count > 0:
            distribution.append({
                "category": category["name"],
                "count": count,
                "percentage": round((count / len(lengths)) * 100, 1)
            })
    
    return distribution

@router.get("/data-quality")
async def get_data_quality_statistics(request: Request):
    """Get data quality statistics."""
    if not model:
        raise HTTPException(status_code=500, detail="Model not loaded")
    
    total_airports = len(model.airports)
    airports_with_coordinates = 0
    airports_with_runways = 0
    airports_with_procedures = 0
    airports_with_aip_data = 0
    airports_with_complete_data = 0
    
    for airport in model.airports.values():
        has_coordinates = airport.latitude_deg is not None and airport.longitude_deg is not None
        has_runways = len(airport.runways) > 0
        has_procedures = len(airport.procedures) > 0
        has_aip_data = len(airport.aip_entries) > 0
        
        if has_coordinates:
            airports_with_coordinates += 1
        if has_runways:
            airports_with_runways += 1
        if has_procedures:
            airports_with_procedures += 1
        if has_aip_data:
            airports_with_aip_data += 1
        if has_coordinates and has_runways and has_procedures and has_aip_data:
            airports_with_complete_data += 1
    
    return {
        "total_airports": total_airports,
        "coverage": {
            "coordinates": {
                "count": airports_with_coordinates,
                "percentage": round((airports_with_coordinates / total_airports) * 100, 1)
            },
            "runways": {
                "count": airports_with_runways,
                "percentage": round((airports_with_runways / total_airports) * 100, 1)
            },
            "procedures": {
                "count": airports_with_procedures,
                "percentage": round((airports_with_procedures / total_airports) * 100, 1)
            },
            "aip_data": {
                "count": airports_with_aip_data,
                "percentage": round((airports_with_aip_data / total_airports) * 100, 1)
            },
            "complete_data": {
                "count": airports_with_complete_data,
                "percentage": round((airports_with_complete_data / total_airports) * 100, 1)
            }
        }
    } 