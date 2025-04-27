from dataclasses import dataclass
from typing import Optional
from datetime import datetime

@dataclass
class AIPEntry:
    """Data class for storing parsed AIP information."""
    
    ident: str  # ICAO code
    section: str  # admin, operational, handling, passenger
    field: str  # Field name in original language
    value: str  # Value in original language
    alt_field: Optional[str] = None  # Field name in alternative language
    alt_value: Optional[str] = None  # Value in alternative language
    created_at: datetime = datetime.now()
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            'ident': self.ident,
            'section': self.section,
            'field': self.field,
            'value': self.value,
            'alt_field': self.alt_field,
            'alt_value': self.alt_value,
            'created_at': self.created_at.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'AIPEntry':
        """Create instance from dictionary."""
        if 'created_at' in data:
            data['created_at'] = datetime.fromisoformat(data['created_at'])
        return cls(**data)
    
    def __repr__(self):
        return f"AIPEntry(ident='{self.ident}', section='{self.section}', field='{self.field}')" 