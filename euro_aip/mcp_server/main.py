#!/usr/bin/env python3
"""
MCP Server for Euro AIP Airport Database

This server provides tools for querying airport data, route planning, and flight information
to LLM clients like ChatGPT and Claude.
"""

import asyncio
import logging
import os
import sys
import math
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union
from functools import lru_cache

# Add the euro_aip package to the path
sys.path.insert(0, str(Path(__file__).parent.parent))

from mcp.server import Server
from mcp.server.models import InitializationOptions
from mcp.server.stdio import stdio_server
from mcp.server.lowlevel.server import NotificationOptions
from mcp.types import Tool, Resource

from pydantic import BaseModel, Field, field_validator
from euro_aip.storage.database_storage import DatabaseStorage
from euro_aip.models.euro_aip_model import EuroAipModel
from euro_aip.models.airport import Airport

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Generic Filter System
class AirportFilter:
    """Generic airport filter system that provides consistent filtering across all tools.
    
    This class handles:
    - Filter definitions and metadata
    - Filter application logic
    - Dynamic filter schema generation for tools
    
    Tool requirements are defined directly in the tool definitions.
    """
    
    # Define all available filter types
    FILTER_TYPES = {
        # Basic filters
        'country': {
            'type': 'string',
            'description': 'ISO country code filter',
            'field_type': 'basic',
            'applies_to': ['search', 'route', 'closest', 'border_crossing']
        },
        'has_customs': {
            'type': 'boolean',
            'description': 'Filter for customs facilities',
            'field_type': 'boolean',
            'applies_to': ['search', 'route', 'closest', 'border_crossing']
        },
        'has_avgas': {
            'type': 'boolean',
            'description': 'Filter for AVGAS fuel',
            'field_type': 'boolean',
            'applies_to': ['search', 'route', 'closest']
        },
        'has_jet_a': {
            'type': 'boolean',
            'description': 'Filter for Jet A fuel',
            'field_type': 'boolean',
            'applies_to': ['search', 'route', 'closest']
        },
        'has_restaurant': {
            'type': 'boolean',
            'description': 'Filter for restaurant facilities',
            'field_type': 'standardized_field',
            'field_id': 502,
            'applies_to': ['search', 'route', 'closest']
        },
        'has_hotel': {
            'type': 'boolean',
            'description': 'Filter for hotel facilities',
            'field_type': 'standardized_field',
            'field_id': 501,
            'applies_to': ['search', 'route', 'closest']
        },
        'has_hard_runway': {
            'type': 'boolean',
            'description': 'Filter for hard surface runways',
            'field_type': 'boolean',
            'applies_to': ['search', 'closest']
        },
        'max_results': {
            'type': 'integer',
            'description': 'Maximum number of results',
            'field_type': 'limit',
            'applies_to': ['search', 'route'],
            'default': 20
        },
        'distance_nm': {
            'type': 'number',
            'description': 'Distance in nautical miles',
            'field_type': 'distance',
            'applies_to': ['route'],
            'default': 50.0
        },
        'max_distance_nm': {
            'type': 'number',
            'description': 'Maximum distance in nautical miles',
            'field_type': 'distance',
            'applies_to': ['closest'],
            'default': 100.0
        }
    }
    
    @classmethod
    def get_filter_schema(cls, tool_type: str) -> dict:
        """Get the input schema for a specific tool type."""
        properties = {}
        
        for filter_name, filter_config in cls.FILTER_TYPES.items():
            if tool_type in filter_config['applies_to']:
                properties[filter_name] = {
                    "type": filter_config['type'],
                    "description": filter_config['description']
                }
                if 'default' in filter_config:
                    properties[filter_name]['default'] = filter_config['default']
        
        return properties
    
    # Tool requirements are now defined directly in tool definitions
    
    @classmethod
    def create_filter_dict(cls, arguments: dict, tool_type: str) -> dict:
        """Create a filter dictionary from tool arguments."""
        filters = {}
        
        for filter_name, filter_config in cls.FILTER_TYPES.items():
            if tool_type in filter_config['applies_to']:
                if filter_name in arguments:
                    filters[filter_name] = arguments[filter_name]
        
        return filters
    
    @classmethod
    def apply_filters(cls, airport: Airport, filters: dict) -> bool:
        """Apply all filters to an airport and return True if it passes all filters."""
        
        for filter_name, filter_value in filters.items():
            if filter_value is None:
                continue
                
            if filter_name == 'country':
                if airport.iso_country != filter_value:
                    return False
                    
            elif filter_name == 'has_customs':
                if airport.point_of_entry != filter_value:
                    return False
                    
            elif filter_name == 'has_avgas':
                if airport.avgas != filter_value:
                    return False
                    
            elif filter_name == 'has_jet_a':
                if airport.jet_a != filter_value:
                    return False
                    
            elif filter_name == 'has_hard_runway':
                if airport.has_hard_runway != filter_value:
                    return False
                    
            elif filter_name in ['has_restaurant', 'has_hotel']:
                filter_config = cls.FILTER_TYPES[filter_name]
                if airport.has_standardized_field(filter_config['field_id']) != filter_value:
                    return False
        
        return True

