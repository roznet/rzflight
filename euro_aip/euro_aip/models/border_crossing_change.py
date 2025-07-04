"""
Border crossing change model.

This module defines the BorderCrossingChange class for representing
changes to border crossing entries (ADDED/REMOVED).
"""

from datetime import datetime
from typing import Dict, Any, Optional

class BorderCrossingChange:
    """Model for border crossing changes."""
    
    def __init__(self, airport_name: str, country_iso: str, action: str, 
                 source: str, changed_at: Optional[datetime] = None):
        """
        Initialize a border crossing change.
        
        Args:
            airport_name: Name of the airport
            country_iso: ISO country code
            action: Action type ('ADDED' or 'REMOVED')
            source: Source of the data
            changed_at: Timestamp of the change
        """
        self.airport_name = airport_name
        self.country_iso = country_iso
        self.action = action
        self.source = source
        self.changed_at = changed_at or datetime.now()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for database storage."""
        return {
            'airport_name': self.airport_name,
            'country_iso': self.country_iso,
            'action': self.action,
            'source': self.source,
            'changed_at': self.changed_at.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'BorderCrossingChange':
        """Create from dictionary (from database)."""
        changed_at = None
        if data.get('changed_at'):
            try:
                changed_at = datetime.fromisoformat(data['changed_at'])
            except ValueError:
                changed_at = datetime.now()
        
        return cls(
            airport_name=data['airport_name'],
            country_iso=data['country_iso'],
            action=data['action'],
            source=data['source'],
            changed_at=changed_at
        )
    
    def __str__(self) -> str:
        """String representation."""
        return f"BorderCrossingChange({self.airport_name}, {self.action}, {self.country_iso})"
    
    def __repr__(self) -> str:
        """Detailed string representation."""
        return (f"BorderCrossingChange(airport_name='{self.airport_name}', "
                f"country_iso='{self.country_iso}', action='{self.action}', "
                f"source='{self.source}', changed_at={self.changed_at})")
    
    def __eq__(self, other: Any) -> bool:
        """Equality comparison."""
        if not isinstance(other, BorderCrossingChange):
            return False
        
        return (self.airport_name == other.airport_name and
                self.country_iso == other.country_iso and
                self.action == other.action and
                self.source == other.source)
    
    def __hash__(self) -> int:
        """Hash for set operations."""
        return hash((self.airport_name, self.country_iso, self.action, self.source)) 