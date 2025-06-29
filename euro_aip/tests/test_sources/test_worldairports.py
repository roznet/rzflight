import pytest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch
import pandas as pd

from euro_aip.sources.worldairports import WorldAirportsSource
from euro_aip.models.euro_aip_model import EuroAipModel


class TestWorldAirportsSource(WorldAirportsSource):
    """Test-specific subclass that uses local test files instead of downloading."""
    
    def __init__(self, cache_dir: str, database: str = 'test_airports.db'):
        super().__init__(cache_dir, database)
        # Override file paths to use test files
        test_assets_dir = Path(__file__).parent.parent / 'assets' / 'csv'
        self.airports_file = test_assets_dir / 'airports_test.csv'
        self.runways_file = test_assets_dir / 'runways_test.csv'
    
    def get_source_name(self) -> str:
        """Override to return the same source name as the original class."""
        return 'WorldAirportsSource'
    
    def fetch_airports(self) -> pd.DataFrame:
        """Override to use local test files instead of downloading."""
        # Read directly from test files
        df = pd.read_csv(self.airports_file, encoding='utf-8-sig')
        return df[df['type'].isin(['heliport', 'closed']) == False]
    
    def fetch_runways(self) -> pd.DataFrame:
        """Override to use local test files instead of downloading."""
        # Read directly from test files
        return pd.read_csv(self.runways_file, encoding='utf-8-sig')


