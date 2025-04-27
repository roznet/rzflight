from dataclasses import dataclass
from typing import Optional
from datetime import datetime

@dataclass
class Runway:
    """Data class for storing runway information."""
    
    airport_ident: str
    length_ft: Optional[float] = None
    width_ft: Optional[float] = None
    surface: Optional[str] = None
    lighted: Optional[str] = None
    closed: Optional[str] = None
    
    # Low end (LE) information
    le_ident: Optional[str] = None
    le_latitude_deg: Optional[float] = None
    le_longitude_deg: Optional[float] = None
    le_elevation_ft: Optional[float] = None
    le_heading_degT: Optional[float] = None
    le_displaced_threshold_ft: Optional[float] = None
    
    # High end (HE) information
    he_ident: Optional[str] = None
    he_latitude_deg: Optional[float] = None
    he_longitude_deg: Optional[float] = None
    he_elevation_ft: Optional[float] = None
    he_heading_degT: Optional[float] = None
    he_displaced_threshold_ft: Optional[float] = None
    
    created_at: datetime = datetime.now()
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            'airport_ident': self.airport_ident,
            'length_ft': self.length_ft,
            'width_ft': self.width_ft,
            'surface': self.surface,
            'lighted': self.lighted,
            'closed': self.closed,
            'le_ident': self.le_ident,
            'le_latitude_deg': self.le_latitude_deg,
            'le_longitude_deg': self.le_longitude_deg,
            'le_elevation_ft': self.le_elevation_ft,
            'le_heading_degT': self.le_heading_degT,
            'le_displaced_threshold_ft': self.le_displaced_threshold_ft,
            'he_ident': self.he_ident,
            'he_latitude_deg': self.he_latitude_deg,
            'he_longitude_deg': self.he_longitude_deg,
            'he_elevation_ft': self.he_elevation_ft,
            'he_heading_degT': self.he_heading_degT,
            'he_displaced_threshold_ft': self.he_displaced_threshold_ft,
            'created_at': self.created_at.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'Runway':
        """Create instance from dictionary."""
        if 'created_at' in data:
            data['created_at'] = datetime.fromisoformat(data['created_at'])
            
        # Convert numeric fields from strings if needed
        numeric_fields = [
            'length_ft', 'width_ft', 'le_elevation_ft', 'le_heading_degT',
            'le_displaced_threshold_ft', 'he_elevation_ft', 'he_heading_degT',
            'he_displaced_threshold_ft'
        ]
        
        for field in numeric_fields:
            if field in data and data[field] is not None:
                try:
                    data[field] = float(data[field])
                except (ValueError, TypeError):
                    data[field] = None
                    
        return cls(**data)
    
    def __repr__(self):
        return f"Runway(airport_ident='{self.airport_ident}', le_ident='{self.le_ident}', he_ident='{self.he_ident}')" 