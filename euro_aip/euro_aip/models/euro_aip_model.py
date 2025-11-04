from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Any, Callable
from datetime import datetime
import logging
from pathlib import Path
import json

from .airport import Airport
from .runway import Runway
from .aip_entry import AIPEntry
from .procedure import Procedure
from .border_crossing_entry import BorderCrossingEntry
from .navpoint import NavPoint

import math

logger = logging.getLogger(__name__)

@dataclass
class EuroAipModel:
    """
    Main model class that maintains the overall model of all airports and their derived information.
    
    This class serves as the central data store for all airport information collected from
    various sources. It provides methods for adding, updating, and querying airport data.
    """
    
    # Main data store: map from ICAO code to Airport object
    airports: Dict[str, Airport] = field(default_factory=dict)
    
    # Border crossing data: map from country ISO to airport name to entry
    border_crossing_points: Dict[str, Dict[str, BorderCrossingEntry]] = field(default_factory=dict)
    
    # Metadata
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    sources_used: Set[str] = field(default_factory=set)
    
    # Field standardization service
    field_service: Optional['FieldStandardizationService'] = None
    
    def __post_init__(self):
        """Initialize field standardization service if not provided."""
        if self.field_service is None:
            from ..utils.field_standardization_service import FieldStandardizationService
            self.field_service = FieldStandardizationService()
    
    def add_airport(self, airport: Airport) -> None:
        """
        Add or update an airport in the model.
        
        Args:
            airport: Airport object to add or update
        """
        if airport.ident in self.airports:
            # Update existing airport
            existing = self.airports[airport.ident]
            
            # Update basic fields if new data is available
            for field_name, value in airport.__dict__.items():
                if value is not None and field_name not in ['runways', 'aip_entries', 'procedures', 'sources', 'created_at', 'updated_at']:
                    setattr(existing, field_name, value)
            
            # Add runways
            for runway in airport.runways:
                existing.add_runway(runway)
            
            # Add AIP entries
            for entry in airport.aip_entries:
                existing.add_aip_entry(entry)
            
            # Add procedures
            for procedure in airport.procedures:
                existing.add_procedure(procedure)
            
            # Add sources
            for source in airport.sources:
                existing.add_source(source)
                self.sources_used.add(source)
            
            existing.updated_at = datetime.now()
            logger.debug(f"Updated airport {airport.ident} with data from {list(airport.sources)}")
        else:
            # Add new airport
            self.airports[airport.ident] = airport
            for source in airport.sources:
                self.sources_used.add(source)
            logger.debug(f"Added new airport {airport.ident} with data from {list(airport.sources)}")
        
        self.updated_at = datetime.now()
    
    def add_aip_entries_to_airport(self, icao: str, entries: List[AIPEntry], standardize: bool = True) -> None:
        """
        Add AIP entries to a specific airport with optional standardization.
        
        Args:
            icao: ICAO airport code
            entries: List of AIPEntry objects to add
            standardize: Whether to standardize the entries using field service
        """
        if icao not in self.airports:
            logger.warning(f"Airport {icao} not found in model, creating new airport")
            airport = Airport(ident=icao)
            self.airports[icao] = airport
        
        airport = self.airports[icao]
        
        if standardize and self.field_service:
            entries = self.field_service.standardize_aip_entries(entries)
        
        airport.add_aip_entries(entries)
        logger.debug(f"Added {len(entries)} AIP entries to {icao}")
    
    def get_airports_with_standardized_aip_data(self) -> List[Airport]:
        """
        Get all airports that have standardized AIP data.
        
        Returns:
            List of airports with standardized AIP data
        """
        return [airport for airport in self.airports.values() 
                if airport.get_standardized_entries()]
    
    def get_field_mapping_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about field mapping across all airports.
        
        Returns:
            Dictionary with field mapping statistics
        """
        all_entries = []
        for airport in self.airports.values():
            all_entries.extend(airport.aip_entries)
        
        if self.field_service:
            return self.field_service.get_mapping_statistics(all_entries)
        else:
            return {
                'total_fields': len(all_entries),
                'mapped_fields': 0,
                'unmapped_fields': len(all_entries),
                'mapping_rate': 0.0,
                'average_mapping_score': 0.0,
                'section_counts': {}
            }
    
    def get_airport(self, icao: str) -> Optional[Airport]:
        """
        Get an airport by ICAO code.
        
        Args:
            icao: ICAO airport code
            
        Returns:
            Airport object or None if not found
        """
        return self.airports.get(icao)
    
    def get_airports_by_country(self, country_code: str) -> List[Airport]:
        """
        Get all airports in a specific country.
        
        Args:
            country_code: ISO country code
            
        Returns:
            List of airports in the country
        """
        return [airport for airport in self.airports.values() 
                if airport.iso_country == country_code]
    
    def get_airports_by_source(self, source_name: str) -> List[Airport]:
        """
        Get all airports that have data from a specific source.
        
        Args:
            source_name: Name of the source
            
        Returns:
            List of airports with data from the source
        """
        return [airport for airport in self.airports.values() 
                if source_name in airport.sources]
    
    def get_airports_with_procedures(self, procedure_type: Optional[str] = None) -> List[Airport]:
        """
        Get all airports that have procedures.
        
        Args:
            procedure_type: Optional procedure type filter
            
        Returns:
            List of airports with procedures
        """
        if procedure_type:
            return [airport for airport in self.airports.values() 
                    if airport.get_procedures_by_type(procedure_type)]
        else:
            return [airport for airport in self.airports.values() 
                    if airport.procedures]
    
    def get_airports_with_runways(self) -> List[Airport]:
        """
        Get all airports that have runway information.
        
        Returns:
            List of airports with runways
        """
        return [airport for airport in self.airports.values() 
                if airport.runways]
    
    def get_airports_with_aip_data(self) -> List[Airport]:
        """
        Get all airports that have AIP data.
        
        Returns:
            List of airports with AIP data
        """
        return [airport for airport in self.airports.values() 
                if airport.aip_entries]
    
    def get_statistics(self) -> Dict[str, any]:
        """
        Get statistics about the model.
        
        Returns:
            Dictionary with model statistics
        """
        total_airports = len(self.airports)
        airports_with_runways = len(self.get_airports_with_runways())
        airports_with_procedures = len(self.get_airports_with_procedures())
        airports_with_aip_data = len(self.get_airports_with_aip_data())
        airports_with_border_crossing = len(self.get_border_crossing_airports())
        
        total_runways = sum(len(airport.runways) for airport in self.airports.values())
        total_procedures = sum(len(airport.procedures) for airport in self.airports.values())
        total_aip_entries = sum(len(airport.aip_entries) for airport in self.airports.values())
        total_border_crossing_points = len(self.get_all_border_crossing_points())
        
        # Count procedures by type
        procedure_types = {}
        for airport in self.airports.values():
            for procedure in airport.procedures:
                proc_type = procedure.procedure_type.lower()
                procedure_types[proc_type] = procedure_types.get(proc_type, 0) + 1
        
        # Get border crossing statistics
        border_crossing_stats = self.get_border_crossing_statistics()
        
        return {
            'total_airports': total_airports,
            'airports_with_runways': airports_with_runways,
            'airports_with_procedures': airports_with_procedures,
            'airports_with_aip_data': airports_with_aip_data,
            'airports_with_border_crossing': airports_with_border_crossing,
            'total_runways': total_runways,
            'total_procedures': total_procedures,
            'total_aip_entries': total_aip_entries,
            'total_border_crossing_points': total_border_crossing_points,
            'procedure_types': procedure_types,
            'border_crossing': border_crossing_stats,
            'sources_used': list(self.sources_used),
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }
    
    
    def to_dict(self) -> Dict[str, any]:
        """
        Convert the model to a dictionary for JSON serialization.
        
        Returns:
            Dictionary representation of the model
        """
        return {
            'airports': {icao: airport.to_dict() for icao, airport in self.airports.items()},
            'border_crossing_points': {
                country_iso: {
                    icao_code: entry.to_dict() 
                    for icao_code, entry in country_entries.items()
                }
                for country_iso, country_entries in self.border_crossing_points.items()
            },
            'statistics': self.get_statistics()
        }
    
    
    
    def __repr__(self):
        return f"EuroAipModel(airports={len(self.airports)}, sources={list(self.sources_used)})"
    
    def __str__(self):
        stats = self.get_statistics()
        return f"""EuroAipModel:
