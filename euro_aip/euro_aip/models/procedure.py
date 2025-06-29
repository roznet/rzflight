from dataclasses import dataclass, field
from typing import Optional, Dict, Any
from datetime import datetime

@dataclass
class Procedure:
    """Data class for storing procedure information with runway linking."""
    
    name: str  # e.g., "RWY13 ILS LOC"
    procedure_type: str  # 'approach', 'departure', 'arrival'
    approach_type: Optional[str] = None  # 'ILS', 'VOR', 'NDB', etc.
    runway_ident: Optional[str] = None  # e.g., "13", "31"
    runway_letter: Optional[str] = None  # e.g., "L", "R", "C"
    runway: Optional[str] = None  # Full runway identifier e.g., "13L"
    category: Optional[str] = None  # 'CAT I', 'CAT II', etc.
    minima: Optional[str] = None  # Minimums information
    notes: Optional[str] = None
    source: Optional[str] = None  # Which source provided this data
    authority: Optional[str] = None  # Authority code (LFC, EGC, etc.)
    raw_name: Optional[str] = None  # Original procedure name
    data: Optional[Dict[str, Any]] = None  # Additional raw data
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    
    def get_full_runway_ident(self) -> Optional[str]:
        """Get the full runway identifier (e.g., '13L')."""
        if self.runway_ident:
            if self.runway_letter:
                return f"{self.runway_ident}{self.runway_letter}"
            return self.runway_ident
        return self.runway
    
    def matches_runway(self, runway_ident: str) -> bool:
        """Check if this procedure matches a runway."""
        return self.get_full_runway_ident() == runway_ident
    
    def is_approach(self) -> bool:
        """Check if this is an approach procedure."""
        return self.procedure_type.lower() == 'approach'
    
    def is_departure(self) -> bool:
        """Check if this is a departure procedure."""
        return self.procedure_type.lower() == 'departure'
    
    def is_arrival(self) -> bool:
        """Check if this is an arrival procedure."""
        return self.procedure_type.lower() == 'arrival'
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            'name': self.name,
            'procedure_type': self.procedure_type,
            'approach_type': self.approach_type,
            'runway_ident': self.runway_ident,
            'runway_letter': self.runway_letter,
            'runway': self.runway,
            'category': self.category,
            'minima': self.minima,
            'notes': self.notes,
            'source': self.source,
            'authority': self.authority,
            'raw_name': self.raw_name,
            'data': self.data,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'Procedure':
        """Create instance from dictionary."""
        # Convert datetime fields
        for field_name in ['created_at', 'updated_at']:
            if field_name in data:
                data[field_name] = datetime.fromisoformat(data[field_name])
        
        return cls(**data)
    
    def __repr__(self):
        runway_info = self.get_full_runway_ident() or "unknown runway"
        return f"Procedure(name='{self.name}', type='{self.procedure_type}', runway='{runway_info}')"
    
    def __str__(self):
        """Return a human-readable string representation."""
        result = f"{self.name} ({self.procedure_type.upper()})"
        
        if self.approach_type:
            result += f" - {self.approach_type}"
        
        runway_info = self.get_full_runway_ident()
        if runway_info:
            result += f" - RWY {runway_info}"
        
        if self.category:
            result += f" - {self.category}"
        
        if self.source:
            result += f" [Source: {self.source}]"
        
        return result 