# Configuration
@dataclass(frozen=True)
class ServerConfig:
    """Server configuration with sensible defaults."""
    name: str = "euro_aip"
    version: str = "1.0.0"
    db_path: str = field(default_factory=lambda: os.getenv("AIRPORTS_DB", "../web/server/airports.db"))
    log_level: str = field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO"))

# Enums for type safety
class ProcedureType(str, Enum):
    APPROACH = "approach"
    DEPARTURE = "departure"
    ARRIVAL = "arrival"

class FacilityType(str, Enum):
    CUSTOMS = "customs"
    AVGAS = "avgas"
    JET_A = "jet_a"
    RESTAURANT = "restaurant"

# Standardized field IDs for common facilities
class StandardizedFields:
    CUSTOMS_IMMIGRATION = 302
    FUEL_OIL_TYPES = 402
    RESTAURANTS = 502
    HOTELS = 501
    TRANSPORTATION = 503
    MEDICAL_FACILITIES = 504

# Input validation models with Pydantic V2
class SearchAirportsRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=50)
    country: Optional[str] = Field(None, max_length=3)
    has_customs: Optional[bool] = None
    has_avgas: Optional[bool] = None
    has_jet_a: Optional[bool] = None
    has_restaurant: Optional[bool] = None
    has_hotel: Optional[bool] = None
    has_hard_runway: Optional[bool] = None
    max_results: int = Field(20, ge=1, le=100)

    @field_validator('country')
    @classmethod
    def validate_country(cls, v):
        if v is not None and len(v) not in [2, 3]:
            raise ValueError("Country code must be 2 or 3 characters")
        return v.upper() if v else v

    @field_validator('query')
    @classmethod
    def validate_query(cls, v):
        return v.strip()

class GetAirportDetailsRequest(BaseModel):
    icao_code: str = Field(..., min_length=3, max_length=4)

    @field_validator('icao_code')
    @classmethod
    def validate_icao(cls, v):
        return v.upper().strip()

# Removed unused request models - now using generic filter system

