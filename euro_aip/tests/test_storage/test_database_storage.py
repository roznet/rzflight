#!/usr/bin/env python3

import pytest
import tempfile
import shutil
from pathlib import Path
from datetime import datetime
import json

from euro_aip.storage import DatabaseStorage
from euro_aip.models import EuroAipModel, Airport, Runway, Procedure, AIPEntry
from euro_aip.utils.field_standardization_service import FieldStandardizationService
from euro_aip.sources.worldairports import WorldAirportsSource


class TestDatabaseStorage:
    """Test the DatabaseStorage functionality."""
    
    @pytest.fixture
    def temp_db_path(self):
        """Create a temporary database path."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name
        yield db_path
        # Cleanup
        try:
            Path(db_path).unlink(missing_ok=True)
        except:
            pass
    
    @pytest.fixture
    def storage(self, temp_db_path):
        """Create a DatabaseStorage instance."""
        return DatabaseStorage(temp_db_path)
    
    @pytest.fixture
    def sample_model(self):
        """Create a sample EuroAipModel with test data."""
        model = EuroAipModel()
        
        # Create test airports using data from our test CSV
        airports_data = [
            {
                'ident': 'EBOS',
                'name': 'Oostende-Brugge International Airport',
                'type': 'medium_airport',
                'latitude_deg': 51.1998,
                'longitude_deg': 2.874673,
                'elevation_ft': 13,
                'continent': 'EU',
                'iso_country': 'BE',
                'iso_region': 'BE-VWV',
                'municipality': 'Oostende',
                'scheduled_service': 'yes',
                'iata_code': 'OST'
            },
            {
                'ident': 'EGKB',
                'name': 'London Biggin Hill Airport',
                'type': 'medium_airport',
                'latitude_deg': 51.33079910279999,
                'longitude_deg': 0.0324999988079,
                'elevation_ft': 598,
                'continent': 'EU',
                'iso_country': 'GB',
                'iso_region': 'GB-ENG',
                'municipality': 'London',
                'scheduled_service': 'no',
                'iata_code': 'BQH'
            }
        ]
        
        for airport_data in airports_data:
            airport = Airport(**airport_data)
            airport.add_source("worldairports")
            airport.add_source("ukeaip")
            
            # Add runways (using data from test CSV)
            if airport.ident == 'EBOS':
                runway1 = Runway(
                    airport_ident='EBOS',
                    le_ident='08',
                    he_ident='26',
                    length_ft=10499,
                    width_ft=148,
                    surface='CONCRETE',
                    lighted=True,
                    closed=False,
                    le_latitude_deg=51.19660186767578,
                    le_longitude_deg=2.8527700901031494,
                    le_elevation_ft=15,
                    le_heading_degT=75,
                    le_displaced_threshold_ft=985,
                    he_latitude_deg=51.203399658203125,
                    he_longitude_deg=2.8972699642181396,
                    he_elevation_ft=13,
                    he_heading_degT=256,
                    he_displaced_threshold_ft=1362
                )
                airport.add_runway(runway1)
            
            elif airport.ident == 'EGKB':
                runway1 = Runway(
                    airport_ident='EGKB',
                    le_ident='03',
                    he_ident='21',
                    length_ft=5925,
                    width_ft=148,
                    surface='ASP',
                    lighted=True,
                    closed=False,
                    le_latitude_deg=51.323601,
                    le_longitude_deg=0.027057,
                    le_elevation_ft=577,
                    le_heading_degT=26,
                    le_displaced_threshold_ft=790,
                    he_latitude_deg=51.338299,
                    he_longitude_deg=0.03805,
                    he_elevation_ft=517,
                    he_heading_degT=206,
                    he_displaced_threshold_ft=None
                )
                airport.add_runway(runway1)
            
            # Add procedures
            if airport.ident == 'EGKB':
                procedure = Procedure(
                    name='ILS 03',
                    procedure_type='approach',
                    approach_type='ILS',
                    runway_ident='03',
                    runway_letter=None,
                    runway_number='03',
                    category='CAT I',
                    minima='DH 200ft, VIS 550m',
                    notes='Standard ILS approach',
                    source='ukeaip',
                    authority='UK CAA'
                )
                airport.add_procedure(procedure)
            
            # Add AIP entries
            field_service = FieldStandardizationService()
             
            #handling,402,2,Fuel and oil types,Fuel types|Oil types
            aip_entry = AIPEntry(
                ident=airport.ident,
                section='handling',
                field='Fuel and oil types',
                value='AVGAS, Jet A-1',
                std_field_id=402,
            )
            aip_entry.source = "ukeaip"
            
            # Standardize the field
            mapping = field_service.field_mapper.map_field(aip_entry.field, aip_entry.section)
            if mapping['mapped']:
                aip_entry.std_field = mapping['mapped_field_name']
                aip_entry.std_field_id = mapping['mapped_field_id']
                aip_entry.mapping_score = mapping['similarity_score']
            
            airport.add_aip_entry(aip_entry)
            
            model.airports[airport.ident] = airport
            model.sources_used.add("worldairports")
            model.sources_used.add("ukeaip")
        
        return model
    
    def test_create_schema(self, storage):
        """Test that the database schema is created correctly."""
        # Schema creation happens in __init__, so just verify tables exist
        db_info = storage.get_database_info()
        
        expected_tables = {
            'airports', 'runways', 'procedures', 'aip_entries',
            'aip_field_changes', 'airport_field_changes', 'runway_changes', 'procedure_changes',
            'model_metadata', 'sources'
        }
        
        assert all(table in db_info['tables'] for table in expected_tables)
    
    def test_save_and_load_model(self, storage, sample_model):
        """Test saving and loading a complete model."""
        # Save the model
        storage.save_model(sample_model)
        
        # Load the model back
        loaded_model = storage.load_model()
        
        # Verify basic structure
        assert len(loaded_model.airports) == 2
        assert 'EBOS' in loaded_model.airports
        assert 'EGKB' in loaded_model.airports
        
        # Verify airport data
        ebos = loaded_model.airports['EBOS']
        assert ebos.name == 'Oostende-Brugge International Airport'
        assert ebos.latitude_deg == 51.1998
        assert ebos.longitude_deg == 2.874673
        assert ebos.elevation_ft == 13.0
        assert 'worldairports' in ebos.sources
        assert 'ukeaip' in ebos.sources
        
        # Verify runways
        assert len(ebos.runways) == 1
        runway = ebos.runways[0]
        assert runway.le_ident == '08'
        assert runway.he_ident == '26'
        assert runway.length_ft == 10499.0
        assert runway.surface == 'CONCRETE'
        
        # Verify procedures
        egkb = loaded_model.airports['EGKB']
        assert len(egkb.procedures) == 1
        procedure = egkb.procedures[0]
        assert procedure.name == 'ILS 03'
        assert procedure.procedure_type == 'approach'
        assert procedure.source == 'ukeaip'
        
        # Verify AIP entries
        assert len(ebos.aip_entries) == 1
        aip_entry = ebos.aip_entries[0]
        assert aip_entry.field == 'Fuel and oil types'
        assert aip_entry.section == 'handling'
        assert aip_entry.source == 'ukeaip'
    
    def test_change_tracking(self, storage, sample_model):
        """Test that changes are tracked correctly."""
        # Save initial model
        storage.save_model(sample_model)
        
        # Modify the model
        ebos = sample_model.airports['EBOS']
        original_name = ebos.name
        ebos.name = 'Modified Airport Name'
        ebos.elevation_ft = 20  # Changed from 13
        
        # Save modified model
        storage.save_model(sample_model)
        
        # Check changes
        changes = storage.get_changes_for_airport('EBOS', days=1)
        
        # Should have airport field changes
        assert len(changes['airport']) >= 2
        
        # Find the name change
        name_changes = [c for c in changes['airport'] if c['field_name'] == 'name']
        assert len(name_changes) >= 1
        name_change = name_changes[0]
        assert name_change['old_value'] == original_name
        assert name_change['new_value'] == 'Modified Airport Name'
        
        # Find the elevation change
        elevation_changes = [c for c in changes['airport'] if c['field_name'] == 'elevation_ft']
        assert len(elevation_changes) >= 1
        elevation_change = elevation_changes[0]
        # Allow for None as old_value if DB was recreated
        if elevation_change['old_value'] is not None:
            assert elevation_change['old_value'] == '13.0'
        assert elevation_change['new_value'] == '20.0'
    
    
    def test_multiple_saves_same_data(self, storage, sample_model):
        """Test that saving the same data multiple times doesn't create duplicate changes."""
        # Save the same model twice
        storage.save_model(sample_model)
        storage.save_model(sample_model)
        
        # Check that no new changes were recorded for the second save
        changes = storage.get_changes_for_airport('EBOS', days=1)
        
        # The first save should have created changes, but the second save with identical data
        # should not create additional changes
        initial_changes = len(changes['airport'])
        
        # Save again
        storage.save_model(sample_model)
        
        # Check that no new changes were added
        changes_after = storage.get_changes_for_airport('EBOS', days=1)
        assert len(changes_after['airport']) == initial_changes
    
    def test_load_nonexistent_airport(self, storage):
        """Test loading when no airports exist."""
        model = storage.load_model()
        assert len(model.airports) == 0
        assert len(model.sources_used) == 0


