"""
Tests for EuroAipModel border crossing integration.
"""

import pytest
import tempfile
import os
from datetime import datetime
from euro_aip.models.euro_aip_model import EuroAipModel
from euro_aip.models.airport import Airport
from euro_aip.models.border_crossing_entry import BorderCrossingEntry


class TestEuroAipModelBorderCrossing:
    """Test cases for EuroAipModel border crossing integration."""
    
    def test_add_border_crossing_entry(self):
        """Test adding a single border crossing entry."""
        model = EuroAipModel()
        
        entry = BorderCrossingEntry(
            airport_name="London Heathrow",
            country_iso="GB",
            icao_code="EGLL",
            source="border_crossing_parser",
            matched_airport_icao="EGLL",
            match_score=0.95
        )
        
        model.add_border_crossing_entry(entry)
        
        # Check that entry was added
        assert "GB" in model.border_crossing_entries
        assert "London Heathrow" in model.border_crossing_entries["GB"]
        assert model.border_crossing_entries["GB"]["London Heathrow"] == entry
        
        # Check sources tracking
        assert "border_crossing_parser" in model.sources_used
    
    def test_add_border_crossing_entries(self):
        """Test adding multiple border crossing entries."""
        model = EuroAipModel()
        
        entries = [
            BorderCrossingEntry(
                airport_name="London Heathrow",
                country_iso="GB",
                icao_code="EGLL",
                source="border_crossing_parser"
            ),
            BorderCrossingEntry(
                airport_name="Paris CDG",
                country_iso="FR",
                icao_code="LFPG",
                source="border_crossing_parser"
            ),
            BorderCrossingEntry(
                airport_name="Gatwick",
                country_iso="GB",
                icao_code="EGKK",
                source="border_crossing_parser"
            )
        ]
        
        model.add_border_crossing_entries(entries)
        
        # Check that all entries were added
        assert len(model.get_all_border_crossing_entries()) == 3
        assert len(model.border_crossing_entries["GB"]) == 2
        assert len(model.border_crossing_entries["FR"]) == 1
        
        # Check specific entries
        assert "London Heathrow" in model.border_crossing_entries["GB"]
        assert "Gatwick" in model.border_crossing_entries["GB"]
        assert "Paris CDG" in model.border_crossing_entries["FR"]
    
    def test_get_border_crossing_entries_by_country(self):
        """Test getting border crossing entries by country."""
        model = EuroAipModel()
        
        entries = [
            BorderCrossingEntry(
                airport_name="London Heathrow",
                country_iso="GB",
                source="border_crossing_parser"
            ),
            BorderCrossingEntry(
                airport_name="Paris CDG",
                country_iso="FR",
                source="border_crossing_parser"
            ),
            BorderCrossingEntry(
                airport_name="Gatwick",
                country_iso="GB",
                source="border_crossing_parser"
            )
        ]
        
        model.add_border_crossing_entries(entries)
        
        # Get UK entries
        uk_entries = model.get_border_crossing_entries_by_country("GB")
        assert len(uk_entries) == 2
        assert all(entry.country_iso == "GB" for entry in uk_entries)
        
        # Get French entries
        fr_entries = model.get_border_crossing_entries_by_country("FR")
        assert len(fr_entries) == 1
        assert fr_entries[0].airport_name == "Paris CDG"
        
        # Get non-existent country
        no_entries = model.get_border_crossing_entries_by_country("XX")
        assert len(no_entries) == 0
    
    def test_get_border_crossing_entry(self):
        """Test getting a specific border crossing entry."""
        model = EuroAipModel()
        
        entry = BorderCrossingEntry(
            airport_name="London Heathrow",
            country_iso="GB",
            source="border_crossing_parser"
        )
        
        model.add_border_crossing_entry(entry)
        
        # Get existing entry
        found_entry = model.get_border_crossing_entry("GB", "London Heathrow")
        assert found_entry == entry
        
        # Get non-existent entry
        not_found = model.get_border_crossing_entry("GB", "Non-existent")
        assert not_found is None
        
        # Get from non-existent country
        not_found = model.get_border_crossing_entry("XX", "London Heathrow")
        assert not_found is None
    
    def test_get_border_crossing_statistics(self):
        """Test border crossing statistics."""
        model = EuroAipModel()
        
        entries = [
            BorderCrossingEntry(
                airport_name="London Heathrow",
                country_iso="GB",
                matched_airport_icao="EGLL",
                match_score=0.95,
                source="border_crossing_parser"
            ),
            BorderCrossingEntry(
                airport_name="Paris CDG",
                country_iso="FR",
                matched_airport_icao="LFPG",
                match_score=0.9,
                source="border_crossing_parser"
            ),
            BorderCrossingEntry(
                airport_name="Unmatched Airport",
                country_iso="DE",
                source="border_crossing_parser"
            )
        ]
        
        model.add_border_crossing_entries(entries)
        
        stats = model.get_border_crossing_statistics()
        
        assert stats['total_entries'] == 3
        assert stats['countries_count'] == 3
        assert stats['matched_count'] == 2
        assert stats['unmatched_count'] == 1
        assert stats['match_rate'] == 2/3
        
        # Check source breakdown
        assert stats['by_source']['border_crossing_parser'] == 3
        
        # Check country breakdown
        assert stats['by_country']['GB'] == 1
        assert stats['by_country']['FR'] == 1
        assert stats['by_country']['DE'] == 1
    
    def test_get_border_crossing_airports(self):
        """Test getting airports that are border crossing points."""
        model = EuroAipModel()
        
        # Add some airports
        model.airports["EGLL"] = Airport(
            ident="EGLL",
            name="London Heathrow",
            iso_country="GB"
        )
        model.airports["LFPG"] = Airport(
            ident="LFPG",
            name="Paris Charles de Gaulle",
            iso_country="FR"
        )
        
        # Add border crossing entries
        entries = [
            BorderCrossingEntry(
                airport_name="London Heathrow",
                country_iso="GB",
                matched_airport_icao="EGLL",
                source="border_crossing_parser"
            ),
            BorderCrossingEntry(
                airport_name="Paris CDG",
                country_iso="FR",
                matched_airport_icao="LFPG",
                source="border_crossing_parser"
            ),
            BorderCrossingEntry(
                airport_name="Unmatched Airport",
                country_iso="DE",
                source="border_crossing_parser"
            )
        ]
        
        model.add_border_crossing_entries(entries)
        
        # Get border crossing airports
        border_airports = model.get_border_crossing_airports()
        
        assert len(border_airports) == 2
        airport_icaos = [airport.ident for airport in border_airports]
        assert "EGLL" in airport_icaos
        assert "LFPG" in airport_icaos
    
    def test_update_border_crossing_airports(self):
        """Test updating airport objects with border crossing information."""
        model = EuroAipModel()
        
        # Add airports
        model.airports["EGLL"] = Airport(
            ident="EGLL",
            name="London Heathrow",
            iso_country="GB"
        )
        
        # Add border crossing entry
        entry = BorderCrossingEntry(
            airport_name="London Heathrow",
            country_iso="GB",
            matched_airport_icao="EGLL",
            source="border_crossing_parser"
        )
        
        model.add_border_crossing_entry(entry)
        
        # Update airports
        model.update_border_crossing_airports()
        
        # Check that airport was updated
        airport = model.airports["EGLL"]
        assert airport.point_of_entry is True
        assert "border_crossing" in airport.sources
    
    def test_json_serialization(self):
        """Test JSON serialization with border crossing data."""
        model = EuroAipModel()
        
        # Add an airport
        model.airports["EGLL"] = Airport(
            ident="EGLL",
            name="London Heathrow",
            iso_country="GB"
        )
        
        # Add border crossing entry
        entry = BorderCrossingEntry(
            airport_name="London Heathrow",
            country_iso="GB",
            matched_airport_icao="EGLL",
            source="border_crossing_parser"
        )
        
        model.add_border_crossing_entry(entry)
        
        # Convert to dict
        data = model.to_dict()
        
        # Check that border crossing data is included
        assert "border_crossing_entries" in data
        assert "GB" in data["border_crossing_entries"]
        assert "London Heathrow" in data["border_crossing_entries"]["GB"]
        
        # Check statistics
        assert "border_crossing" in data["statistics"]
        assert data["statistics"]["border_crossing"]["total_entries"] == 1
        
        # Test saving and loading
        with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as f:
            file_path = f.name
        
        try:
            model.save_to_json(file_path)
            
            # Load the model
            loaded_model = EuroAipModel.load_from_json(file_path)
            
            # Check that data was preserved
            assert len(loaded_model.airports) == 1
            assert len(loaded_model.get_all_border_crossing_entries()) == 1
            
            # Check specific entry
            loaded_entry = loaded_model.get_border_crossing_entry("GB", "London Heathrow")
            assert loaded_entry is not None
            assert loaded_entry.airport_name == "London Heathrow"
            assert loaded_entry.country_iso == "GB"
            assert loaded_entry.matched_airport_icao == "EGLL"
            
        finally:
            os.unlink(file_path)
    
    def test_model_statistics_inclusion(self):
        """Test that border crossing data is included in model statistics."""
        model = EuroAipModel()
        
        # Add border crossing entry
        entry = BorderCrossingEntry(
            airport_name="London Heathrow",
            country_iso="GB",
            source="border_crossing_parser"
        )
        
        model.add_border_crossing_entry(entry)
        
        stats = model.get_statistics()
        
        # Check that border crossing stats are included
        assert "airports_with_border_crossing" in stats
        assert "total_border_crossing_entries" in stats
        assert "border_crossing" in stats
        
        # Check values
        assert stats["total_border_crossing_entries"] == 1
        assert stats["border_crossing"]["total_entries"] == 1 