# Service class
class AirportService:
    """Service class encapsulating airport business logic."""
    
    def __init__(self, model: EuroAipModel):
        self.model = model
    
    # Use the generic filter system instead of hardcoded filters
    
    def _matches_search_query(self, airport: Airport, query: str) -> bool:
        """Check if airport matches search query."""
        query_upper = query.upper()
        return (
            query_upper in airport.ident or 
            (airport.name and query_upper in airport.name.upper()) or
            (airport.iata_code and query_upper in airport.iata_code) or
            (airport.municipality and query_upper in airport.municipality.upper())
        )
    
    # Old helper methods removed - now using AirportFilter.apply_filters()
    
    def search_airports(self, request: SearchAirportsRequest) -> List[Airport]:
        """Search airports using the generic filter system."""
        results = []
        
        # Convert request to filter dictionary
        filters = {
            'country': request.country,
            'has_customs': request.has_customs,
            'has_avgas': request.has_avgas,
            'has_jet_a': request.has_jet_a,
            'has_restaurant': request.has_restaurant,
            'has_hotel': request.has_hotel,
            'has_hard_runway': request.has_hard_runway,
        }
        
        for airport in self.model.airports.values():
            # Basic search
            if not self._matches_search_query(airport, request.query):
                continue
            
            # Apply all filters using the generic system
            if not AirportFilter.apply_filters(airport, filters):
                continue
            
            results.append(airport)
            
            if len(results) >= request.max_results:
                break
        
        # Sort by relevance
        def relevance_score(airport: Airport) -> Tuple[bool, bool, bool, bool, int]:
            customs = airport.point_of_entry is True
            avgas = airport.avgas is True
            restaurant = bool(airport.has_standardized_field(StandardizedFields.RESTAURANTS))
            hotel = bool(airport.has_standardized_field(StandardizedFields.HOTELS))
            runway_length = airport.longest_runway_length_ft or 0
            return (customs, avgas, restaurant, hotel, runway_length)
        
        return sorted(results, key=relevance_score, reverse=True)
    
    def find_airports_near_route(self, route_airports: List[str], distance_nm: float, 
                                filters: Optional[Dict[str, Any]] = None) -> List[Dict]:
        """Find airports near route with optional filtering."""
        # Get nearby airports from model
        nearby_airports = self.model.find_airports_near_route(route_airports, distance_nm)
        
        if not filters:
            return nearby_airports
        
        # Apply filters using the generic system
        filtered_airports = []
        route_set = set(route_airports)
        
        for item in nearby_airports:
            airport = item['airport']
            
            # Skip airports that are part of the route
            if airport.ident in route_set:
                continue
            
            # Apply all filters using the generic system
            if not AirportFilter.apply_filters(airport, filters):
                continue
            
            filtered_airports.append(item)
        
        return filtered_airports
    
    def find_closest_airports(self, location: str, filters: Optional[Dict[str, Any]] = None, 
                             max_distance_nm: float = 100.0) -> List[Airport]:
        """Find closest airports to a location with optional filtering."""
        results = []
        location_upper = location.upper()
        
        for airport in self.model.airports.values():
            # Check if location matches airport name or city
            if not (
                (airport.name and location_upper in airport.name.upper()) or
                (airport.municipality and location_upper in airport.municipality.upper())
            ):
                continue
            
            # Apply all filters using the generic system
            if not AirportFilter.apply_filters(airport, filters or {}):
                continue
            
            results.append(airport)
        
        # Sort by runway length (prefer larger airports)
        results.sort(key=lambda x: x.longest_runway_length_ft or 0, reverse=True)
        return results
    
    def get_border_crossing_airports(self, filters: Optional[Dict[str, Any]] = None) -> List[Airport]:
        """Get border crossing airports with optional filtering."""
        border_airports = self.model.get_border_crossing_airports()
        
        if not filters:
            return border_airports
        
        filtered_airports = []
        for airport in border_airports:
            # Apply all filters using the generic system
            if not AirportFilter.apply_filters(airport, filters):
                continue
            
            filtered_airports.append(airport)
        
        return filtered_airports
    
    def get_airport_statistics(self, country: Optional[str] = None) -> Dict[str, Any]:
        """Get airport statistics with optional country filtering."""
        if country:
            airports = self.get_airports_by_country(country)
        else:
            airports = list(self.model.airports.values())
        
        total = len(airports)
        if total == 0:
            return {"total_airports": 0}
        
        # Count facilities directly from airport objects
        stats = {
            "total_airports": total,
            "with_customs": sum(1 for a in airports if a.point_of_entry),
            "with_avgas": sum(1 for a in airports if a.avgas),
            "with_jet_a": sum(1 for a in airports if a.jet_a),
            "with_restaurant": sum(1 for a in airports if a.has_standardized_field(StandardizedFields.RESTAURANTS)),
            "with_hotel": sum(1 for a in airports if a.has_standardized_field(StandardizedFields.HOTELS)),
            "with_hard_runway": sum(1 for a in airports if a.has_hard_runway),
            "with_procedures": sum(1 for a in airports if a.procedures),
            "border_crossing_points": sum(1 for a in airports if a.point_of_entry),
        }
        
        # Add percentages
        for key in list(stats.keys()):
            if key != "total_airports":
                percentage = (stats[key] / total * 100) if total > 0 else 0
                stats[f"{key}_percentage"] = round(percentage, 1)
        
        return stats
    
    def get_airport_procedures(self, icao_code: str, procedure_type: Optional[str] = None, 
                              runway: Optional[str] = None) -> List:
        """Get airport procedures with optional filtering."""
        airport = self.model.get_airport(icao_code)
        if not airport:
            return []
        
        procedures = airport.procedures
        
        # Apply filters
        if procedure_type:
            procedures = [p for p in procedures if p.procedure_type == procedure_type]
        
        if runway:
            procedures = airport.get_procedures_by_runway(runway)
        
        return procedures
    
    def get_airport(self, icao_code: str) -> Optional[Airport]:
        """Get a single airport by ICAO code."""
        return self.model.get_airport(icao_code)
    
    def get_airports_by_country(self, country_code: str) -> List[Airport]:
        """Get all airports in a specific country."""
        return self.model.get_airports_by_country(country_code)

