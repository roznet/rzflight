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
            source="border_crossing_parser"
        )
        
        model.add_border_crossing_entry(entry)
        
        # Check that entry was added correctly
        assert "GB" in model.border_crossing_points
        assert "EGLL" in model.border_crossing_points["GB"]
        assert model.border_crossing_points["GB"]["EGLL"] == entry
        
        # Check source tracking
        assert "border_crossing_parser" in model.sources_used
    
    def test_add_border_crossing_points(self):
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
                airport_name="Paris Charles de Gaulle",
                country_iso="FR",
                icao_code="LFPG",
                source="border_crossing_parser"
            )
        ]
        
        model.add_border_crossing_points(entries)
        
        # Check that entries were added correctly
        assert len(model.get_all_border_crossing_points()) == 2
        assert "GB" in model.border_crossing_points
        assert "FR" in model.border_crossing_points
        assert "EGLL" in model.border_crossing_points["GB"]
        assert "LFPG" in model.border_crossing_points["FR"]
    
    def test_get_border_crossing_points_by_country(self):
        """Test getting border crossing entries by country."""
        model = EuroAipModel()
        
        entries = [
            BorderCrossingEntry(
                airport_name="London Heathrow",
                country_iso="GB",
                icao_code="EGLL",
                source="border_crossing_parser"
            ),
            BorderCrossingEntry(
                airport_name="Paris Charles de Gaulle",
                country_iso="FR",
                icao_code="LFPG",
                source="border_crossing_parser"
            )
        ]
        
        model.add_border_crossing_points(entries)
        
        # Test getting entries for existing country
        gb_entries = model.get_border_crossing_points_by_country("GB")
        assert len(gb_entries) == 1
        assert gb_entries[0].airport_name == "London Heathrow"
        assert gb_entries[0].icao_code == "EGLL"
        
        # Test getting entries for non-existing country
        us_entries = model.get_border_crossing_points_by_country("US")
        assert len(us_entries) == 0
    
    def test_get_border_crossing_entry(self):
        """Test getting a specific border crossing entry by ICAO code."""
        model = EuroAipModel()
        
        entry = BorderCrossingEntry(
            airport_name="London Heathrow",
            country_iso="GB",
            icao_code="EGLL",
            source="border_crossing_parser"
        )
        
        model.add_border_crossing_entry(entry)
        
        # Test getting existing entry
        found_entry = model.get_border_crossing_entry("GB", "EGLL")
        assert found_entry is not None
        assert found_entry.airport_name == "London Heathrow"
        assert found_entry.icao_code == "EGLL"
        
        # Test getting non-existing entry
        not_found = model.get_border_crossing_entry("GB", "EGKK")
        assert not_found is None
        
        # Test getting entry from non-existing country
        not_found = model.get_border_crossing_entry("XX", "EGLL")
        assert not_found is None
    
    def test_get_border_crossing_entry_by_name(self):
        """Test getting a border crossing entry by airport name (backward compatibility)."""
        model = EuroAipModel()
        
        entry = BorderCrossingEntry(
            airport_name="London Heathrow",
            country_iso="GB",
            icao_code="EGLL",
            source="border_crossing_parser"
        )
        
        model.add_border_crossing_entry(entry)
        
        # Test getting existing entry by name
        found_entry = model.get_border_crossing_entry_by_name("GB", "London Heathrow")
        assert found_entry is not None
        assert found_entry.airport_name == "London Heathrow"
        assert found_entry.icao_code == "EGLL"
        
        # Test getting non-existing entry by name
        not_found = model.get_border_crossing_entry_by_name("GB", "Non-existent")
        assert not_found is None
        
        # Test getting entry from non-existing country
        not_found = model.get_border_crossing_entry_by_name("XX", "London Heathrow")
        assert not_found is None
    
    def test_get_all_border_crossing_points(self):
        """Test getting all border crossing entries."""
        model = EuroAipModel()
        
        entries = [
            BorderCrossingEntry(
                airport_name="London Heathrow",
                country_iso="GB",
                icao_code="EGLL",
                source="border_crossing_parser"
            ),
            BorderCrossingEntry(
                airport_name="Paris Charles de Gaulle",
                country_iso="FR",
                icao_code="LFPG",
                source="border_crossing_parser"
            )
        ]
        
        model.add_border_crossing_points(entries)
        
        all_entries = model.get_all_border_crossing_points()
        assert len(all_entries) == 2
        
        # Check that both entries are present
        icao_codes = {entry.icao_code for entry in all_entries}
        assert "EGLL" in icao_codes
        assert "LFPG" in icao_codes
    
    def test_get_border_crossing_countries(self):
        """Test getting list of countries with border crossing entries."""
        model = EuroAipModel()
        
        entries = [
            BorderCrossingEntry(
                airport_name="London Heathrow",
                country_iso="GB",
                icao_code="EGLL",
                source="border_crossing_parser"
            ),
            BorderCrossingEntry(
                airport_name="Paris Charles de Gaulle",
                country_iso="FR",
                icao_code="LFPG",
                source="border_crossing_parser"
            )
        ]
        
        model.add_border_crossing_points(entries)
        
        countries = model.get_border_crossing_countries()
        assert len(countries) == 2
        assert "GB" in countries
        assert "FR" in countries
    
    def test_remove_border_crossing_points_by_country(self):
        """Test removing border crossing entries by country."""
        model = EuroAipModel()
        
        entries = [
            BorderCrossingEntry(
                airport_name="London Heathrow",
                country_iso="GB",
                icao_code="EGLL",
                source="border_crossing_parser"
            ),
            BorderCrossingEntry(
                airport_name="Paris Charles de Gaulle",
                country_iso="FR",
                icao_code="LFPG",
                source="border_crossing_parser"
            )
        ]
        
        model.add_border_crossing_points(entries)
        
        # Verify initial state
        assert len(model.get_all_border_crossing_points()) == 2
        assert "GB" in model.border_crossing_points
        assert "FR" in model.border_crossing_points
        
        # Remove GB entries
        model.remove_border_crossing_points_by_country("GB")
        
        # Verify GB was removed but FR remains
        assert len(model.get_all_border_crossing_points()) == 1
        assert "GB" not in model.border_crossing_points
        assert "FR" in model.border_crossing_points
        
        # Remove non-existing country (should not error)
        model.remove_border_crossing_points_by_country("XX")
        
        # Verify FR still exists
        assert "FR" in model.border_crossing_points
    
    def test_get_border_crossing_statistics(self):
        """Test border crossing statistics."""
        model = EuroAipModel()
        
        entries = [
            BorderCrossingEntry(
                airport_name="London Heathrow",
                country_iso="GB",
                icao_code="EGLL",
                matched_airport_icao="EGLL",
                match_score=0.95,
                source="border_crossing_parser"
            ),
            BorderCrossingEntry(
                airport_name="Paris CDG",
                country_iso="FR",
                icao_code="LFPG",
                matched_airport_icao="LFPG",
                match_score=0.9,
                source="border_crossing_parser"
            ),
            BorderCrossingEntry(
                airport_name="Unmatched Airport",
                country_iso="DE",
                icao_code="EDDF",
                source="border_crossing_parser"
            )
        ]
        
        model.add_border_crossing_points(entries)
        
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
                icao_code="EGLL",
                matched_airport_icao="EGLL",
                source="border_crossing_parser"
            ),
            BorderCrossingEntry(
                airport_name="Paris CDG",
                country_iso="FR",
                icao_code="LFPG",
                matched_airport_icao="LFPG",
                source="border_crossing_parser"
            ),
            BorderCrossingEntry(
                airport_name="Unmatched Airport",
                country_iso="DE",
                icao_code="EDDF",
                source="border_crossing_parser"
            )
        ]
        
        model.add_border_crossing_points(entries)
        
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
            icao_code="EGLL",
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
    
    
    def test_model_statistics_inclusion(self):
        """Test that border crossing data is included in model statistics."""
        model = EuroAipModel()
        
        # Add border crossing entry
        entry = BorderCrossingEntry(
            airport_name="London Heathrow",
            country_iso="GB",
            icao_code="EGLL",
            source="border_crossing_parser"
        )
        
        model.add_border_crossing_entry(entry)
        
        stats = model.get_statistics()
        
        # Check that border crossing stats are included
        assert "airports_with_border_crossing" in stats
        assert "total_border_crossing_points" in stats
        assert "border_crossing" in stats
        
        # Check values
        assert stats["total_border_crossing_points"] == 1
        assert stats["border_crossing"]["total_entries"] == 1
    
    def test_per_country_border_crossing_updates(self):
        """Test that updating border crossing data for one country doesn't affect other countries."""
        model = EuroAipModel()
        
        # Initial setup: add entries for two countries
        initial_entries = [
            BorderCrossingEntry(
                airport_name="London Heathrow",
                country_iso="GB",
                icao_code="EGLL",
                source="border_crossing_parser"
            ),
            BorderCrossingEntry(
                airport_name="Gatwick",
                country_iso="GB",
                icao_code="EGKK",
                source="border_crossing_parser"
            ),
            BorderCrossingEntry(
                airport_name="Paris CDG",
                country_iso="FR",
                icao_code="LFPG",
                source="border_crossing_parser"
            ),
            BorderCrossingEntry(
                airport_name="Nice",
                country_iso="FR",
                icao_code="LFMN",
                source="border_crossing_parser"
            )
        ]
        
        model.add_border_crossing_points(initial_entries)
        
        # Verify initial state
        assert len(model.get_all_border_crossing_points()) == 4
        assert len(model.get_border_crossing_points_by_country("GB")) == 2
        assert len(model.get_border_crossing_points_by_country("FR")) == 2
        
        # Update only GB: remove Gatwick, add Manchester
        updated_gb_entries = [
            BorderCrossingEntry(
                airport_name="London Heathrow",
                country_iso="GB",
                icao_code="EGLL",
                source="border_crossing_parser"
            ),
            BorderCrossingEntry(
                airport_name="Manchester",
                country_iso="GB",
                icao_code="EGCC",
                source="border_crossing_parser"
            )
        ]
        
        # Remove existing GB entries and add new ones (simulating per-country update)
        model.remove_border_crossing_points_by_country("GB")
        model.add_border_crossing_points(updated_gb_entries)
        
        # Verify GB was updated correctly
        gb_entries = model.get_border_crossing_points_by_country("GB")
        assert len(gb_entries) == 2
        gb_airport_names = [entry.airport_name for entry in gb_entries]
        assert "London Heathrow" in gb_airport_names
        assert "Manchester" in gb_airport_names
        assert "Gatwick" not in gb_airport_names  # Should be removed
        
        # Verify FR was NOT affected
        fr_entries = model.get_border_crossing_points_by_country("FR")
        assert len(fr_entries) == 2
        fr_airport_names = [entry.airport_name for entry in fr_entries]
        assert "Paris CDG" in fr_airport_names
        assert "Nice" in fr_airport_names
        
        # Verify total count is correct
        assert len(model.get_all_border_crossing_points()) == 4  # 2 GB + 2 FR
        
        # Verify statistics are correct
        stats = model.get_border_crossing_statistics()
        assert stats['total_entries'] == 4
        assert stats['countries_count'] == 2
        assert stats['by_country']['GB'] == 2
        assert stats['by_country']['FR'] == 2
    
    def test_border_crossing_deduplication_and_completeness(self):
        """Test deduplication logic and is_more_complete functionality."""
        model = EuroAipModel()
        
        # Test 1: Same ICAO, different names - should keep only the more complete entry
        entry1 = BorderCrossingEntry(
            airport_name="London Heathrow",
            country_iso="GB",
            icao_code="EGLL",
            source="border_crossing_parser"
        )
        
        entry2 = BorderCrossingEntry(
            airport_name="London Heathrow Airport",  # Slightly different name
            country_iso="GB",
            icao_code="EGLL",  # Same ICAO
            metadata={"info": "extra"},  # More complete
            source="border_crossing_parser"
        )
        
        # Add the less complete entry first
        model.add_border_crossing_entry(entry1)
        # Add the more complete entry second
        model.add_border_crossing_entry(entry2)
        
        # Should only have one entry for EGLL, and it should be the more complete one
        gb_entries = model.get_border_crossing_points_by_country("GB")
        assert len(gb_entries) == 1
        stored_entry = gb_entries[0]
        assert stored_entry.airport_name == "London Heathrow Airport"
        assert stored_entry.icao_code == "EGLL"
        assert stored_entry.metadata == {"info": "extra"}
        
        # Now add the less complete entry again, it should NOT override the more complete one
        model.add_border_crossing_entry(entry1)
        gb_entries = model.get_border_crossing_points_by_country("GB")
        assert len(gb_entries) == 1
        stored_entry = gb_entries[0]
        assert stored_entry.airport_name == "London Heathrow Airport"
        assert stored_entry.icao_code == "EGLL"
        assert stored_entry.metadata == {"info": "extra"}

        # Test 2: Same ICAO, one with matched_airport_icao, one without
        # The one WITHOUT matched_airport_icao should be kept (more complete)
        model = EuroAipModel()  # Fresh model
        
        entry_with_match = BorderCrossingEntry(
            airport_name="London Heathrow",
            country_iso="GB",
            icao_code="EGLL",
            matched_airport_icao="EGLL",  # Has match
            match_score=0.95,
            source="border_crossing_parser"
        )
        
        entry_without_match = BorderCrossingEntry(
            airport_name="London Heathrow",
            country_iso="GB",
            icao_code="EGLL",
            # No matched_airport_icao - this should be considered more complete
            source="border_crossing_parser"
        )
        
        # Verify is_more_complete logic
        assert entry_without_match.is_more_complete_than(entry_with_match)
        assert not entry_with_match.is_more_complete_than(entry_without_match)
        
        # Add both entries
        model.add_border_crossing_entry(entry_with_match)
        model.add_border_crossing_entry(entry_without_match)
        
        # Should only have one entry
        gb_entries = model.get_border_crossing_points_by_country("GB")
        assert len(gb_entries) == 1
        
        # The entry WITHOUT matched_airport_icao should be kept
        stored_entry = gb_entries[0]
        assert stored_entry.matched_airport_icao is None
        assert stored_entry.icao_code == "EGLL"
        
        # Test 3: Same ICAO, different completeness levels
        model = EuroAipModel()  # Fresh model
        
        entry_basic = BorderCrossingEntry(
            airport_name="London Heathrow",
            country_iso="GB",
            icao_code="EGLL",
            source="border_crossing_parser"
        )
        
        entry_complete = BorderCrossingEntry(
            airport_name="London Heathrow",
            country_iso="GB",
            icao_code="EGLL",
            matched_airport_icao="EGLL",
            match_score=0.95,
            metadata={"additional_info": "test"},
            source="border_crossing_parser"
        )
        
        # According to the rule, the native entry should always be preferred
        assert entry_basic.is_more_complete_than(entry_complete)
        assert not entry_complete.is_more_complete_than(entry_basic)
        
        # Add both entries
        model.add_border_crossing_entry(entry_basic)
        model.add_border_crossing_entry(entry_complete)
        
        # Should only have one entry
        gb_entries = model.get_border_crossing_points_by_country("GB")
        assert len(gb_entries) == 1
        
        # The native entry should be kept
        stored_entry = gb_entries[0]
        assert stored_entry.matched_airport_icao is None
        assert stored_entry.icao_code == "EGLL" 