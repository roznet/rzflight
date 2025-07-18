from dataclasses import dataclass, field
from typing import Optional, Dict, Any
from datetime import datetime
from euro_aip.models.runway import Runway

@dataclass
class Procedure:
    """Data class for storing procedure information with runway linking."""
    
    name: str  # e.g., "RWY13 ILS LOC"
    procedure_type: str  # 'approach', 'departure', 'arrival'
    approach_type: Optional[str] = None  # 'ILS', 'VOR', 'NDB', etc.
    runway_number: Optional[str] = None  # e.g., "13", "31"
    runway_letter: Optional[str] = None  # e.g., "L", "R", "C"
    runway_ident: Optional[str] = None  # Full runway identifier e.g., "13L"
    source: Optional[str] = None  # Which source provided this data
    authority: Optional[str] = None  # Authority code (LFC, EGC, etc.)
    raw_name: Optional[str] = None  # Original procedure name
    data: Optional[Dict[str, Any]] = None  # Additional raw data
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    
    # Class-level precision hierarchy
    _APPROACH_PRECISION_HIERARCHY = {
        'ILS': 1,      # Most precise - Instrument Landing System
        'RNP': 2,      # Required Navigation Performance
        'RNAV': 3,     # Area Navigation
        'VOR': 4,      # VHF Omnidirectional Range
        'NDB': 5,      # Non-Directional Beacon
        'LOC': 6,      # Localizer
        'LDA': 7,      # Localizer Directional Aid
        'SDF': 8,      # Simplified Directional Facility
    }
    
    def get_full_runway_ident(self) -> Optional[str]:
        """Get the full runway identifier (e.g., '13L')."""
        if self.runway_number:
            if self.runway_letter:
                return f"{self.runway_number}{self.runway_letter}"
            return self.runway_number
        return self.runway_ident
    
    def matches_runway(self, runway: Runway) -> bool:
        """Check if this procedure matches a runway."""
        return self.runway_ident == runway.le_ident or self.runway_ident == runway.he_ident
    
    def is_approach(self) -> bool:
        """Check if this is an approach procedure."""
        return self.procedure_type.lower() == 'approach'
    
    def is_departure(self) -> bool:
        """Check if this is a departure procedure."""
        return self.procedure_type.lower() == 'departure'
    
    def is_arrival(self) -> bool:
        """Check if this is an arrival procedure."""
        return self.procedure_type.lower() == 'arrival'
    
    def get_approach_precision(self) -> int:
        """
        Get the precision ranking for this procedure's approach type.
        Lower numbers indicate higher precision.
        
        Returns:
            Precision ranking (lower = more precise)
        """
        if not self.approach_type:
            return 999  # Lowest precision for procedures without approach type
        
        # Normalize approach type (handle case variations)
        normalized_type = self.approach_type.upper()
        
        # Return precision ranking, default to lowest precision if unknown
        return self._APPROACH_PRECISION_HIERARCHY.get(normalized_type, 999)
    
    def compare_precision(self, other: 'Procedure') -> int:
        """
        Compare the precision of this procedure with another.
        
        Args:
            other: Another Procedure to compare with
            
        Returns:
            -1 if this procedure is more precise than other
             0 if both procedures have the same precision
             1 if other procedure is more precise than this
        """
        if not isinstance(other, Procedure):
            raise TypeError("Can only compare with other Procedure objects")
        
        this_precision = self.get_approach_precision()
        other_precision = other.get_approach_precision()
        
        if this_precision < other_precision:
            return -1  # This is more precise
        elif this_precision > other_precision:
            return 1   # Other is more precise
        else:
            return 0   # Same precision
    
    def is_more_precise_than(self, other: 'Procedure') -> bool:
        """
        Check if this procedure is more precise than another.
        
        Args:
            other: Another Procedure to compare with
            
        Returns:
            True if this procedure is more precise than other
        """
        return self.compare_precision(other) < 0
    
    def is_less_precise_than(self, other: 'Procedure') -> bool:
        """
        Check if this procedure is less precise than another.
        
        Args:
            other: Another Procedure to compare with
            
        Returns:
            True if this procedure is less precise than other
        """
        return self.compare_precision(other) > 0
    
    def has_same_precision_as(self, other: 'Procedure') -> bool:
        """
        Check if this procedure has the same precision as another.
        
        Args:
            other: Another Procedure to compare with
            
        Returns:
            True if both procedures have the same precision
        """
        return self.compare_precision(other) == 0
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            'name': self.name,
            'procedure_type': self.procedure_type,
            'approach_type': self.approach_type,
            'runway_number': self.runway_number,
            'runway_letter': self.runway_letter,
            'runway_ident': self.runway_ident,
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
        
        if self.source:
            result += f" [Source: {self.source}]"
        
        return result 