# Response formatter
class ResponseFormatter:
    """Formats responses for different tool calls."""
    
    @staticmethod
    def format_airport_search(airports: List[Airport], query: str) -> str:
        """Format airport search results."""
        if not airports:
            return f"No airports found matching '{query}'."
        
        result = f"Found {len(airports)} airports matching '{query}':\n\n"
        
        for airport in airports:
            result += f"**{airport.ident} - {airport.name}**\n"
            result += f"Location: {airport.municipality or 'Unknown'}, {airport.iso_country or 'Unknown'}"
            
            if airport.latitude_deg and airport.longitude_deg:
                result += f" ({airport.latitude_deg:.4f}, {airport.longitude_deg:.4f})"
            result += "\n"
            
            # Facilities
            facilities = ResponseFormatter._get_facility_list(airport)
            result += f"Facilities: {', '.join(facilities) if facilities else 'None'}\n"
            
            # Runway info
            runway_info = f"{airport.longest_runway_length_ft or 'Unknown'}ft"
            if airport.has_hard_runway:
                runway_info += " (hard surface)"
            result += f"Runway: {runway_info}\n"
            
            result += f"Procedures: {len(airport.procedures)}"
            if airport.point_of_entry:
                result += " (Border crossing)"
            result += "\n\n"
        
        return result
    
    @staticmethod
    def format_airport_details(airport: Airport) -> str:
        """Format detailed airport information."""
        details = f"**{airport.ident} - {airport.name}**\n\n"
        
        details += "**Location:**\n"
        details += f"- City: {airport.municipality or 'Unknown'}\n"
        details += f"- Country: {airport.iso_country or 'Unknown'}\n"
        if airport.latitude_deg and airport.longitude_deg:
            details += f"- Coordinates: {airport.latitude_deg:.4f}, {airport.longitude_deg:.4f}\n"
        if airport.elevation_ft:
            details += f"- Elevation: {airport.elevation_ft}ft\n"
        
        details += "\n**Facilities:**\n"
        for facility in [FacilityType.CUSTOMS, FacilityType.AVGAS, FacilityType.JET_A, FacilityType.RESTAURANT]:
            entry = airport.get_aip_entry_for_field(facility.value)
            value = entry.value if entry else "Not available"
            details += f"- {facility.value.replace('_', ' ').title()}: {value}\n"
        
        details += "\n**Runways:**\n"
        details += f"- Count: {len(airport.runways)}\n"
        details += f"- Longest: {airport.longest_runway_length_ft or 'Unknown'}ft\n"
        details += f"- Hard surface: {'Yes' if airport.has_hard_runway else 'No'}\n"
        details += f"- Lighted: {'Yes' if airport.has_lighted_runway else 'No'}\n"
        
        procedures = airport.procedures
        details += "\n**Procedures:**\n"
        details += f"- Total: {len(procedures)}\n"
        details += f"- Approaches: {len([p for p in procedures if p.procedure_type == 'approach'])}\n"
        details += f"- Departures: {len([p for p in procedures if p.procedure_type == 'departure'])}\n"
        
        details += "\n**Special Status:**\n"
        details += f"- Border crossing point: {'Yes' if airport.point_of_entry else 'No'}\n"
        if hasattr(airport, 'sources') and airport.sources:
            details += f"- Sources: {', '.join(airport.sources)}\n"
        
        # Add all standardized AIP entries
        standardized_entries = airport.get_standardized_entries()
        if standardized_entries:
            details += "\n**Standardized AIP Information:**\n"
            for entry in standardized_entries:
                if entry.std_field and entry.value:
                    details += f"- {entry.std_field}: {entry.value}\n"
        
        return details
    
    @staticmethod
    def format_border_crossing_airports(airports: List[Airport]) -> str:
        """Format border crossing airports."""
        if not airports:
            return "No border crossing airports found."
        
        result = "**Border Crossing Airports:**\n\n"
        
        # Group by country
        by_country = {}
        for airport in airports:
            country_code = airport.iso_country or "Unknown"
            if country_code not in by_country:
                by_country[country_code] = []
            by_country[country_code].append(airport)
        
        for country_code, country_airports in by_country.items():
            result += f"**{country_code}:**\n"
            for airport in country_airports:
                customs_entry = airport.get_aip_entry_for_field(302)  # Customs and immigration
                customs_available = customs_entry and customs_entry.value
                
                result += f"- {airport.ident} - {airport.name}"
                if airport.municipality:
                    result += f" ({airport.municipality})"
                if customs_available:
                    result += " - Customs available"
                result += "\n"
            result += "\n"
        
        return result
    
    @staticmethod
    def format_statistics(stats: Dict[str, Any], country: Optional[str] = None) -> str:
        """Format airport statistics."""
        result = "**Airport Statistics"
        if country:
            result += f" for {country}"
        result += ":**\n\n"
        
        result += f"Total airports: {stats['total_airports']}\n"
        
        if stats['total_airports'] > 0:
            result += f"With customs: {stats['with_customs']} ({stats['with_customs_percentage']}%)\n"
            result += f"With AVGAS: {stats['with_avgas']} ({stats['with_avgas_percentage']}%)\n"
            result += f"With Jet A: {stats['with_jet_a']} ({stats['with_jet_a_percentage']}%)\n"
            result += f"With restaurant: {stats['with_restaurant']} ({stats['with_restaurant_percentage']}%)\n"
            result += f"With hotel: {stats['with_hotel']} ({stats['with_hotel_percentage']}%)\n"
            result += f"With hard runway: {stats['with_hard_runway']} ({stats['with_hard_runway_percentage']}%)\n"
            result += f"With procedures: {stats['with_procedures']} ({stats['with_procedures_percentage']}%)\n"
            result += f"Border crossing points: {stats['border_crossing_points']} ({stats['border_crossing_points_percentage']}%)\n"
        
        return result
    
    @staticmethod
    def format_route_search(airports: List, route_airports: List[str], distance_nm: float) -> str:
        """Format route search results."""
        if not airports:
            return f"No airports found within {distance_nm}nm of the route {', '.join(route_airports)}."
        
        result = f"Found {len(airports)} airports within {distance_nm}nm of route {', '.join(route_airports)}:\n\n"
        
        for item in airports:
            airport = item['airport']
            
            result += f"**{airport.ident} - {airport.name}** (Distance: {item['distance_nm']:.1f}nm)\n"
            result += f"Location: {airport.municipality}, {airport.iso_country}\n"
            
            # Get facilities list using the helper method
            facilities = ResponseFormatter._get_facility_list(airport)
            result += f"Facilities: {', '.join(facilities) if facilities else 'None'}\n"
            result += f"Runway: {airport.longest_runway_length_ft}ft {'(hard surface)' if airport.has_hard_runway else ''}\n\n"
        
        return result
    
    @staticmethod
    def format_closest_airport(airports: List, location: str) -> str:
        """Format closest airport results."""
        if not airports:
            return f"No airports found matching '{location}'."
        
        airport = airports[0]  # Take the first (closest) result
        customs_entry = airport.get_aip_entry_for_field(302)  # Customs and immigration
        
        result = f"**Closest airport to {location}:**\n\n"
        result += f"**{airport.ident} - {airport.name}**\n"
        result += f"Location: {airport.municipality}, {airport.iso_country}\n"
        result += f"Coordinates: {airport.latitude_deg:.4f}, {airport.longitude_deg:.4f}\n"
        result += f"Runway: {airport.longest_runway_length_ft}ft {'(hard surface)' if airport.has_hard_runway else ''}\n"
        result += f"Customs: {'Available' if customs_entry and customs_entry.value else 'Not available'}\n"
        
        return result
    
    @staticmethod
    def format_procedures(airport, procedures: List) -> str:
        """Format airport procedures."""
        if not procedures:
            return f"No procedures found for {airport.ident}."
        
        result = f"**Procedures for {airport.ident} - {airport.name}:**\n\n"
        
        # Group by procedure type
        by_type = {}
        for proc in procedures:
            proc_type = proc.procedure_type
            if proc_type not in by_type:
                by_type[proc_type] = []
            by_type[proc_type].append(proc)
        
        for proc_type, procs in by_type.items():
            result += f"**{proc_type.title()} Procedures:**\n"
            for proc in procs:
                result += f"- {proc.name}"
                if proc.approach_type:
                    result += f" ({proc.approach_type})"
                if proc.runway_ident:
                    result += f" - Runway {proc.runway_ident}"
                result += "\n"
            result += "\n"
        
        return result
    
    @staticmethod
    def _get_facility_list(airport: Airport) -> List[str]:
        """Get list of available facilities for an airport."""
        facilities = []
        
        # Use boolean fields directly where available
        if airport.point_of_entry:
            facilities.append("Customs")
        
        if airport.avgas:
            facilities.append("AVGAS")
        
        if airport.jet_a:
            facilities.append("Jet A")
        
        if airport.has_standardized_field(StandardizedFields.RESTAURANTS):
            facilities.append("Restaurant")
        
        if airport.has_standardized_field(StandardizedFields.HOTELS):
            facilities.append("Hotel")
        
        return facilities

