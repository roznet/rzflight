from dataclasses import dataclass, field
from typing import Optional, List, Dict, Set, Any
from datetime import datetime
from euro_aip.models.runway import Runway
from euro_aip.models.aip_entry import AIPEntry
from euro_aip.models.procedure import Procedure
from euro_aip.models.navpoint import NavPoint

# Shared constants for approach precision
APPROACH_PRECISION_ORDER = ['ILS', 'RNP', 'RNAV', 'LOC', 'LDA', 'SDF', 'VOR', 'NDB']

@dataclass
class Airport:
    """Data class for storing airport information."""
    
    ident: str  # ICAO code
    type: Optional[str] = None
    name: Optional[str] = None
    latitude_deg: Optional[float] = None
    longitude_deg: Optional[float] = None
    elevation_ft: Optional[str] = None
    continent: Optional[str] = None
    iso_country: Optional[str] = None
    iso_region: Optional[str] = None
    municipality: Optional[str] = None
    scheduled_service: Optional[str] = None
    gps_code: Optional[str] = None
    iata_code: Optional[str] = None
    local_code: Optional[str] = None
    home_link: Optional[str] = None
    wikipedia_link: Optional[str] = None
    keywords: Optional[str] = None

    # AIP data
    point_of_entry: Optional[bool] = None
    avgas : Optional[bool] = None
    jet_a : Optional[bool] = None
    
    # Derived runway characteristics
    has_hard_runway: Optional[bool] = None
    has_lighted_runway: Optional[bool] = None
    has_soft_runway: Optional[bool] = None
    has_water_runway: Optional[bool] = None
    has_snow_runway: Optional[bool] = None
    longest_runway_length_ft: Optional[int] = None
    
    # Source tracking
    sources: Set[str] = field(default_factory=set)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    
    # Relationships
    runways: List['Runway'] = field(default_factory=list)
    aip_entries: List['AIPEntry'] = field(default_factory=list)
    procedures: List['Procedure'] = field(default_factory=list)

    @property
    def navpoint(self) -> Optional[NavPoint]:
        """Get NavPoint representation of this airport."""
        if not hasattr(self, '_navpoint') or self._navpoint is None:
            if self.latitude_deg is not None and self.longitude_deg is not None:
                self._navpoint = NavPoint(
                    latitude=self.latitude_deg,
                    longitude=self.longitude_deg,
                    name=self.ident
                )
            else:
                self._navpoint = None
        return self._navpoint
    
    @navpoint.setter
    def navpoint(self, value: NavPoint):
        """Set NavPoint and update coordinates."""
        self._navpoint = value
        if value:
            self.latitude_deg = value.latitude
            self.longitude_deg = value.longitude
    
    def get_authority(self) -> str:
        """Get the authority for the airport."""
        # get the authority from the ICAO code first 2 letters
        authority = self.ident[:2]
        if authority == 'ET':
            authority = 'ED'
        return authority + 'C'
    
    def add_source(self, source_name: str):
        """Add a source to the tracking set."""
        self.sources.add(source_name)
        self.updated_at = datetime.now()
    
    def add_runway(self, runway: 'Runway'):
        """Add a runway to the airport."""
        # Check if runway already exists
        existing_runway = next((r for r in self.runways if r.le_ident == runway.le_ident and r.he_ident == runway.he_ident), None)
        if existing_runway:
            # Update existing runway with new data
            for field, value in runway.__dict__.items():
                if value is not None and field != 'created_at':
                    setattr(existing_runway, field, value)
        else:
            self.runways.append(runway)
    
    def add_aip_entry(self, entry: 'AIPEntry'):
        """Add an AIP entry to the airport."""
        # Check if entry already exists
        existing_entry = next((e for e in self.aip_entries 
                             if e.section == entry.section and e.field == entry.field), None)
        if existing_entry:
            # Update existing entry
            existing_entry.value = entry.value
            existing_entry.alt_field = entry.alt_field
            existing_entry.alt_value = entry.alt_value
            # Update standardized fields if provided
            if entry.std_field:
                existing_entry.std_field = entry.std_field
                existing_entry.std_field_id = entry.std_field_id
                existing_entry.mapping_score = entry.mapping_score
        else:
            self.aip_entries.append(entry)
    
    def add_aip_entries(self, entries: List['AIPEntry']):
        """Add multiple AIP entries to the airport."""
        for entry in entries:
            self.add_aip_entry(entry)
    
    def get_standardized_aip_data(self) -> Dict[str, str]:
        """
        Get standardized AIP field data as dictionary.
        
        Returns:
            Dictionary mapping standardized field names to values
        """
        return {entry.std_field: entry.value 
                for entry in self.aip_entries 
                if entry.std_field is not None}
    
    def get_aip_entries_by_section(self, section: str) -> List['AIPEntry']:
        """Get all AIP entries for a specific section."""
        return [entry for entry in self.aip_entries if entry.section == section]
    
    def get_standardized_entries(self) -> List['AIPEntry']:
        """Get all AIP entries that have been standardized."""
        return [entry for entry in self.aip_entries if entry.is_standardized()]
    
    def get_unstandardized_entries(self) -> List['AIPEntry']:
        """Get all AIP entries that have not been standardized."""
        return [entry for entry in self.aip_entries if not entry.is_standardized()]
    def get_aip_entry_for_field(self, std_field_id: int) -> Optional['AIPEntry']:
        """Get AIP entry for a specific field."""
        return next((entry for entry in self.aip_entries if entry.std_field_id == std_field_id), None)
    
    def get_aip_entry_by_field(self, field_name: str, use_standardized: bool = True) -> Optional['AIPEntry']:
        """
        Get AIP entry by field name.
        
        Args:
            field_name: Field name to search for
            use_standardized: If True, search by standardized field name first
            
        Returns:
            AIPEntry if found, None otherwise
        """
        if use_standardized:
            # Try standardized field first
            for entry in self.aip_entries:
                if entry.std_field == field_name:
                    return entry
        
        # Fall back to original field name
        for entry in self.aip_entries:
            if entry.field == field_name:
                return entry
        
        return None
    
    def add_procedure(self, procedure: 'Procedure'):
        """Add a procedure to the airport."""
        # Check if procedure already exists
        existing_procedure = next((p for p in self.procedures 
                                 if p.name == procedure.name and p.procedure_type == procedure.procedure_type), None)
        if existing_procedure:
            # Update existing procedure with new data
            for field, value in procedure.__dict__.items():
                if value is not None and field not in ['created_at', 'updated_at']:
                    setattr(existing_procedure, field, value)
            existing_procedure.updated_at = datetime.now()
        else:
            self.procedures.append(procedure)
    
    def get_procedures_by_type(self, procedure_type: str) -> List['Procedure']:
        """Get all procedures of a specific type."""
        return [p for p in self.procedures if p.procedure_type.lower() == procedure_type.lower()]
    
    def get_procedures_by_runway(self, runway_ident: str) -> List['Procedure']:
        """Get all procedures for a specific runway."""
        return [p for p in self.procedures if p.matches_runway(runway_ident)]
    
    def get_approaches_by_runway(self, runway: Runway) -> List['Procedure']:
        """Get all approach procedures for a specific runway."""
        return [p for p in self.procedures 
                if p.is_approach() and p.matches_runway(runway)]
    
    def get_most_precise_approach_for_runway(self, runway: Runway) -> Optional['Procedure']:
        """
        Get the most precise approach procedure for a specific runway.
        
        Args:
            runway: The runway to get approaches for
            
        Returns:
            The most precise approach procedure, or None if no approaches exist
        """
        approaches = self.get_approaches_by_runway(runway)
        if not approaches:
            return None
        
        # Sort by precision (most precise first) and return the first one
        approaches.sort(key=lambda p: p.get_approach_precision())
        return approaches[0]
    
    def get_most_precise_approach_for_runway_end(self, runway: Runway, runway_end_ident: str) -> Optional['Procedure']:
        """
        Get the most precise approach procedure for a specific runway end.
        
        Args:
            runway: The runway to get approaches for
            runway_end_ident: The runway end identifier (e.g., '13L', '31R')
            
        Returns:
            The most precise approach procedure for the runway end, or None if no approaches exist
        """
        approaches = [p for p in self.procedures 
                     if p.is_approach() and p.runway_ident == runway_end_ident]
        
        if not approaches:
            return None
        
        # Sort by precision (most precise first) and return the first one
        approaches.sort(key=lambda p: p.get_approach_precision())
        return approaches[0]
    
    def get_departures_by_runway(self, runway_ident: str) -> List['Procedure']:
        """Get all departure procedures for a specific runway."""
        return [p for p in self.procedures 
                if p.is_departure() and p.matches_runway(runway_ident)]
    
    def get_arrivals_by_runway(self, runway_ident: str) -> List['Procedure']:
        """Get all arrival procedures for a specific runway."""
        return [p for p in self.procedures 
                if p.is_arrival() and p.matches_runway(runway_ident)]
    
    def get_approaches(self) -> List['Procedure']:
        """Get all approach procedures."""
        return [p for p in self.procedures if p.is_approach()]
    
    def get_departures(self) -> List['Procedure']:
        """Get all departure procedures."""
        return [p for p in self.procedures if p.is_departure()]
    
    def get_arrivals(self) -> List['Procedure']:
        """Get all arrival procedures."""
        return [p for p in self.procedures if p.is_arrival()]
    
    def get_procedures_by_source(self, source: str) -> List['Procedure']:
        """Get all procedures from a specific source."""
        return [p for p in self.procedures if p.source == source]
    
    def get_precision_category(self, approach_type: str) -> str:
        """
        Get precision category for an approach type.
        
        Args:
            approach_type: The approach type (e.g., 'ILS', 'RNAV', 'VOR')
            
        Returns:
            Precision category: 'precision', 'rnp', or 'non-precision'
        """
        approach_type_upper = approach_type.upper()
        
        if approach_type_upper == 'ILS':
            return 'precision'
        elif approach_type_upper in ['RNP', 'RNAV']:
            return 'rnp'
        else:
            return 'non-precision'
    
    def get_procedure_lines(self, distance_nm: float = 10.0) -> Dict[str, Any]:
        """
        Get procedure lines for visualization.
        
        Args:
            distance_nm: Distance in nautical miles for the procedure lines (default: 10.0)
            
        Returns:
            Dictionary containing airport ident and list of procedure line data
        """
        procedure_lines = []
        
        for runway in self.runways:
            
            # Process each runway end
            for end in ['le', 'he']:
                other = 'le' if end == 'he' else 'he'
                
                # Get runway end coordinates
                end_lat = getattr(runway, f'{end}_latitude_deg')
                end_lon = getattr(runway, f'{end}_longitude_deg')
                other_heading = getattr(runway, f'{other}_heading_degT')
                current_ident = getattr(runway, f'{end}_ident')
                
                # Skip if missing required data
                if not all([end_lat, end_lon, other_heading, current_ident]):
                    continue
                
                # Get the most precise approach for this runway end
                most_precise_approach = self.get_most_precise_approach_for_runway_end(runway, current_ident)
                
                if not most_precise_approach or not most_precise_approach.approach_type:
                    continue
                
                approach_type = most_precise_approach.approach_type.upper()
                
                # Calculate end point using NavPoint
                runway_end = NavPoint(latitude=float(end_lat), longitude=float(end_lon))
                end_point = runway_end.point_from_bearing_distance(
                    float(other_heading), distance_nm, f"{self.ident}_{current_ident}_end"
                )
                
                # Create procedure line data
                line_data = {
                    "runway_end": current_ident,
                    "start_lat": float(end_lat),
                    "start_lon": float(end_lon),
                    "end_lat": end_point.latitude,
                    "end_lon": end_point.longitude,
                    "approach_type": approach_type,
                    "procedure_name": most_precise_approach.name,
                    "precision_category": self.get_precision_category(approach_type),
                    "distance_nm": distance_nm
                }
                
                procedure_lines.append(line_data)
        
        return {
            "airport_ident": self.ident,
            "procedure_lines": procedure_lines
        }
    
    def get_procedures_by_authority(self, authority: str) -> List['Procedure']:
        """Get all procedures from a specific authority."""
        return [p for p in self.procedures if p.authority == authority]
    
    def get_runway_procedures_summary(self) -> Dict[str, Dict[str, List[str]]]:
        """Get a summary of procedures by runway and type."""
        summary = {}
        
        for runway in self.runways:
            runway_ident = runway.le_ident  # Use le_ident as primary
            if runway_ident not in summary:
                summary[runway_ident] = {
                    'approaches': [],
                    'departures': [],
                    'arrivals': []
                }
            
            # Get procedures for this runway
            approaches = self.get_approaches_by_runway(runway_ident)
            departures = self.get_departures_by_runway(runway_ident)
            arrivals = self.get_arrivals_by_runway(runway_ident)
            
            summary[runway_ident]['approaches'] = [p.name for p in approaches]
            summary[runway_ident]['departures'] = [p.name for p in departures]
            summary[runway_ident]['arrivals'] = [p.name for p in arrivals]
        
        return summary
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        data = {
            'ident': self.ident,
            'type': self.type,
            'name': self.name,
            'latitude_deg': self.latitude_deg,
            'longitude_deg': self.longitude_deg,
            'elevation_ft': self.elevation_ft,
            'continent': self.continent,
            'iso_country': self.iso_country,
            'iso_region': self.iso_region,
            'municipality': self.municipality,
            'scheduled_service': self.scheduled_service,
            'gps_code': self.gps_code,
            'iata_code': self.iata_code,
            'local_code': self.local_code,
            'home_link': self.home_link,
            'wikipedia_link': self.wikipedia_link,
            'keywords': self.keywords,
            'sources': list(self.sources),
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }
        
        # Add relationships
        if self.runways:
            data['runways'] = [r.to_dict() for r in self.runways]
        if self.aip_entries:
            data['aip_entries'] = [e.to_dict() for e in self.aip_entries]
        if self.procedures:
            data['procedures'] = [p.to_dict() for p in self.procedures]
            
        return data
    
    @classmethod
    def from_dict(cls, data: dict) -> 'Airport':
        """Create instance from dictionary."""
        # Filter out unknown fields
        known_fields = {field for field in cls.__dataclass_fields__}
        filtered_data = {k: v for k, v in data.items() if k in known_fields}
        
        # Convert datetime fields
        for field_name in ['created_at', 'updated_at']:
            if field_name in filtered_data:
                filtered_data[field_name] = datetime.fromisoformat(filtered_data[field_name])
        
        # Convert sources set
        if 'sources' in filtered_data:
            filtered_data['sources'] = set(filtered_data['sources'])
        
        # Handle relationships
        runways = []
        if 'runways' in data:
            from .runway import Runway
            runways = [Runway.from_dict(r) for r in data['runways']]
        
        aip_entries = []
        if 'aip_entries' in data:
            from .aip_entry import AIPEntry
            aip_entries = [AIPEntry.from_dict(e) for e in data['aip_entries']]
        
        procedures = []
        if 'procedures' in data:
            from .procedure import Procedure
            procedures = [Procedure.from_dict(p) for p in data['procedures']]
        
        # Create airport instance
        airport = cls(**filtered_data)
        airport.runways = runways
        airport.aip_entries = aip_entries
        airport.procedures = procedures
        
        return airport
    
    def __repr__(self):
        return f"Airport(ident='{self.ident}', name='{self.name}', sources={list(self.sources)})"
        
    def __str__(self):
        """Return a human-readable string representation of the airport."""
        airport_info = f"{self.name} ({self.ident})"
        
        if self.municipality:
            airport_info += f"\nLocation: {self.municipality}"
        if self.iso_country:
            airport_info += f", {self.iso_country}"
            
        if self.latitude_deg and self.longitude_deg:
            airport_info += f"\nCoordinates: {self.latitude_deg:.4f}°N, {self.longitude_deg:.4f}°E"
        if self.elevation_ft:
            airport_info += f"\nElevation: {self.elevation_ft}ft"
        
        if self.sources:
            airport_info += f"\nSources: {', '.join(sorted(self.sources))}"
            
        if self.runways:
            airport_info += f"\n\nRunways ({len(self.runways)}):"
            for runway in self.runways:
                airport_info += f"\n{str(runway)}"
        
        if self.procedures:
            airport_info += f"\n\nProcedures ({len(self.procedures)}):"
            for procedure in self.procedures:
                airport_info += f"\n{str(procedure)}"
                
        return airport_info 