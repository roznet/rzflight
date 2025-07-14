"""
Tests for border crossing storage functionality in DatabaseStorage.
"""

import pytest
import tempfile
import os
from datetime import datetime
from euro_aip.storage.database_storage import DatabaseStorage
from euro_aip.models.border_crossing_entry import BorderCrossingEntry
from euro_aip.models.border_crossing_change import BorderCrossingChange


class TestBorderCrossingStorage:
    """Test cases for border crossing storage functionality."""
    
    @pytest.fixture
    def temp_db(self):
        """Create a temporary database for testing."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name
        
        storage = DatabaseStorage(db_path)
        yield storage
        
        # Cleanup
        os.unlink(db_path)
    
    def test_save_and_load_border_crossing_points(self, temp_db):
        """Test saving and loading border crossing entries."""
        entries = [
            BorderCrossingEntry(
                airport_name="London Heathrow",
                country_iso="GB",
                icao_code="EGLL",
                source="border_crossing_parser",
                extraction_method="html_table_parsing",
                metadata={"number": "1"},
                matched_airport_icao="EGLL",
                match_score=0.95
            ),
            BorderCrossingEntry(
                airport_name="Paris Charles de Gaulle",
                country_iso="FR",
                icao_code="LFPG",
                source="border_crossing_parser",
                extraction_method="html_table_parsing",
                metadata={"number": "2"},
                matched_airport_icao="LFPG",
                match_score=0.9
            ),
            BorderCrossingEntry(
                airport_name="Unmatched Airport",
                country_iso="DE",
                source="border_crossing_parser",
                extraction_method="html_table_parsing",
                metadata={"number": "3"},
                match_score=None
            )
        ]
        
        # Save entries
        temp_db.save_border_crossing_data(entries)
        
        # Load entries
        loaded_entries = temp_db.load_border_crossing_data()
        
        assert len(loaded_entries) == 3
        
        # Find entries by airport name instead of relying on order
        heathrow_entry = next((e for e in loaded_entries if e.airport_name == "London Heathrow"), None)
        paris_entry = next((e for e in loaded_entries if e.airport_name == "Paris Charles de Gaulle"), None)
        unmatched_entry = next((e for e in loaded_entries if e.airport_name == "Unmatched Airport"), None)
        
        assert heathrow_entry is not None
        assert paris_entry is not None
        assert unmatched_entry is not None
        
        # Check Heathrow entry
        assert heathrow_entry.country_iso == "GB"
        assert heathrow_entry.icao_code == "EGLL"
        assert heathrow_entry.source == "border_crossing_parser"
        assert heathrow_entry.matched_airport_icao == "EGLL"
        assert heathrow_entry.match_score == 0.95
        assert heathrow_entry.metadata == {"number": "1"}
        
        # Check Paris entry
        assert paris_entry.country_iso == "FR"
        assert paris_entry.icao_code == "LFPG"
        
        # Check unmatched entry
        assert unmatched_entry.country_iso == "DE"
        assert unmatched_entry.icao_code is None
        assert unmatched_entry.matched_airport_icao is None
        assert unmatched_entry.match_score is None
    
    def test_border_crossing_points_changes(self, temp_db):
        """Test border crossing change detection and tracking (per-country, no first-time change)."""
        # Initial entries for two countries
        initial_entries = [
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
            )
        ]
        
        # Save initial entries (should NOT create any change entries)
        temp_db.save_border_crossing_data(initial_entries)
        changes_after_first = temp_db.get_border_crossing_points_changes(days=30)
        assert changes_after_first == []  # No changes for first insert per country
        
        # New entries: add one for GB, remove FR, add NL
        new_entries = [
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
            ),
            BorderCrossingEntry(
                airport_name="Amsterdam Schiphol",
                country_iso="NL",
                icao_code="EHAM",
                source="border_crossing_parser"
            )
        ]
        temp_db.save_border_crossing_data(new_entries)
        changes = temp_db.get_border_crossing_points_changes(days=30)
        # Should have 2 changes for GB (1 added, 1 removed), 0 for NL (first insert), 1 for FR (removed)
        gb_changes = [c for c in changes if c.country_iso == "GB"]
        fr_changes = [c for c in changes if c.country_iso == "FR"]
        nl_changes = [c for c in changes if c.country_iso == "NL"]
        # GB: Manchester added, Paris CDG removed (but Paris CDG is FR, so only added for GB)
        assert any(c.action == "ADDED" and c.airport_name == "Manchester" for c in gb_changes)
        # FR: Paris CDG removed
        assert any(c.action == "REMOVED" and c.airport_name == "Paris CDG" for c in fr_changes)
        # NL: No changes for first insert
        assert nl_changes == []

    def test_border_crossing_change_tracking_per_country(self, temp_db):
        """Test that change tracking is per-country and no changes for first-time country insert."""
        # Insert for one country
        gb_entries = [
            BorderCrossingEntry(
                airport_name="London Heathrow",
                country_iso="GB",
                icao_code="EGLL",
                source="border_crossing_parser"
            )
        ]
        temp_db.save_border_crossing_data(gb_entries)
        # No changes for first insert
        assert temp_db.get_border_crossing_points_changes(days=30) == []
        # Add a new airport for GB (should record an ADDED change)
        gb_entries2 = [
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
        temp_db.save_border_crossing_data(gb_entries2)
        changes = temp_db.get_border_crossing_points_changes(days=30)
        gb_changes = [c for c in changes if c.country_iso == "GB"]
        assert any(c.action == "ADDED" and c.airport_name == "Manchester" for c in gb_changes)
        # Now add a new country (NL) - should NOT record changes for NL
        nl_entries = gb_entries2 + [
            BorderCrossingEntry(
                airport_name="Amsterdam Schiphol",
                country_iso="NL",
                icao_code="EHAM",
                source="border_crossing_parser"
            )
        ]
        temp_db.save_border_crossing_data(nl_entries)
        changes = temp_db.get_border_crossing_points_changes(days=30)
        nl_changes = [c for c in changes if c.country_iso == "NL"]
        assert nl_changes == []
    
    def test_border_crossing_statistics(self, temp_db):
        """Test border crossing statistics."""
        entries = [
            BorderCrossingEntry(
                airport_name="London Heathrow",
                country_iso="GB",
                icao_code="EGLL",
                source="border_crossing_parser",
                matched_airport_icao="EGLL",
                match_score=0.95
            ),
            BorderCrossingEntry(
                airport_name="Paris CDG",
                country_iso="FR",
                icao_code="LFPG",
                source="border_crossing_parser",
                matched_airport_icao="LFPG",
                match_score=0.9
            ),
            BorderCrossingEntry(
                airport_name="Unmatched Airport",
                country_iso="DE",
                source="border_crossing_parser"
            ),
            BorderCrossingEntry(
                airport_name="Another UK Airport",
                country_iso="GB",
                source="border_crossing_parser"
            )
        ]
        
        temp_db.save_border_crossing_data(entries)
        
        stats = temp_db.get_border_crossing_statistics()
        
        assert stats['total_entries'] == 4
        assert stats['matched_count'] == 2
        assert stats['unmatched_count'] == 2
        assert stats['match_rate'] == 0.5
        
        # Check country breakdown
        assert stats['by_country']['GB'] == 2
        assert stats['by_country']['FR'] == 1
        assert stats['by_country']['DE'] == 1
        
        # Check source breakdown
        assert stats['by_source']['border_crossing_parser'] == 4
    
    def test_border_crossing_by_country(self, temp_db):
        """Test getting border crossing entries by country."""
        entries = [
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
            )
        ]
        
        temp_db.save_border_crossing_data(entries)
        
        # Get UK entries
        uk_entries = temp_db.get_border_crossing_by_country("GB")
        assert len(uk_entries) == 2
        assert all(entry['country_iso'] == 'GB' for entry in uk_entries)
        
        # Get French entries
        fr_entries = temp_db.get_border_crossing_by_country("FR")
        assert len(fr_entries) == 1
        assert fr_entries[0]['country_iso'] == 'FR'
        assert fr_entries[0]['airport_name'] == 'Paris CDG'
        
        # Get non-existent country
        no_entries = temp_db.get_border_crossing_by_country("XX")
        assert len(no_entries) == 0
    
    def test_border_crossing_airports_join(self, temp_db):
        """Test joining border crossing entries with airports."""
        # First save some airports
        from euro_aip.models.euro_aip_model import EuroAipModel
        from euro_aip.models.airport import Airport
        
        model = EuroAipModel()
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
        
        temp_db.save_model(model)
        
        # Save border crossing entries
        entries = [
            BorderCrossingEntry(
                airport_name="London Heathrow",
                country_iso="GB",
                icao_code="EGLL",
                source="border_crossing_parser",
                matched_airport_icao="EGLL",
                match_score=0.95
            ),
            BorderCrossingEntry(
                airport_name="Paris CDG",
                country_iso="FR",
                icao_code="LFPG",
                source="border_crossing_parser",
                matched_airport_icao="LFPG",
                match_score=0.9
            )
        ]
        
        temp_db.save_border_crossing_data(entries)
        
        # Get joined data
        border_airports = temp_db.get_border_crossing_airports()
        
        assert len(border_airports) == 2
        
        # Check first airport
        heathrow = next(a for a in border_airports if a['icao_code'] == 'EGLL')
        assert heathrow['name'] == 'London Heathrow'
        assert heathrow['iso_country'] == 'GB'
        assert heathrow['border_crossing_name'] == 'London Heathrow'
        assert heathrow['source'] == 'border_crossing_parser'
        assert heathrow['match_score'] == 0.95
        
        # Check second airport
        paris = next(a for a in border_airports if a['icao_code'] == 'LFPG')
        assert paris['name'] == 'Paris Charles de Gaulle'
        assert paris['iso_country'] == 'FR'
        assert paris['border_crossing_name'] == 'Paris CDG'
        assert paris['source'] == 'border_crossing_parser'
        assert paris['match_score'] == 0.9 