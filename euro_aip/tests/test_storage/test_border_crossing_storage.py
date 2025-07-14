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
        """Test saving and loading border crossing points."""
        # Create test entries
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
            ),
            BorderCrossingEntry(
                airport_name="Unmatched Airport",
                country_iso="DE",
                icao_code="EDDF",
                source="border_crossing_parser"
            )
        ]
        
        # Save entries
        temp_db.save_border_crossing_data(entries)
        
        # Load entries
        loaded_entries = temp_db.load_border_crossing_data()
        
        assert len(loaded_entries) == 3
        
        # Find entries by ICAO code instead of relying on order
        heathrow_entry = next((e for e in loaded_entries if e.icao_code == "EGLL"), None)
        paris_entry = next((e for e in loaded_entries if e.icao_code == "LFPG"), None)
        unmatched_entry = next((e for e in loaded_entries if e.icao_code == "EDDF"), None)
        
        assert heathrow_entry is not None
        assert paris_entry is not None
        assert unmatched_entry is not None
        
        # Check Heathrow entry
        assert heathrow_entry.country_iso == "GB"
        assert heathrow_entry.airport_name == "London Heathrow"
        assert heathrow_entry.icao_code == "EGLL"
        assert heathrow_entry.source == "border_crossing_parser"
        
        # Check Paris entry
        assert paris_entry.country_iso == "FR"
        assert paris_entry.airport_name == "Paris Charles de Gaulle"
        assert paris_entry.icao_code == "LFPG"
        assert paris_entry.source == "border_crossing_parser"
        
        # Check unmatched entry
        assert unmatched_entry.country_iso == "DE"
        assert unmatched_entry.airport_name == "Unmatched Airport"
        assert unmatched_entry.icao_code == "EDDF"
        assert unmatched_entry.source == "border_crossing_parser"
    
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
        
        # Save initial entries
        temp_db.save_border_crossing_data(initial_entries)
        
        # Check that no changes are recorded for first-time insert
        changes = temp_db.get_border_crossing_points_changes(days=1)
        assert len(changes) == 0
        
        # Update with changes: remove Heathrow, add Gatwick for GB; add Amsterdam for NL
        updated_entries = [
            BorderCrossingEntry(
                airport_name="London Gatwick",
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
                airport_name="Amsterdam Schiphol",
                country_iso="NL",
                icao_code="EHAM",
                source="border_crossing_parser"
            )
        ]
        
        # Save updated entries
        temp_db.save_border_crossing_data(updated_entries)
        
        # Check changes
        changes = temp_db.get_border_crossing_points_changes(days=1)
        assert len(changes) == 2  # EGLL removed, EGKK added, EHAM added (but no change for first-time NL)
        
        # Find specific changes
        removed_changes = [c for c in changes if c.action == "REMOVED"]
        added_changes = [c for c in changes if c.action == "ADDED"]
        
        assert len(removed_changes) == 1
        assert len(added_changes) == 1
        
        # Check that EGLL was removed
        assert any(c.icao_code == "EGLL" and c.country_iso == "GB" for c in removed_changes)
        
        # Check that EGKK was added
        assert any(c.icao_code == "EGKK" and c.country_iso == "GB" for c in added_changes)
        
        # Check that EHAM was NOT added (first-time for NL)
        assert not any(c.icao_code == "EHAM" for c in changes)
    
    def test_border_crossing_change_tracking_per_country(self, temp_db):
        """Test that border crossing change tracking works per-country."""
        # Initial entries for GB only
        initial_entries = [
            BorderCrossingEntry(
                airport_name="London Heathrow",
                country_iso="GB",
                icao_code="EGLL",
                source="border_crossing_parser"
            )
        ]
        
        # Save initial entries
        temp_db.save_border_crossing_data(initial_entries)
        
        # Check that no changes are recorded for first-time insert
        changes = temp_db.get_border_crossing_points_changes(days=1)
        assert len(changes) == 0
        
        # Add FR entries (first-time for FR, should not create changes)
        fr_entries = [
            BorderCrossingEntry(
                airport_name="Paris CDG",
                country_iso="FR",
                icao_code="LFPG",
                source="border_crossing_parser"
            )
        ]
        
        # Save FR entries
        temp_db.save_border_crossing_data(fr_entries)
        
        # Check that no changes are recorded (first-time for FR)
        changes = temp_db.get_border_crossing_points_changes(days=1)
        assert len(changes) == 0
        
        # Now update GB (should create changes)
        updated_entries = [
            BorderCrossingEntry(
                airport_name="London Gatwick",
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
        
        # Save updated entries
        temp_db.save_border_crossing_data(updated_entries)
        
        # Check changes
        changes = temp_db.get_border_crossing_points_changes(days=1)
        assert len(changes) == 2  # EGLL removed, EGKK added
        
        # Verify changes are for GB only
        for change in changes:
            assert change.country_iso == "GB"
        
        # Check that FR was not affected
        loaded_entries = temp_db.load_border_crossing_data()
        fr_entries = [e for e in loaded_entries if e.country_iso == "FR"]
        assert len(fr_entries) == 1
        assert fr_entries[0].icao_code == "LFPG"
    
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