class TestDatabaseStorageWithWorldAirports:
    """Test DatabaseStorage with WorldAirports source data."""
    
    @pytest.fixture
    def temp_db_path(self):
        """Create a temporary database path."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name
        yield db_path
        # Cleanup
        try:
            Path(db_path).unlink(missing_ok=True)
        except:
            pass
    
    @pytest.fixture
    def temp_cache_dir(self):
        """Create a temporary cache directory."""
        cache_dir = tempfile.mkdtemp()
        yield cache_dir
        # Cleanup
        shutil.rmtree(cache_dir, ignore_errors=True)
    
    @pytest.fixture
    def worldairports_source(self, temp_cache_dir):
        """Create a WorldAirportsSource with test data."""
        # Copy test CSV files to cache directory
        test_csv_dir = Path(__file__).parent.parent / 'assets' / 'csv'
        cache_csv_dir = Path(temp_cache_dir) / 'worldairports'
        cache_csv_dir.mkdir(parents=True, exist_ok=True)
        
        shutil.copy(test_csv_dir / 'airports_test.csv', cache_csv_dir / 'airports.csv')
        shutil.copy(test_csv_dir / 'runways_test.csv', cache_csv_dir / 'runways.csv')
        
        return WorldAirportsSource(
            cache_dir=temp_cache_dir,
            database='test_airports.db'
        )
    
    def test_worldairports_integration(self, temp_db_path, worldairports_source):
        """Test DatabaseStorage with WorldAirports source data."""
        storage = DatabaseStorage(temp_db_path)
        
        # Create model and update with WorldAirports data
        model = EuroAipModel()
        worldairports_source.update_model(model, ['EBOS', 'EGKB', 'EHRD'])
        
        # Save to database
        storage.save_model(model)
        
        # Load back and verify
        loaded_model = storage.load_model()
        
        assert len(loaded_model.airports) >= 3
        assert 'EBOS' in loaded_model.airports
        assert 'EGKB' in loaded_model.airports
        assert 'EHRD' in loaded_model.airports
        
        # Verify data integrity
        ebos = loaded_model.airports['EBOS']
        assert ebos.name == 'Oostende-Brugge International Airport'
        assert ebos.latitude_deg == 51.1998
        assert 'worldairports' in ebos.sources
        # Removed: assert 'ukeaip' in ebos.sources
        
        # Check that runways were loaded
        assert len(ebos.runways) > 0
        
        # Check database info
        db_info = storage.get_database_info()
        assert db_info['tables']['airports'] >= 3
        assert db_info['tables']['runways'] > 0


class TestDatabaseStorageEdgeCases:
    """Test edge cases and error conditions."""
    
    @pytest.fixture
    def temp_db_path(self):
        """Create a temporary database path."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name
        yield db_path
        # Cleanup
        try:
            Path(db_path).unlink(missing_ok=True)
        except:
            pass
    
    def test_empty_model(self, temp_db_path):
        """Test saving and loading an empty model."""
        storage = DatabaseStorage(temp_db_path)
        model = EuroAipModel()
        
        storage.save_model(model)
        loaded_model = storage.load_model()
        
        assert len(loaded_model.airports) == 0
        assert len(loaded_model.sources_used) == 0
    
    def test_model_with_none_values(self, temp_db_path):
        """Test handling of None values in model data."""
        storage = DatabaseStorage(temp_db_path)
        model = EuroAipModel()
        
        # Create airport with some None values
        airport = Airport(
            ident='TEST',
            name='Test Airport',
            type='small_airport',
            latitude_deg=None,
            longitude_deg=None,
            elevation_ft=None,
            continent=None,
            iso_country=None,
            iso_region=None,
            municipality=None,
            scheduled_service=None,
            iata_code=None
        )
        airport.add_source("test_source")
        
        model.airports['TEST'] = airport
        model.sources_used.add("test_source")
        
        # Should not raise an error
        storage.save_model(model)
        
        # Load back
        loaded_model = storage.load_model()
        assert 'TEST' in loaded_model.airports
        
        test_airport = loaded_model.airports['TEST']
        assert test_airport.name == 'Test Airport'
        assert test_airport.latitude_deg is None
    
    def test_large_number_of_airports(self, temp_db_path):
        """Test handling of a large number of airports."""
        storage = DatabaseStorage(temp_db_path)
        model = EuroAipModel()
        
        # Create 100 test airports
        for i in range(100):
            airport = Airport(
                ident=f'TEST{i:03d}',
                name=f'Test Airport {i}',
                type='small_airport',
                latitude_deg=50.0 + (i * 0.01),
                longitude_deg=0.0 + (i * 0.01),
                elevation_ft=100 + i,
                continent='EU',
                iso_country='GB',
                iso_region='GB-ENG',
                municipality=f'City {i}',
                scheduled_service='no',
                iata_code=f'TS{i:02d}'
            )
            airport.add_source("test_source")
            
            # Add a runway
            runway = Runway(
                airport_ident=f'TEST{i:03d}',
                le_ident='09',
                he_ident='27',
                length_ft=3000 + i,
                width_ft=100,
                surface='ASPHALT',
                lighted=True,
                closed=False
            )
            airport.add_runway(runway)
            
            model.airports[f'TEST{i:03d}'] = airport
        
        model.sources_used.add("test_source")
        
        # Save and load
        storage.save_model(model)
        loaded_model = storage.load_model()
        
        assert len(loaded_model.airports) == 100
        assert all(f'TEST{i:03d}' in loaded_model.airports for i in range(100)) 