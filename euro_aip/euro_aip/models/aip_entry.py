from dataclasses import dataclass
from typing import Optional
from datetime import datetime

@dataclass
class AIPEntry:
    """Data class for storing parsed AIP information with standardized field mapping."""
    
    ident: str  # ICAO code
    section: str  # admin, operational, handling, passenger
    field: str  # Original field name
    value: str  # Field value
    std_field: Optional[str] = None  # Standardized field name
    std_field_id: Optional[int] = None  # Standard field ID
    mapping_score: Optional[float] = None  # Similarity score from field mapper
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
            'std_field': self.std_field,
            'std_field_id': self.std_field_id,
            'mapping_score': self.mapping_score,
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
    
    def is_standardized(self) -> bool:
        """Check if this entry has been standardized."""
        return self.std_field is not None and self.std_field_id is not None
    
    def get_effective_field_name(self) -> str:
        """Get the standardized field name if available, otherwise original field name."""
        return self.std_field if self.std_field else self.field
    
    def __repr__(self):
        if self.std_field:
            return f"AIPEntry(ident='{self.ident}', field='{self.field}' -> '{self.std_field}', score={self.mapping_score:.2f})"
        else:
            return f"AIPEntry(ident='{self.ident}', section='{self.section}', field='{self.field}')" 
    