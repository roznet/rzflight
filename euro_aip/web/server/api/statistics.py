#!/usr/bin/env python3

from fastapi import APIRouter, HTTPException
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
async def get_overview_statistics():
    """Get overview statistics for the entire model."""
    if not model:
        raise HTTPException(status_code=500, detail="Model not loaded")
    
    return model.get_statistics()

@router.get("/by-country")
async def get_statistics_by_country():
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
async def get_procedure_distribution():
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
async def get_aip_data_distribution():
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
async def get_runway_statistics():
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
    """Create length distribution buckets for charting."""
    if not lengths:
        return []
    
    min_length = min(lengths)
    max_length = max(lengths)
    
    # Create buckets
    bucket_size = (max_length - min_length) // 10 if max_length > min_length else 1000
    buckets = {}
    
    for length in lengths:
        bucket = (length // bucket_size) * bucket_size
        bucket_key = f"{bucket}-{bucket + bucket_size}"
        if bucket_key not in buckets:
            buckets[bucket_key] = 0
        buckets[bucket_key] += 1
    
    return [
        {"range": bucket, "count": count}
        for bucket, count in sorted(buckets.items())
    ]

@router.get("/data-quality")
async def get_data_quality_statistics():
    """Get data quality statistics."""
    if not model:
        raise HTTPException(status_code=500, detail="Model not loaded")
    
    total_airports = len(model.airports)
    airports_with_coordinates = 0
    airports_with_runways = 0
    airports_with_procedures = 0
    airports_with_aip_data = 0
    airports_with_border_crossing = 0
    
    total_aip_entries = 0
    standardized_entries = 0
    
    for airport in model.airports.values():
        if airport.latitude_deg and airport.longitude_deg:
            airports_with_coordinates += 1
        
        if airport.runways:
            airports_with_runways += 1
        
        if airport.procedures:
            airports_with_procedures += 1
        
        if airport.aip_entries:
            airports_with_aip_data += 1
            total_aip_entries += len(airport.aip_entries)
            
            # Count standardized entries
            for entry in airport.aip_entries:
                if entry.is_standardized():
                    standardized_entries += 1
        
        if airport.point_of_entry:
            airports_with_border_crossing += 1
    
    return {
        "total_airports": total_airports,
        "completeness": {
            "coordinates": {
                "count": airports_with_coordinates,
                "percentage": (airports_with_coordinates / total_airports * 100) if total_airports > 0 else 0
            },
            "runways": {
                "count": airports_with_runways,
                "percentage": (airports_with_runways / total_airports * 100) if total_airports > 0 else 0
            },
            "procedures": {
                "count": airports_with_procedures,
                "percentage": (airports_with_procedures / total_airports * 100) if total_airports > 0 else 0
            },
            "aip_data": {
                "count": airports_with_aip_data,
                "percentage": (airports_with_aip_data / total_airports * 100) if total_airports > 0 else 0
            },
            "border_crossing": {
                "count": airports_with_border_crossing,
                "percentage": (airports_with_border_crossing / total_airports * 100) if total_airports > 0 else 0
            }
        },
        "aip_standardization": {
            "total_entries": total_aip_entries,
            "standardized_entries": standardized_entries,
            "standardization_rate": (standardized_entries / total_aip_entries * 100) if total_aip_entries > 0 else 0
        }
    } 