class TestWorldAirportsSourceClass:
    """Test suite for WorldAirportsSource using local test files."""
    
    @pytest.fixture
    def temp_cache_dir(self):
        """Create a temporary cache directory for tests."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield temp_dir
    
    @pytest.fixture
    def world_airports_source(self, temp_cache_dir):
        """Create a WorldAirportsSource instance using test files."""
        return TestWorldAirportsSource(temp_cache_dir, 'test_airports.db')
    
    def test_fetch_airports(self, world_airports_source):
        """Test fetching airports data from test files."""
        df = world_airports_source.fetch_airports()
        
        assert isinstance(df, pd.DataFrame)
        assert len(df) > 0
        assert 'ident' in df.columns
        assert 'name' in df.columns
        assert 'type' in df.columns
        
        # Check that we have the expected test airports
        expected_airports = ['EBOS', 'EDSB', 'EGKB', 'EHRD', 'EKAH', 'ESMS', 
                           'LDPL', 'LEGE', 'LFAT', 'LFQA', 'LIMJ', 'LKKV', 
                           'LOWS', 'LSGS']
        actual_airports = df['ident'].tolist()
        for airport in expected_airports:
            assert airport in actual_airports
    
    def test_fetch_runways(self, world_airports_source):
        """Test fetching runways data from test files."""
        df = world_airports_source.fetch_runways()
        
        assert isinstance(df, pd.DataFrame)
        assert len(df) > 0
        assert 'airport_ident' in df.columns
        assert 'length_ft' in df.columns
        assert 'surface' in df.columns
        
        # Check that we have runways for test airports
        expected_airports = ['EBOS', 'EDSB', 'EGKB', 'EHRD', 'EKAH', 'ESMS', 
                           'LDPL', 'LEGE', 'LFAT', 'LFQA', 'LIMJ', 'LKKV', 
                           'LOWS', 'LSGS']
        actual_airports = df['airport_ident'].unique().tolist()
        for airport in expected_airports:
            assert airport in actual_airports
    
    def test_get_airports(self, world_airports_source):
        """Test getting airports data with caching."""
        df = world_airports_source.get_airports()
        
        assert isinstance(df, pd.DataFrame)
        assert len(df) > 0
        assert 'ident' in df.columns
        
        # Test that filtering works (exclude heliports and closed airports)
        assert not df['type'].isin(['heliport', 'closed']).any()
    
    def test_get_runways(self, world_airports_source):
        """Test getting runways data with caching."""
        df = world_airports_source.get_runways()
        
        assert isinstance(df, pd.DataFrame)
        assert len(df) > 0
        assert 'airport_ident' in df.columns
    
    def test_fetch_airport_database(self, world_airports_source):
        """Test creating the SQLite database from test files."""
        metadata = world_airports_source.fetch_airport_database()
        
        assert isinstance(metadata, dict)
        assert 'database' in metadata
        assert 'tables' in metadata
        assert len(metadata['tables']) == 4  # airports, runways, surface_types, eu_airports_runway_summary
        
        # Check that database file was created
        db_path = Path(world_airports_source.database)
        assert db_path.exists()
        
        # Check table metadata
        table_names = [table['name'] for table in metadata['tables']]
        assert 'airports' in table_names
        assert 'runways' in table_names
        assert 'surface_types' in table_names
        assert 'eu_airports_runway_summary' in table_names
    
    def test_get_airport_summary(self, world_airports_source):
        """Test getting airport summary data."""
        summaries = world_airports_source.get_airport_summary()
        
        assert isinstance(summaries, list)
        assert len(summaries) > 0
        
        # Check structure of summary data
        if summaries:
            summary = summaries[0]
            assert 'ident' in summary
            assert 'length_ft' in summary
            assert 'surface_type' in summary
            assert 'surface' in summary
            assert 'hard' in summary
            assert 'soft' in summary
            assert 'water' in summary
            assert 'snow' in summary
    
    def test_update_model(self, world_airports_source):
        """Test updating EuroAipModel with WorldAirports data."""
        model = EuroAipModel()
        
        # Update model with all airports
        world_airports_source.update_model(model)
        
        # Check that airports were added
        assert len(model.airports) > 0
        
        # Check specific test airports
        expected_airports = ['EBOS', 'EDSB', 'EGKB', 'EHRD', 'EKAH', 'ESMS', 
                           'LDPL', 'LEGE', 'LFAT', 'LFQA', 'LIMJ', 'LKKV', 
                           'LOWS', 'LSGS']
        
        for airport_code in expected_airports:
            airport = model.get_airport(airport_code)
            assert airport is not None
            assert airport.ident == airport_code
            assert airport.name is not None
            assert airport.type is not None
            
            # Check that airport has source tracking
            assert 'WorldAirportsSource' in airport.sources
    
    def test_update_model_with_specific_airports(self, world_airports_source):
        """Test updating model with specific airports only."""
        model = EuroAipModel()
        specific_airports = ['EBOS', 'EGKB', 'EHRD']
        
        world_airports_source.update_model(model, airports=specific_airports)
        
        # Check that only specified airports were added
        assert len(model.airports) == len(specific_airports)
        
        for airport_code in specific_airports:
            airport = model.get_airport(airport_code)
            assert airport is not None
            assert airport.ident == airport_code
    
    def test_find_available_airports(self, world_airports_source):
        """Test finding all available airports."""
        airports = world_airports_source.find_available_airports()
        
        assert isinstance(airports, list)
        assert len(airports) > 0
        
        # Check that we have the expected test airports
        expected_airports = ['EBOS', 'EDSB', 'EGKB', 'EHRD', 'EKAH', 'ESMS', 
                           'LDPL', 'LEGE', 'LFAT', 'LFQA', 'LIMJ', 'LKKV', 
                           'LOWS', 'LSGS']
        
        for airport in expected_airports:
            assert airport in airports
    
    def test_airport_runway_relationships(self, world_airports_source):
        """Test that airports have proper runway relationships."""
        model = EuroAipModel()
        world_airports_source.update_model(model)
        
        # Check specific airports that should have runways
        test_cases = [
            ('EBOS', 2),  # EBOS has 2 runways
            ('EGKB', 2),  # EGKB has 2 runways
            ('EHRD', 1),  # EHRD has 1 runway
        ]
        
        for airport_code, expected_runway_count in test_cases:
            airport = model.get_airport(airport_code)
            assert airport is not None
            assert len(airport.runways) == expected_runway_count
            
            # Check runway properties
            for runway in airport.runways:
                assert runway.airport_ident == airport_code
                assert runway.length_ft is not None or runway.length_ft == 0
                assert runway.surface is not None
    
    def test_surface_type_classification(self, world_airports_source):
        """Test that surface types are properly classified."""
        model = EuroAipModel()
        world_airports_source.update_model(model)
        
        # Check specific surface types from test data
        surface_tests = [
            ('EBOS', 'CONCRETE'),  # Should be classified as 'hard'
            ('EGKB', 'ASP'),       # Should be classified as 'hard'
            ('LSGS', 'GRS'),       # Should be classified as 'soft'
        ]
        
        for airport_code, expected_surface in surface_tests:
            airport = model.get_airport(airport_code)
            assert airport is not None
            
            # Find runway with expected surface
            matching_runways = [r for r in airport.runways if r.surface == expected_surface]
            assert len(matching_runways) > 0
    
    def test_error_handling(self, world_airports_source):
        """Test error handling in update_model."""
        model = EuroAipModel()
        
        # This should not raise an exception even if there are issues with individual airports
        world_airports_source.update_model(model)
        
        # Should still have some airports even if some failed
        assert len(model.airports) > 0 