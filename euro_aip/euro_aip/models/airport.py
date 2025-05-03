from dataclasses import dataclass
from typing import Optional, List
from datetime import datetime

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
    created_at: datetime = datetime.now()
    
    # Optional relationships (not stored in the dataclass, but can be loaded)
    runways: List['Runway'] = None 
    aip_entries: List['AIPEntry'] = None
    
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
            'created_at': self.created_at.isoformat()
        }
        
        # Add relationships if they exist
        if self.runways:
            data['runways'] = [r.to_dict() for r in self.runways]
        if self.aip_entries:
            data['aip_entries'] = [e.to_dict() for e in self.aip_entries]
            
        return data
    
    @classmethod
    def from_dict(cls, data: dict) -> 'Airport':
        """Create instance from dictionary."""
        # Filter out unknown fields
        known_fields = {field for field in cls.__dataclass_fields__}
        filtered_data = {k: v for k, v in data.items() if k in known_fields}
        
        if 'created_at' in filtered_data:
            filtered_data['created_at'] = datetime.fromisoformat(filtered_data['created_at'])
        return cls(**filtered_data)
    
    def __repr__(self):
        return f"Airport(ident='{self.ident}', name='{self.name}')"
        
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
            
        if self.runways:
            airport_info += f"\n\nRunways:"
            for runway in self.runways:
                airport_info += f"\n{str(runway)}"
                
        return airport_info 