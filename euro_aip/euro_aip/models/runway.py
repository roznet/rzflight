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
    lighted: Optional[bool] = None
    closed: Optional[bool] = None
    
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
        # Filter out unknown fields
        known_fields = {field for field in cls.__dataclass_fields__}
        filtered_data = {k: v for k, v in data.items() if k in known_fields}
        
        if 'created_at' in filtered_data:
            filtered_data['created_at'] = datetime.fromisoformat(filtered_data['created_at'])
            
        # Convert numeric fields from strings if needed
        for field, value in filtered_data.items():
            if value is not None and any(field.endswith(suffix) for suffix in ['_deg', '_degT', '_ft']):
                try:
                    filtered_data[field] = float(value)
                except (ValueError, TypeError):
                    filtered_data[field] = None
                    
        # Convert boolean fields
        for field in ['lighted', 'closed']:
            if field in filtered_data and filtered_data[field] is not None:
                filtered_data[field] = bool(filtered_data[field])
                    
        return cls(**filtered_data)
    
    def __repr__(self):
        return f"Runway(airport_ident='{self.airport_ident}', le_ident='{self.le_ident}', he_ident='{self.he_ident}')"
        
    def __str__(self):
        """Return a human-readable string representation of the runway."""
        status = []
        if self.closed:
            status.append("CLOSED")
        if self.lighted:
            status.append("LIGHTED")
            
        runway_info = f"Runway {self.le_ident}/{self.he_ident}"
        if status:
            runway_info += f" ({', '.join(status)})"
            
        if self.length_ft:
            runway_info += f"\nLength: {self.length_ft:.0f}ft"
        if self.width_ft:
            runway_info += f" Width: {self.width_ft:.0f}ft"
        if self.surface:
            runway_info += f"\nSurface: {self.surface}"
            
        return runway_info 