- Total airports: {stats['total_airports']}
- Airports with runways: {stats['airports_with_runways']}
- Airports with procedures: {stats['airports_with_procedures']}
- Airports with AIP data: {stats['airports_with_aip_data']}
- Airports with border crossing: {stats['airports_with_border_crossing']}
- Total runways: {stats['total_runways']}
- Total procedures: {stats['total_procedures']}
- Total AIP entries: {stats['total_aip_entries']}
- Total border crossing entries: {stats['total_border_crossing_points']}
- Sources used: {', '.join(stats['sources_used'])}
- Created: {stats['created_at']}
- Updated: {stats['updated_at']}"""
    
    def get_procedures_by_runway(self, airport_icao: str, runway_ident: str) -> List['Procedure']:
        """Get all procedures for a specific runway at an airport."""
        airport = self.get_airport(airport_icao)
        if not airport:
            return []
        return airport.get_procedures_by_runway(runway_ident)
    
    def get_approaches_by_runway(self, airport_icao: str, runway_ident: str) -> List['Procedure']:
        """Get all approach procedures for a specific runway at an airport."""
        airport = self.get_airport(airport_icao)
        if not airport:
            return []
        return airport.get_approaches_by_runway(runway_ident)
    
    def get_departures_by_runway(self, airport_icao: str, runway_ident: str) -> List['Procedure']:
        """Get all departure procedures for a specific runway at an airport."""
        airport = self.get_airport(airport_icao)
        if not airport:
            return []
        return airport.get_departures_by_runway(runway_ident)
    
    def get_arrivals_by_runway(self, airport_icao: str, runway_ident: str) -> List['Procedure']:
        """Get all arrival procedures for a specific runway at an airport."""
        airport = self.get_airport(airport_icao)
        if not airport:
            return []
        return airport.get_arrivals_by_runway(runway_ident)
    
    def get_all_approaches(self) -> Dict[str, List['Procedure']]:
        """Get all approach procedures across all airports."""
        result = {}
        for icao, airport in self.airports.items():
            approaches = airport.get_approaches()
            if approaches:
                result[icao] = approaches
        return result
    
    def get_all_departures(self) -> Dict[str, List['Procedure']]:
        """Get all departure procedures across all airports."""
        result = {}
        for icao, airport in self.airports.items():
            departures = airport.get_departures()
            if departures:
                result[icao] = departures
        return result
    
    def get_all_arrivals(self) -> Dict[str, List['Procedure']]:
        """Get all arrival procedures across all airports."""
        result = {}
        for icao, airport in self.airports.items():
            arrivals = airport.get_arrivals()
            if arrivals:
                result[icao] = arrivals
        return result
    
    def get_procedures_by_source(self, source: str) -> Dict[str, List['Procedure']]:
        """Get all procedures from a specific source across all airports."""
        result = {}
        for icao, airport in self.airports.items():
            procedures = airport.get_procedures_by_source(source)
            if procedures:
                result[icao] = procedures
        return result
    
    def get_procedures_by_authority(self, authority: str) -> Dict[str, List['Procedure']]:
        """Get all procedures from a specific authority across all airports."""
        result = {}
        for icao, airport in self.airports.items():
            procedures = airport.get_procedures_by_authority(authority)
            if procedures:
                result[icao] = procedures
        return result
    
    def get_runway_procedures_summary(self, airport_icao: str) -> Dict[str, Dict[str, List[str]]]:
        """Get a summary of procedures by runway and type for a specific airport."""
        airport = self.get_airport(airport_icao)
        if not airport:
            return {}
        return airport.get_runway_procedures_summary()
    
    def get_all_runway_procedures_summary(self) -> Dict[str, Dict[str, Dict[str, List[str]]]]:
        """Get a summary of procedures by runway and type for all airports."""
        result = {}
        for icao, airport in self.airports.items():
            summary = airport.get_runway_procedures_summary()
            if summary:
                result[icao] = summary
        return result
    
    # Border crossing methods
    
    def add_border_crossing_entry(self, entry: BorderCrossingEntry) -> None:
        """
        Add a border crossing entry to the model.
        
        Args:
            entry: BorderCrossingEntry to add
        """
        country_iso = entry.country_iso
        icao_code = entry.icao_code or entry.matched_airport_icao

        # the model only stores airports
        # If is_airport is None but we have an ICAO code, treat it as an airport
        if entry.is_airport is False:
            return

        if not icao_code:
            logger.warning(f"Border crossing entry for {entry.airport_name} has no ICAO code, skipping")
            return

        # Only add border crossing entries for airports that are in the model
        if icao_code not in self.airports:
            return
        if country_iso not in self.border_crossing_points:
            self.border_crossing_points[country_iso] = {}

        
        # Check if there's already an entry with this ICAO code
        if icao_code in self.border_crossing_points[country_iso]:
            existing_entry = self.border_crossing_points[country_iso][icao_code]
            
            # Use is_more_complete_than logic to decide which entry to keep
            if entry.is_more_complete_than(existing_entry):
                # New entry is more complete, replace the existing one
                self.border_crossing_points[country_iso][icao_code] = entry
                logger.debug(f"Replaced border crossing entry for {entry.airport_name} ({icao_code}) in {country_iso} with more complete entry")
            else:
                # Existing entry is more complete or equal, keep the existing one
                logger.debug(f"Kept existing border crossing entry for {existing_entry.airport_name} ({icao_code}) in {country_iso} as it is more complete")
        else:
            # No existing entry, add the new one
            self.border_crossing_points[country_iso][icao_code] = entry
            logger.debug(f"Added border crossing entry for {entry.airport_name} ({icao_code}) in {country_iso}")
        
        self.sources_used.add(entry.source)
        self.updated_at = datetime.now()
    
    def add_border_crossing_points(self, entries: List[BorderCrossingEntry]) -> None:
        """
        Add multiple border crossing entries to the model.
        
        Args:
            entries: List of BorderCrossingEntry objects to add
        """
        for entry in entries:
            self.add_border_crossing_entry(entry)
        
        logger.info(f"Added {len(entries)} border crossing entries to model")
    
    def get_border_crossing_points_by_country(self, country_iso: str) -> List[BorderCrossingEntry]:
        """
        Get all border crossing entries for a specific country.
        
        Args:
            country_iso: ISO country code
            
        Returns:
            List of border crossing entries for the country
        """
        if country_iso not in self.border_crossing_points:
            return []
        
        return list(self.border_crossing_points[country_iso].values())
    
    def get_border_crossing_entry(self, country_iso: str, icao_code: str) -> Optional[BorderCrossingEntry]:
        """
        Get a specific border crossing entry.
        
        Args:
            country_iso: ISO country code
            icao_code: ICAO code of the airport
            
        Returns:
            BorderCrossingEntry if found, None otherwise
        """
        if country_iso not in self.border_crossing_points:
            return None
        
        return self.border_crossing_points[country_iso].get(icao_code)
    
    def get_border_crossing_entry_by_name(self, country_iso: str, airport_name: str) -> Optional[BorderCrossingEntry]:
        """
        Get a border crossing entry by airport name (for backward compatibility).
        
        Args:
            country_iso: ISO country code
            airport_name: Name of the airport
            
        Returns:
            BorderCrossingEntry if found, None otherwise
        """
        if country_iso not in self.border_crossing_points:
            return None
        
        for entry in self.border_crossing_points[country_iso].values():
            if entry.airport_name == airport_name:
                return entry
        
        return None
    
    def get_all_border_crossing_points(self) -> List[BorderCrossingEntry]:
        """
        Get all border crossing entries in the model.
        
        Returns:
            List of all border crossing entries
        """
        all_entries = []
        for country_entries in self.border_crossing_points.values():
            all_entries.extend(country_entries.values())
        return all_entries
    
    def get_border_crossing_countries(self) -> List[str]:
        """
        Get list of countries that have border crossing entries.
        
        Returns:
            List of ISO country codes
        """
        return list(self.border_crossing_points.keys())
    
    def remove_border_crossing_points_by_country(self, country_iso: str) -> None:
        """
        Remove all border crossing entries for a specific country.
        
        Args:
            country_iso: ISO country code
        """
        if country_iso in self.border_crossing_points:
            removed_count = len(self.border_crossing_points[country_iso])
            del self.border_crossing_points[country_iso]
            self.updated_at = datetime.now()
            logger.info(f"Removed {removed_count} border crossing entries for country {country_iso}")
        else:
            logger.debug(f"No border crossing entries found for country {country_iso}")
    
    def get_border_crossing_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about border crossing entries.
        
        Returns:
            Dictionary with border crossing statistics
        """
        total_entries = len(self.get_all_border_crossing_points())
        countries_count = len(self.border_crossing_points)
        
        # Count matched vs unmatched
        matched_count = 0
        unmatched_count = 0
        for entry in self.get_all_border_crossing_points():
            if entry.matched_airport_icao:
                matched_count += 1
            else:
                unmatched_count += 1
        
        # Count by source
        source_counts = {}
        for entry in self.get_all_border_crossing_points():
            source = entry.source or 'unknown'
            source_counts[source] = source_counts.get(source, 0) + 1
        
        # Count by country
        country_counts = {}
        for country_iso, entries in self.border_crossing_points.items():
            country_counts[country_iso] = len(entries)
        
        return {
            'total_entries': total_entries,
            'countries_count': countries_count,
            'matched_count': matched_count,
            'unmatched_count': unmatched_count,
            'match_rate': matched_count / total_entries if total_entries > 0 else 0,
            'by_source': source_counts,
            'by_country': country_counts
        }
    
    def get_border_crossing_airports(self) -> List[Airport]:
        """
        Get all airports that are border crossing points.
        
        Returns:
            List of airports that are border crossing points
        """
        border_airports = []
        for entry in self.get_all_border_crossing_points():
            if entry.icao_code in self.airports:
                border_airports.append(self.airports[entry.icao_code])
        
        return border_airports
    
    def update_all_derived_fields(self) -> None:
        """
        Update all calculated/derived fields across the model.
        This should be called after loading the model to ensure all
        connections and derived information are properly set.
        """
        logger.info("Updating all derived fields...")
        
        # Update border crossing information
        self._update_border_crossing_airports()
        
        # Update runway characteristics
        self._update_runway_characteristics()
        
        # Future: Add more derived field updates here
        # self._update_approach_precision_rankings()
        # self._update_airport_categories()
        # etc.
        
        logger.info("All derived fields updated successfully")
    
    def _update_border_crossing_airports(self) -> None:
        """
        Update airport objects with border crossing information.
        """
        updated_count = 0
        for entry in self.get_all_border_crossing_points():
            # Use the same logic as add_border_crossing_entry
            icao_code = entry.icao_code or entry.matched_airport_icao
            if icao_code and icao_code in self.airports:
                airport = self.airports[icao_code]
                airport.point_of_entry = True
                airport.add_source('border_crossing')
                updated_count += 1
        
        logger.info(f"Updated {updated_count} airports with border crossing information")
    
    def _update_runway_characteristics(self) -> None:
        """
        Update airport objects with runway characteristics.
        """
        from ..utils.runway_classifier import is_hard_surface, is_soft_surface, is_water_surface, is_snow_surface
        
        updated_count = 0
        for airport in self.airports.values():
            has_hard_runway = False
            has_soft_runway = False
            has_water_runway = False
            has_snow_runway = False
            has_lighted_runway = False
            longest_runway_length = 0
            
            for runway in airport.runways:
                # Check for different surface types using utility functions
                if runway.surface:
                    if is_hard_surface(runway.surface):
                        has_hard_runway = True
                    elif is_soft_surface(runway.surface):
                        has_soft_runway = True
                    elif is_water_surface(runway.surface):
                        has_water_runway = True
                    elif is_snow_surface(runway.surface):
                        has_snow_runway = True
                
                # Check for lighted runways
                if runway.lighted:
                    has_lighted_runway = True
                
                # Track longest runway
                if runway.length_ft and runway.length_ft > longest_runway_length:
                    longest_runway_length = runway.length_ft
            
            # Update airport with derived runway characteristics
            airport.has_hard_runway = has_hard_runway
            airport.has_soft_runway = has_soft_runway
            airport.has_water_runway = has_water_runway
            airport.has_snow_runway = has_snow_runway
            airport.has_lighted_runway = has_lighted_runway
            airport.longest_runway_length_ft = longest_runway_length if longest_runway_length > 0 else None
            
            if (has_hard_runway or has_soft_runway or has_water_runway or 
                has_snow_runway or has_lighted_runway or longest_runway_length > 0):
                updated_count += 1
        
        logger.info(f"Updated {updated_count} airports with runway characteristics")
    
    def update_border_crossing_airports(self) -> None:
        """
        Legacy method - now calls the centralized update function.
        Kept for backward compatibility.
        """
        self._update_border_crossing_airports() 

    def find_airports_near_route(self, route_airports: List[str], distance_nm: float = 50.0) -> List[Dict[str, Any]]:
        """
        Find all airports within a specified distance from a route defined by airport ICAO codes.
        For single airports, treats them as a point search within the specified distance.
        
        Args:
            route_airports: List of ICAO airport codes defining the route
            distance_nm: Distance in nautical miles from the route (default: 50.0)
            
        Returns:
            List of dictionaries containing airport data and distance information
        """
        if len(route_airports) < 1:
            logger.warning("Route must contain at least 1 airport")
            return []
        
        # Convert route airports to NavPoints
        route_points = []
        for icao in route_airports:
            airport = self.get_airport(icao.upper())
            if not airport or not airport.latitude_deg or not airport.longitude_deg:
                logger.warning(f"Airport {icao} not found or missing coordinates, skipping")
                continue
            navpoint = airport.navpoint
            if navpoint:
                route_points.append(navpoint)
        
        if len(route_points) < 1:
            logger.warning("No valid airports in route")
            return []
        
        # Find airports near the route
        nearby_airports = []
        
        for airport in self.airports.values():
            
            airport_point = airport.navpoint
            if not airport_point:
                continue  # Skip airports without coordinates
            
            # Calculate minimum distance to the route
            min_distance = float('inf')
            closest_segment = None
            
            if len(route_points) == 1:
                # Single airport: calculate direct distance to the point
                _, min_distance = airport_point.haversine_distance(route_points[0])
                closest_segment = (route_points[0].name, route_points[0].name)
            else:
                # Multiple airports: calculate minimum distance to any segment of the route
                for i in range(len(route_points) - 1):
                    segment_distance = airport_point.distance_to_segment(
                        route_points[i], route_points[i + 1]
                    )
                    if segment_distance < min_distance:
                        min_distance = segment_distance
                        closest_segment = (route_points[i].name, route_points[i + 1].name)
            
            # Check if airport is within the specified distance
            if min_distance <= distance_nm:
                nearby_airports.append({
                    'airport': airport,
                    'distance_nm': round(min_distance, 2),
                    'closest_segment': closest_segment
                })
        
        # Sort by distance
        nearby_airports.sort(key=lambda x: x['distance_nm'])
        
        logger.info(f"Found {len(nearby_airports)} airports within {distance_nm}nm of route")
        return nearby_airports
    

    
    def _distance_to_line_segment2(self, point: NavPoint, line_start: NavPoint, line_end: NavPoint) -> float:
        """
        Calculate the shortest distance from a point to a great-circle segment defined by two points.
        Returns distance in nautical miles.
        """
        EARTH_RADIUS_NM = 3440.065  # nautical miles

        # Distances
        _, dist_AP = line_start.haversine_distance(point)
        _, dist_AB = line_start.haversine_distance(line_end)
        _, dist_BP = line_end.haversine_distance(point)

        # If segment is very short, just return distance to closest endpoint
        if dist_AB < 0.1:  # Less than 0.1nm
            return min(dist_AP, dist_BP)

        # Bearings in degrees
        bearing_AB, _ = line_start.haversine_distance(line_end)
        bearing_AP, _ = line_start.haversine_distance(point)

        # Convert to radians
        δ13 = dist_AP / EARTH_RADIUS_NM
        θ13 = math.radians(bearing_AP)
        θ12 = math.radians(bearing_AB)

        # Cross-track distance
        d_xt = math.asin(math.sin(δ13) * math.sin(θ13 - θ12)) * EARTH_RADIUS_NM

        # Handle numerical instability when point is very close to line
        if abs(d_xt) < 0.001:  # Point is very close to the great circle line
            # Calculate along-track distance more carefully
            cos_ratio = math.cos(δ13) / max(math.cos(d_xt / EARTH_RADIUS_NM), 0.0001)
            cos_ratio = max(min(cos_ratio, 1.0), -1.0)  # Clamp to valid range
            d_at = math.acos(cos_ratio) * EARTH_RADIUS_NM
        else:
            # Standard along-track calculation
            cos_ratio = math.cos(δ13) / math.cos(d_xt / EARTH_RADIUS_NM)
            cos_ratio = max(min(cos_ratio, 1.0), -1.0)  # Clamp to valid range
            d_at = math.acos(cos_ratio) * EARTH_RADIUS_NM

        # Check if projection falls within the segment
        if d_at < 0:
            return dist_AP  # closest to start
        elif d_at > dist_AB:
            return dist_BP  # closest to end
        else:
            return abs(d_xt)
    
    def analyze_fields_with_interpreters(
        self, 
        interpreters: List['BaseInterpreter'], 
        country_filter: Optional[str] = None,
        airport_filter: Optional[List[str]] = None,
        custom_filter: Optional[Callable[['Airport'], bool]] = None
    ) -> Dict[str, 'InterpretationResult']:
        """
        Analyze multiple field types across airports using interpreters.
        
        Args:
            interpreters: List of interpreters to use for field analysis
            country_filter: Optional ISO country code to filter airports
            airport_filter: Optional list of specific airport ICAO codes
            custom_filter: Optional custom filter function taking Airport and returning bool
            
        Returns:
            Dictionary mapping interpreter names to InterpretationResult
        """
        from ..interp.base import InterpretationResult
        
        # Start with all airports
        candidate_airports = list(self.airports.keys())
        
        # Apply filters in intersection (all must pass)
        if country_filter:
            country_airports = [
                icao for icao, airport in self.airports.items()
                if airport.iso_country == country_filter
            ]
            candidate_airports = list(set(candidate_airports) & set(country_airports))
            logger.info(f"Country filter '{country_filter}': {len(candidate_airports)} airports")
        
        if airport_filter:
            airport_airports = [
                icao for icao in candidate_airports
                if icao in airport_filter
            ]
            candidate_airports = airport_airports
            logger.info(f"Airport filter: {len(candidate_airports)} airports")
        
        if custom_filter:
            custom_airports = [
                icao for icao in candidate_airports
                if custom_filter(self.airports[icao])
            ]
            candidate_airports = custom_airports
            logger.info(f"Custom filter: {len(candidate_airports)} airports")
        
        logger.info(f"Final candidate airports: {len(candidate_airports)}")
        
        # Process each interpreter
        results = {}
        
        for interpreter in interpreters:
            interpreter_name = interpreter.get_interpreter_name()
            field_id = interpreter.get_standard_field_id()
            
            logger.info(f"Processing {interpreter_name} interpreter for field {field_id}")
            
            successful = {}
            failed = []
            missing = []
            
            # Find airports with this field
            airports_with_field = []
            for icao in candidate_airports:
                airport = self.airports[icao]
                entry = airport.get_aip_entry_for_field(field_id)
                if entry and entry.value:
                    airports_with_field.append(icao)
            
            logger.info(f"Found {len(airports_with_field)} airports with field {field_id}")
            
            # Process each airport with the field
            for icao in airports_with_field:
                airport = self.airports[icao]
                entry = airport.get_aip_entry_for_field(field_id)
                
                if not entry or not entry.value:
                    missing.append(icao)
                    continue
                
                # Try to interpret the field value
                try:
                    interpreted_data = interpreter.interpret_field_value(entry.value, airport)
                    if interpreted_data:
                        successful[icao] = interpreted_data
                    else:
                        failed.append({
                            'airport_icao': icao,
                            'field_value': entry.value,
                            'reason': 'No structured data extracted',
                            'interpreter': interpreter_name
                        })
                except Exception as e:
                    failed.append({
                        'airport_icao': icao,
                        'field_value': entry.value,
                        'reason': f'Exception: {str(e)}',
                        'interpreter': interpreter_name
                    })
            
            # Create result for this interpreter
            results[interpreter_name] = InterpretationResult(
                successful=successful,
                failed=failed,
                missing=missing
            )
            
            logger.info(f"{interpreter_name}: {len(successful)} successful, {len(failed)} failed, {len(missing)} missing")
        
        return results