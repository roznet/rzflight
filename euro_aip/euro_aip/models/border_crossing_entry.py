"""
Border crossing entry model.

This module defines the BorderCrossingEntry class for representing
border crossing airport entries from various sources.
"""

import json
from datetime import datetime
from typing import Dict, Optional, Any

class BorderCrossingEntry:
    """Model for border crossing airport entries."""
    
    def __init__(self, airport_name: str, country_iso: str, icao_code: Optional[str] = None,
                 is_airport: Optional[bool] = None,
                 source: Optional[str] = None, extraction_method: Optional[str] = None,
                 metadata: Optional[Dict[str, Any]] = None, matched_airport_icao: Optional[str] = None,
                 match_score: Optional[float] = None, created_at: Optional[datetime] = None,
                 updated_at: Optional[datetime] = None):
        """
        Initialize a border crossing entry.
        
        Args:
            airport_name: Name of the airport
            country_iso: ISO country code
            icao_code: ICAO code if available
            source: Source of the data (e.g., 'border_crossing_parser')
            extraction_method: Method used to extract the data
            metadata: Additional metadata from parsing
            matched_airport_icao: ICAO code of matched airport in our database
            match_score: Fuzzy match score if matched
            created_at: Creation timestamp
            updated_at: Last update timestamp
        """
        self.airport_name = airport_name
        self.country_iso = country_iso
        self.icao_code = icao_code
        self.is_airport = is_airport
        self.source = source
        self.extraction_method = extraction_method
        self.metadata = metadata or {}
        self.matched_airport_icao = matched_airport_icao
        self.match_score = match_score
        self.created_at = created_at or datetime.now()
        self.updated_at = updated_at or datetime.now()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for database storage."""
        return {
            'airport_name': self.airport_name,
            'country_iso': self.country_iso,
            'icao_code': self.icao_code,
            'is_airport': self.is_airport,
            'source': self.source,
            'extraction_method': self.extraction_method,
            'metadata_json': json.dumps(self.metadata) if self.metadata else None,
            'matched_airport_icao': self.matched_airport_icao,
            'match_score': self.match_score,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'BorderCrossingEntry':
        """Create from dictionary (from database)."""
        metadata = None
        if data.get('metadata_json'):
            try:
                metadata = json.loads(data['metadata_json'])
            except (json.JSONDecodeError, TypeError):
                metadata = {}
        
        created_at = None
        if data.get('created_at'):
            try:
                created_at = datetime.fromisoformat(data['created_at'])
            except ValueError:
                created_at = datetime.now()
        
        updated_at = None
        if data.get('updated_at'):
            try:
                updated_at = datetime.fromisoformat(data['updated_at'])
            except ValueError:
                updated_at = datetime.now()
        
        return cls(
            airport_name=data['airport_name'],
            country_iso=data['country_iso'],
            icao_code=data.get('icao_code'),
            is_airport=data.get('is_airport'),
            source=data.get('source'),
            extraction_method=data.get('extraction_method'),
            metadata=metadata,
            matched_airport_icao=data.get('matched_airport_icao'),
            match_score=data.get('match_score'),
            created_at=created_at,
            updated_at=updated_at
        )
    
    def __str__(self) -> str:
        """String representation."""
        return f"BorderCrossingEntry({self.airport_name}, {self.country_iso}, {self.icao_code})"
    
    def __repr__(self) -> str:
        """Detailed string representation."""
        return (f"BorderCrossingEntry(airport_name='{self.airport_name}', "
                f"country_iso='{self.country_iso}', icao_code='{self.icao_code}', "
                f"source='{self.source}', matched_airport_icao='{self.matched_airport_icao}', "
                f"match_score={self.match_score})")
    
    def __eq__(self, other: Any) -> bool:
        """Equality comparison."""
        if not isinstance(other, BorderCrossingEntry):
            return False
        
        return (self.airport_name == other.airport_name and
                self.country_iso == other.country_iso and
                self.icao_code == other.icao_code and
                self.source == other.source)
    
    def __hash__(self) -> int:
        """Hash for set operations."""
        return hash((self.airport_name, self.country_iso, self.icao_code, self.source))
    
    def merge_with(self, other: 'BorderCrossingEntry') -> 'BorderCrossingEntry':
        """
        Merge this entry with another, combining information intelligently.
        
        Args:
            other: Another BorderCrossingEntry to merge with
            
        Returns:
            New BorderCrossingEntry with combined information
        """
        if not isinstance(other, BorderCrossingEntry):
            raise ValueError("Can only merge with another BorderCrossingEntry")
        
        # Start with this entry's data
        merged_data = {
            'airport_name': self.airport_name,
            'country_iso': self.country_iso,
            'icao_code': self.icao_code,
            'is_airport': self.is_airport,
            'source': self.source,
            'extraction_method': self.extraction_method,
            'metadata': self.metadata.copy() if self.metadata else {},
            'matched_airport_icao': self.matched_airport_icao,
            'match_score': self.match_score,
            'created_at': min(self.created_at, other.created_at),
            'updated_at': max(self.updated_at, other.updated_at)
        }
        
        # Track if meaningful data was merged (not just metadata)
        meaningful_changes = False
        
        # Merge ICAO codes - prefer non-None values
        if not merged_data['icao_code'] and other.icao_code:
            merged_data['icao_code'] = other.icao_code
            meaningful_changes = True
        
        # Merge is_airport - prefer True over None/False
        if merged_data['is_airport'] is None and other.is_airport is not None:
            merged_data['is_airport'] = other.is_airport
            meaningful_changes = True
        elif merged_data['is_airport'] is False and other.is_airport is True:
            merged_data['is_airport'] = True
            meaningful_changes = True
        
        # Merge extraction methods - prefer more specific ones
        if not merged_data['extraction_method'] and other.extraction_method:
            merged_data['extraction_method'] = other.extraction_method
            meaningful_changes = True
        elif merged_data['extraction_method'] and other.extraction_method:
            # Prefer more specific extraction methods
            if 'csv' in other.extraction_method.lower() and 'html' in merged_data['extraction_method'].lower():
                merged_data['extraction_method'] = other.extraction_method
                meaningful_changes = True
        
        # Merge matched airport ICAO - prefer the one with higher match score
        if not merged_data['matched_airport_icao'] and other.matched_airport_icao:
            merged_data['matched_airport_icao'] = other.matched_airport_icao
            merged_data['match_score'] = other.match_score
            meaningful_changes = True
        elif merged_data['matched_airport_icao'] and other.matched_airport_icao:
            # Keep the one with higher match score
            if (other.match_score or 0) > (merged_data['match_score'] or 0):
                merged_data['matched_airport_icao'] = other.matched_airport_icao
                merged_data['match_score'] = other.match_score
                meaningful_changes = True
        
        # Merge sources - only add new source if meaningful changes occurred
        if meaningful_changes and other.source:
            sources = set()
            if self.source:
                sources.add(self.source)
            sources.add(other.source)
            merged_data['source'] = ';'.join(sorted(sources))
        
        # Merge metadata - combine all unique keys (this doesn't count as meaningful change)
        if other.metadata:
            for key, value in other.metadata.items():
                if key not in merged_data['metadata'] or not merged_data['metadata'][key]:
                    merged_data['metadata'][key] = value
                elif isinstance(merged_data['metadata'][key], str) and isinstance(value, str):
                    # For string values, prefer non-empty ones
                    if not merged_data['metadata'][key].strip() and value.strip():
                        merged_data['metadata'][key] = value
        
        return BorderCrossingEntry(**merged_data)
    
    def is_more_complete_than(self, other: 'BorderCrossingEntry') -> bool:
        """
        Check if this entry is more complete than another.
        
        Args:
            other: Another BorderCrossingEntry to compare with
            
        Returns:
            True if this entry is more complete
        """
        if not isinstance(other, BorderCrossingEntry):
            return False
        
        # Native ICAO (has icao_code but no matched_airport_icao) is always preferred over matched
        self_native = self.icao_code and not self.matched_airport_icao
        other_native = other.icao_code and not other.matched_airport_icao
        
        if self_native and not other_native:
            return True
        if other_native and not self_native:
            return False
        
        # If both are the same type (both native or both matched), use scoring
        self_score = 0
        other_score = 0
        
        # ICAO code presence (should always be present here)
        if self.icao_code:
            self_score += 10
        if other.icao_code:
            other_score += 10
        
        # Match score
        if self.match_score:
            self_score += int(self.match_score * 5)
        if other.match_score:
            other_score += int(other.match_score * 5)
        
        # Metadata completeness
        if self.metadata:
            self_score += len(self.metadata)
        if other.metadata:
            other_score += len(other.metadata)
        
        # Additional fields
        if self.is_airport is not None:
            self_score += 1
        if other.is_airport is not None:
            other_score += 1
        if self.extraction_method:
            self_score += 1
        if other.extraction_method:
            other_score += 1
        
        return self_score > other_score 