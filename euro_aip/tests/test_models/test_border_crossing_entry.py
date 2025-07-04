"""
Tests for the BorderCrossingEntry model.
"""

import pytest
from datetime import datetime
from euro_aip.models.border_crossing_entry import BorderCrossingEntry


class TestBorderCrossingEntry:
    """Test cases for the BorderCrossingEntry class."""
    
    def test_init_basic(self):
        """Test basic initialization."""
        entry = BorderCrossingEntry(
            airport_name="London Heathrow",
            country_iso="GB",
            icao_code="EGLL"
        )
        
        assert entry.airport_name == "London Heathrow"
        assert entry.country_iso == "GB"
        assert entry.icao_code == "EGLL"
        assert entry.matched_airport_icao is None
        assert entry.match_score is None
        assert isinstance(entry.created_at, datetime)
        assert isinstance(entry.updated_at, datetime)
    
    def test_init_with_all_fields(self):
        """Test initialization with all fields."""
        metadata = {"number": "1", "row_data": {"first_column": "(1)"}}
        created_at = datetime(2023, 1, 1, 12, 0, 0)
        updated_at = datetime(2023, 1, 2, 12, 0, 0)
        
        entry = BorderCrossingEntry(
            airport_name="Paris Charles de Gaulle",
            country_iso="FR",
            icao_code="LFPG",
            source="border_crossing_parser",
            extraction_method="html_table_parsing",
            metadata=metadata,
            matched_airport_icao="LFPG",
            match_score=0.95,
            created_at=created_at,
            updated_at=updated_at
        )
        
        assert entry.airport_name == "Paris Charles de Gaulle"
        assert entry.country_iso == "FR"
        assert entry.icao_code == "LFPG"
        assert entry.source == "border_crossing_parser"
        assert entry.extraction_method == "html_table_parsing"
        assert entry.metadata == metadata
        assert entry.matched_airport_icao == "LFPG"
        assert entry.match_score == 0.95
        assert entry.created_at == created_at
        assert entry.updated_at == updated_at
    
    def test_to_dict(self):
        """Test conversion to dictionary."""
        metadata = {"test": "value"}
        entry = BorderCrossingEntry(
            airport_name="Amsterdam Schiphol",
            country_iso="NL",
            icao_code="EHAM",
            source="border_crossing_parser",
            extraction_method="html_table_parsing",
            metadata=metadata,
            matched_airport_icao="EHAM",
            match_score=0.8
        )
        
        data = entry.to_dict()
        
        assert data['airport_name'] == "Amsterdam Schiphol"
        assert data['country_iso'] == "NL"
        assert data['icao_code'] == "EHAM"
        assert data['source'] == "border_crossing_parser"
        assert data['extraction_method'] == "html_table_parsing"
        assert '"test": "value"' in data['metadata_json']
        assert data['matched_airport_icao'] == "EHAM"
        assert data['match_score'] == 0.8
        assert 'created_at' in data
        assert 'updated_at' in data
    
    def test_from_dict(self):
        """Test creation from dictionary."""
        data = {
            'airport_name': 'Frankfurt Airport',
            'country_iso': 'DE',
            'icao_code': 'EDDF',
            'source': 'border_crossing_parser',
            'extraction_method': 'html_table_parsing',
            'metadata_json': '{"number": "2"}',
            'matched_airport_icao': 'EDDF',
            'match_score': 0.9,
            'created_at': '2023-01-01T12:00:00',
            'updated_at': '2023-01-02T12:00:00'
        }
        
        entry = BorderCrossingEntry.from_dict(data)
        
        assert entry.airport_name == "Frankfurt Airport"
        assert entry.country_iso == "DE"
        assert entry.icao_code == "EDDF"
        assert entry.source == "border_crossing_parser"
        assert entry.extraction_method == "html_table_parsing"
        assert entry.metadata == {"number": "2"}
        assert entry.matched_airport_icao == "EDDF"
        assert entry.match_score == 0.9
        assert entry.created_at == datetime(2023, 1, 1, 12, 0, 0)
        assert entry.updated_at == datetime(2023, 1, 2, 12, 0, 0)
    
    def test_from_dict_invalid_json(self):
        """Test from_dict with invalid JSON metadata."""
        data = {
            'airport_name': 'Test Airport',
            'country_iso': 'US',
            'metadata_json': 'invalid json',
            'created_at': '2023-01-01T12:00:00',
            'updated_at': '2023-01-02T12:00:00'
        }
        
        entry = BorderCrossingEntry.from_dict(data)
        
        assert entry.airport_name == "Test Airport"
        assert entry.country_iso == "US"
        assert entry.metadata == {}  # Should default to empty dict
    
    def test_from_dict_invalid_datetime(self):
        """Test from_dict with invalid datetime strings."""
        data = {
            'airport_name': 'Test Airport',
            'country_iso': 'US',
            'created_at': 'invalid datetime',
            'updated_at': 'also invalid'
        }
        
        entry = BorderCrossingEntry.from_dict(data)
        
        assert entry.airport_name == "Test Airport"
        assert entry.country_iso == "US"
        # Should use current datetime for invalid dates
        assert isinstance(entry.created_at, datetime)
        assert isinstance(entry.updated_at, datetime)
    
    def test_str_repr(self):
        """Test string representations."""
        entry = BorderCrossingEntry(
            airport_name="London Heathrow",
            country_iso="GB",
            icao_code="EGLL"
        )
        
        str_repr = str(entry)
        assert "BorderCrossingEntry" in str_repr
        assert "London Heathrow" in str_repr
        assert "GB" in str_repr
        assert "EGLL" in str_repr
        
        repr_str = repr(entry)
        assert "BorderCrossingEntry" in repr_str
        assert "airport_name='London Heathrow'" in repr_str
        assert "country_iso='GB'" in repr_str
        assert "icao_code='EGLL'" in repr_str
    
    def test_equality(self):
        """Test equality comparison."""
        entry1 = BorderCrossingEntry(
            airport_name="London Heathrow",
            country_iso="GB",
            icao_code="EGLL",
            source="border_crossing_parser"
        )
        
        entry2 = BorderCrossingEntry(
            airport_name="London Heathrow",
            country_iso="GB",
            icao_code="EGLL",
            source="border_crossing_parser"
        )
        
        entry3 = BorderCrossingEntry(
            airport_name="Paris CDG",
            country_iso="FR",
            icao_code="LFPG",
            source="border_crossing_parser"
        )
        
        assert entry1 == entry2
        assert entry1 != entry3
        assert entry1 != "not an entry"
    
    def test_hash(self):
        """Test hash for set operations."""
        entry1 = BorderCrossingEntry(
            airport_name="London Heathrow",
            country_iso="GB",
            icao_code="EGLL",
            source="border_crossing_parser"
        )
        
        entry2 = BorderCrossingEntry(
            airport_name="London Heathrow",
            country_iso="GB",
            icao_code="EGLL",
            source="border_crossing_parser"
        )
        
        entry_set = {entry1, entry2}
        assert len(entry_set) == 1  # Should deduplicate based on hash 