"""
Tests for the BorderCrossingChange model.
"""

import pytest
from datetime import datetime
from euro_aip.models.border_crossing_change import BorderCrossingChange


class TestBorderCrossingChange:
    """Test cases for the BorderCrossingChange class."""
    
    def test_init_basic(self):
        """Test basic initialization."""
        change = BorderCrossingChange(
            airport_name="London Heathrow",
            country_iso="GB",
            action="ADDED",
            source="border_crossing_parser"
        )
        
        assert change.airport_name == "London Heathrow"
        assert change.country_iso == "GB"
        assert change.action == "ADDED"
        assert change.source == "border_crossing_parser"
        assert isinstance(change.changed_at, datetime)
    
    def test_init_with_datetime(self):
        """Test initialization with specific datetime."""
        changed_at = datetime(2023, 1, 1, 12, 0, 0)
        change = BorderCrossingChange(
            airport_name="Paris Charles de Gaulle",
            country_iso="FR",
            action="REMOVED",
            source="border_crossing_parser",
            changed_at=changed_at
        )
        
        assert change.airport_name == "Paris Charles de Gaulle"
        assert change.country_iso == "FR"
        assert change.action == "REMOVED"
        assert change.source == "border_crossing_parser"
        assert change.changed_at == changed_at
    
    def test_to_dict(self):
        """Test conversion to dictionary."""
        changed_at = datetime(2023, 1, 1, 12, 0, 0)
        change = BorderCrossingChange(
            airport_name="Amsterdam Schiphol",
            country_iso="NL",
            action="ADDED",
            source="border_crossing_parser",
            changed_at=changed_at
        )
        
        data = change.to_dict()
        
        assert data['airport_name'] == "Amsterdam Schiphol"
        assert data['country_iso'] == "NL"
        assert data['action'] == "ADDED"
        assert data['source'] == "border_crossing_parser"
        assert data['changed_at'] == "2023-01-01T12:00:00"
    
    def test_from_dict(self):
        """Test creation from dictionary."""
        data = {
            'airport_name': 'Frankfurt Airport',
            'country_iso': 'DE',
            'action': 'REMOVED',
            'source': 'border_crossing_parser',
            'changed_at': '2023-01-01T12:00:00'
        }
        
        change = BorderCrossingChange.from_dict(data)
        
        assert change.airport_name == "Frankfurt Airport"
        assert change.country_iso == "DE"
        assert change.action == "REMOVED"
        assert change.source == "border_crossing_parser"
        assert change.changed_at == datetime(2023, 1, 1, 12, 0, 0)
    
    def test_from_dict_invalid_datetime(self):
        """Test from_dict with invalid datetime string."""
        data = {
            'airport_name': 'Test Airport',
            'country_iso': 'US',
            'action': 'ADDED',
            'source': 'border_crossing_parser',
            'changed_at': 'invalid datetime'
        }
        
        change = BorderCrossingChange.from_dict(data)
        
        assert change.airport_name == "Test Airport"
        assert change.country_iso == "US"
        assert change.action == "ADDED"
        assert change.source == "border_crossing_parser"
        # Should use current datetime for invalid date
        assert isinstance(change.changed_at, datetime)
    
    def test_str_repr(self):
        """Test string representations."""
        change = BorderCrossingChange(
            airport_name="London Heathrow",
            country_iso="GB",
            action="ADDED",
            source="border_crossing_parser"
        )
        
        str_repr = str(change)
        assert "BorderCrossingChange" in str_repr
        assert "London Heathrow" in str_repr
        assert "ADDED" in str_repr
        assert "GB" in str_repr
        
        repr_str = repr(change)
        assert "BorderCrossingChange" in repr_str
        assert "airport_name='London Heathrow'" in repr_str
        assert "country_iso='GB'" in repr_str
        assert "action='ADDED'" in repr_str
        assert "source='border_crossing_parser'" in repr_str
    
    def test_equality(self):
        """Test equality comparison."""
        change1 = BorderCrossingChange(
            airport_name="London Heathrow",
            country_iso="GB",
            action="ADDED",
            source="border_crossing_parser"
        )
        
        change2 = BorderCrossingChange(
            airport_name="London Heathrow",
            country_iso="GB",
            action="ADDED",
            source="border_crossing_parser"
        )
        
        change3 = BorderCrossingChange(
            airport_name="Paris CDG",
            country_iso="FR",
            action="REMOVED",
            source="border_crossing_parser"
        )
        
        assert change1 == change2
        assert change1 != change3
        assert change1 != "not a change"
    
    def test_hash(self):
        """Test hash for set operations."""
        change1 = BorderCrossingChange(
            airport_name="London Heathrow",
            country_iso="GB",
            action="ADDED",
            source="border_crossing_parser"
        )
        
        change2 = BorderCrossingChange(
            airport_name="London Heathrow",
            country_iso="GB",
            action="ADDED",
            source="border_crossing_parser"
        )
        
        change_set = {change1, change2}
        assert len(change_set) == 1  # Should deduplicate based on hash
    
    def test_action_values(self):
        """Test different action values."""
        added_change = BorderCrossingChange(
            airport_name="Test Airport",
            country_iso="US",
            action="ADDED",
            source="border_crossing_parser"
        )
        
        removed_change = BorderCrossingChange(
            airport_name="Test Airport",
            country_iso="US",
            action="REMOVED",
            source="border_crossing_parser"
        )
        
        assert added_change.action == "ADDED"
        assert removed_change.action == "REMOVED" 