# Error classes
class MCPServerError(Exception):
    """Base exception for MCP server errors."""
    pass

class ValidationError(MCPServerError):
    """Validation error."""
    pass

class AirportNotFoundError(MCPServerError):
    """Airport not found error."""
    pass

# Global instances (simplified approach for working version)
model: Optional[EuroAipModel] = None
airport_service: Optional[AirportService] = None

# Initialize MCP server
server = Server("euro_aip")

@server.list_tools()
async def handle_list_tools() -> list[Tool]:
    """List all available tools."""
    return [
        Tool(
            name="search_airports",
            description="Search for airports by name, ICAO code, or location with various filters",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    **AirportFilter.get_filter_schema('search')
                },
                "required": ["query"]
            }
        ),
        Tool(
            name="get_airport_details",
            description="Get detailed information about a specific airport by ICAO code",
            inputSchema={
                "type": "object",
                "properties": {
                    "icao_code": {"type": "string", "description": "ICAO airport code"}
                },
                "required": ["icao_code"]
            }
        ),
        Tool(
            name="get_border_crossing_airports",
            description="Get all airports that serve as border crossing points",
            inputSchema={
                "type": "object",
                "properties": AirportFilter.get_filter_schema('border_crossing'),
                "required": []
            }
        ),
        Tool(
            name="find_airports_near_route",
            description="Find airports within a specified distance from a flight route",
            inputSchema={
                "type": "object",
                "properties": {
                    "route_airports": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of ICAO airport codes defining the route"
                    },
                    **AirportFilter.get_filter_schema('route')
                },
                "required": ["route_airports"]
            }
        ),
        Tool(
            name="find_closest_airport",
            description="Find the closest airport to a location or city",
            inputSchema={
                "type": "object",
                "properties": {
                    "location": {"type": "string", "description": "City name or location description"},
                    **AirportFilter.get_filter_schema('closest')
                },
                "required": ["location"]
            }
        ),
        Tool(
            name="get_airport_procedures",
            description="Get instrument procedures for a specific airport",
            inputSchema={
                "type": "object",
                "properties": {
                    "icao_code": {"type": "string", "description": "ICAO airport code"},
                    "procedure_type": {
                        "type": "string",
                        "enum": ["approach", "departure", "arrival"],
                        "description": "Type of procedures to retrieve"
                    },
                    "runway": {"type": "string", "description": "Runway identifier (e.g., '13', '31L')"}
                },
                "required": ["icao_code"]
            }
        ),
        Tool(
            name="get_airport_statistics",
            description="Get statistics about the airport database",
            inputSchema={
                "type": "object",
                "properties": AirportFilter.get_filter_schema('border_crossing')
            }
        ),
    ]

