#!/usr/bin/env python3

from fastapi import APIRouter, HTTPException, Request
from typing import List, Dict, Any, Set
import logging

from euro_aip.models.euro_aip_model import EuroAipModel

logger = logging.getLogger(__name__)

router = APIRouter(tags=["filters"])

# Global model reference
model: EuroAipModel = None

def set_model(m: EuroAipModel):
    """Set the global model reference."""
    global model
    model = m

def format_country_name_for_display(country_name: str) -> str:
    """
    Format country name for display by capitalizing each word properly.
    
    Args:
        country_name: Raw country name (e.g., "BOSNIA AND HERZEGOVINA")
        
    Returns:
        Formatted country name (e.g., "Bosnia And Herzegovina")
    """
    if not country_name:
        return country_name
    
    # Split by spaces and capitalize each word
    words = country_name.split()
    formatted_words = []
    
    for word in words:
        # Handle special cases like "AND", "OF", "THE" - keep them lowercase
        if word.upper() in ["AND", "OF", "THE", "OF THE"]:
            formatted_words.append(word.lower())
        else:
            # Capitalize first letter, lowercase the rest
            formatted_words.append(word.capitalize())
    
    return " ".join(formatted_words)

@router.get("/countries")
async def get_available_countries(request: Request):
    """Get list of available countries with airport counts."""
    if not model:
        raise HTTPException(status_code=500, detail="Model not loaded")
    
    # Import CountryMapper fresh to get latest mappings
    from euro_aip.utils.country_mapper import CountryMapper
    country_mapper = CountryMapper()
    
    countries = {}
    for airport in model.airports.values():
        if airport.iso_country:
            if airport.iso_country not in countries:
                countries[airport.iso_country] = 0
            countries[airport.iso_country] += 1
    
    return [
        {
            "code": code, 
            "name": format_country_name_for_display(country_mapper.get_country_name(code)) or code,
            "count": count
        }
        for code, count in sorted(countries.items())
    ]

@router.get("/procedure-types")
async def get_available_procedure_types(request: Request):
    """Get list of available procedure types with counts."""
    if not model:
        raise HTTPException(status_code=500, detail="Model not loaded")
    
    procedure_types = {}
    for airport in model.airports.values():
        for procedure in airport.procedures:
            proc_type = procedure.procedure_type.lower()
            if proc_type not in procedure_types:
                procedure_types[proc_type] = 0
            procedure_types[proc_type] += 1
    
    return [
        {"type": proc_type, "count": count}
        for proc_type, count in sorted(procedure_types.items())
    ]

@router.get("/aip-sections")
async def get_available_aip_sections(request: Request):
    """Get list of available AIP sections with counts."""
    if not model:
        raise HTTPException(status_code=500, detail="Model not loaded")
    
    sections = {}
    for airport in model.airports.values():
        for entry in airport.aip_entries:
            section = entry.section
            if section not in sections:
                sections[section] = 0
            sections[section] += 1
    
    return [
        {"section": section, "count": count}
        for section, count in sorted(sections.items())
    ]

@router.get("/aip-fields")
async def get_available_aip_fields(request: Request):
    """Get list of available AIP standardized fields with counts."""
    if not model:
        raise HTTPException(status_code=500, detail="Model not loaded")
    
    fields = {}
    for airport in model.airports.values():
        for entry in airport.aip_entries:
            if entry.std_field:
                field = entry.std_field
                if field not in fields:
                    fields[field] = 0
                fields[field] += 1
    
    return [
        {"field": field, "count": count}
        for field, count in sorted(fields.items())
    ]

@router.get("/sources")
async def get_available_sources(request: Request):
    """Get list of available data sources with counts."""
    if not model:
        raise HTTPException(status_code=500, detail="Model not loaded")
    
    sources = {}
    for airport in model.airports.values():
        for source in airport.sources:
            if source not in sources:
                sources[source] = 0
            sources[source] += 1
    
    return [
        {"source": source, "count": count}
        for source, count in sorted(sources.items())
    ]

@router.get("/runway-characteristics")
async def get_runway_characteristics(request: Request):
    """Get runway characteristics statistics."""
    if not model:
        raise HTTPException(status_code=500, detail="Model not loaded")
    
    runway_lengths = []
    runway_surfaces = {}
    runway_lighting = {}
    
    for airport in model.airports.values():
        for runway in airport.runways:
            # Length statistics
            if runway.length_ft:
                runway_lengths.append(runway.length_ft)
            
            # Surface types
            if runway.surface:
                surface = runway.surface.lower()
                if surface not in runway_surfaces:
                    runway_surfaces[surface] = 0
                runway_surfaces[surface] += 1
            
            # Lighting
            if runway.lighted:
                lighting = "lighted" if runway.lighted else "unlighted"
                if lighting not in runway_lighting:
                    runway_lighting[lighting] = 0
                runway_lighting[lighting] += 1
    
    return {
        "lengths": {
            "min": min(runway_lengths) if runway_lengths else None,
            "max": max(runway_lengths) if runway_lengths else None,
            "average": sum(runway_lengths) / len(runway_lengths) if runway_lengths else None,
            "count": len(runway_lengths)
        },
        "surfaces": [
            {"surface": surface, "count": count}
            for surface, count in sorted(runway_surfaces.items())
        ],
        "lighting": [
            {"lighting": lighting, "count": count}
            for lighting, count in sorted(runway_lighting.items())
        ]
    }

@router.get("/border-crossing")
async def get_border_crossing_statistics(request: Request):
    """Get border crossing statistics."""
    if not model:
        raise HTTPException(status_code=500, detail="Model not loaded")
    
    return model.get_border_crossing_statistics()

@router.get("/all")
async def get_all_filters(request: Request):
    """Get all available filter options in one call."""
    if not model:
        raise HTTPException(status_code=500, detail="Model not loaded")
    
    return {
        "countries": await get_available_countries(request),
        "procedure_types": await get_available_procedure_types(request),
        "aip_sections": await get_available_aip_sections(request),
        "aip_fields": await get_available_aip_fields(request),
        "sources": await get_available_sources(request),
        "runway_characteristics": await get_runway_characteristics(request),
        "border_crossing": await get_border_crossing_statistics(request)
    } 