@server.list_resources()
async def handle_list_resources() -> list[Resource]:
    """Return an empty resource list."""
    return []

@server.list_prompts()
async def handle_list_prompts() -> list:
    """Return an empty prompts list."""
    return []

@server.call_tool()
async def handle_call_tool(name: str, arguments: Dict[str, Any]):
    """Handle tool calls."""
    global model, airport_service
    
    if not model or not airport_service:
        return {
            "content": [{"type": "text", "text": "Error: Airport database not loaded."}],
            "isError": True
        }
    
    try:
        if name == "search_airports":
            try:
                request = SearchAirportsRequest(**arguments)
                airports = airport_service.search_airports(request)
                response = ResponseFormatter.format_airport_search(airports, request.query)
                return {"content": [{"type": "text", "text": response}]}
            except Exception as e:
                raise ValidationError(f"Invalid search parameters: {e}")
        
        elif name == "get_airport_details":
            try:
                request = GetAirportDetailsRequest(**arguments)
                airport = airport_service.get_airport(request.icao_code)
                if not airport:
                    raise AirportNotFoundError(f"Airport {request.icao_code} not found.")
                response = ResponseFormatter.format_airport_details(airport)
                return {"content": [{"type": "text", "text": response}]}
            except ValidationError:
                raise
            except AirportNotFoundError:
                raise
            except Exception as e:
                raise ValidationError(f"Invalid parameters: {e}")
        
        elif name == "get_border_crossing_airports":
            try:
                # Create filters using the generic system
                filters = AirportFilter.create_filter_dict(arguments, 'border_crossing')
                border_airports = airport_service.get_border_crossing_airports(filters)
                
                response = ResponseFormatter.format_border_crossing_airports(border_airports)
                return {"content": [{"type": "text", "text": response}]}
            except Exception as e:
                raise ValidationError(f"Invalid parameters: {e}")
        
        elif name == "find_airports_near_route":
            try:
                # Simple validation for route airports
                route_airports = arguments.get("route_airports", [])
                if not route_airports or not isinstance(route_airports, list):
                    raise ValidationError("route_airports must be a non-empty list")
                
                # Normalize ICAO codes
                route_airports = [code.upper().strip() for code in route_airports]
                distance_nm = arguments.get("distance_nm", 50.0)
                
                # Create filters using the generic system
                filters = AirportFilter.create_filter_dict(arguments, 'route')
                
                # Find airports near the route with filtering
                nearby_airports = airport_service.find_airports_near_route(route_airports, distance_nm, filters)
                
                response = ResponseFormatter.format_route_search(nearby_airports, route_airports, distance_nm)
                return {"content": [{"type": "text", "text": response}]}
            except Exception as e:
                raise ValidationError(f"Invalid parameters: {e}")
        
        elif name == "find_closest_airport":
            try:
                location = arguments.get("location", "").strip()
                if not location:
                    raise ValidationError("location is required")
                
                # Create filters using the generic system
                filters = AirportFilter.create_filter_dict(arguments, 'closest')
                
                # Find closest airports with filtering
                results = airport_service.find_closest_airports(location, filters)
                
                response = ResponseFormatter.format_closest_airport(results, location)
                return {"content": [{"type": "text", "text": response}]}
            except Exception as e:
                raise ValidationError(f"Invalid parameters: {e}")
        
        elif name == "get_airport_procedures":
            try:
                icao_code = arguments.get("icao_code", "").strip().upper()
                if not icao_code:
                    raise ValidationError("icao_code is required")
                
                procedure_type = arguments.get("procedure_type")
                runway = arguments.get("runway")
                
                # Get procedures using service method
                procedures = airport_service.get_airport_procedures(icao_code, procedure_type, runway)
                
                if not procedures:
                    return {"content": [{"type": "text", "text": f"No procedures found for {icao_code} with the specified criteria."}]}
                
                # Get airport for formatting
                airport = airport_service.get_airport(icao_code)
                response = ResponseFormatter.format_procedures(airport, procedures)
                return {"content": [{"type": "text", "text": response}]}
            except ValidationError:
                raise
            except AirportNotFoundError:
                raise
            except Exception as e:
                raise ValidationError(f"Invalid parameters: {e}")
        
        elif name == "get_airport_statistics":
            try:
                # Create filters using the generic system
                filters = AirportFilter.create_filter_dict(arguments, 'border_crossing')
                country = filters.get('country')
                
                stats = airport_service.get_airport_statistics(country)
                response = ResponseFormatter.format_statistics(stats, country)
                return {"content": [{"type": "text", "text": response}]}
            except Exception as e:
                raise ValidationError(f"Invalid parameters: {e}")
        
        else:
            return {
                "content": [{"type": "text", "text": f"Unknown tool: {name}"}],
                "isError": True
            }
    
    except ValidationError as e:
        logger.warning(f"Validation error in {name}: {e}")
        return {
            "content": [{"type": "text", "text": f"Invalid input: {str(e)}"}],
            "isError": True
        }
    except AirportNotFoundError as e:
        return {
            "content": [{"type": "text", "text": str(e)}],
            "isError": True
        }
    except Exception as e:
        logger.error(f"Error in tool {name}: {e}", exc_info=True)
        return {
            "content": [{"type": "text", "text": f"Internal server error: {str(e)}"}],
            "isError": True
        }

async def main():
    """Main function to run the MCP server."""
    global model, airport_service
    
    # Load the airport database
    config = ServerConfig()
    db_path = config.db_path
    logger.info(f"Loading airport database from: {db_path}")
    
    try:
        db_storage = DatabaseStorage(db_path)
        model = db_storage.load_model()
        airport_service = AirportService(model)
        logger.info(f"Loaded model with {len(model.airports)} airports")
    except Exception as e:
        logger.error(f"Failed to load database: {e}")
        sys.exit(1)
    
    # Run the MCP server
    async with stdio_server() as streams:
        await server.run(
            streams[0],  # read stream
            streams[1],  # write stream
            InitializationOptions(
                server_name=config.name,
                server_version=config.version,
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(
                        prompts_changed=False,
                        resources_changed=False,
                        tools_changed=False,
                    ),
                    experimental_capabilities={},
                ),
            ),
        )

if __name__ == "__main__":
    asyncio.run(main())