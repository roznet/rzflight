#!/usr/bin/env python3

import pytest
import tempfile
import shutil
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

from euro_aip.storage import DatabaseStorage
from euro_aip.models import EuroAipModel


class TestAIPExportIntegration:
    """Test aipexport.py integration with DatabaseStorage."""
    
    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for test files."""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        # Cleanup
        shutil.rmtree(temp_dir, ignore_errors=True)
    
    @pytest.fixture
    def test_csv_files(self, temp_dir):
        """Set up test CSV files for WorldAirports source."""
        # Copy test CSV files
        test_csv_dir = Path(__file__).parent.parent / 'assets' / 'csv'
        cache_dir = Path(temp_dir) / 'cache' / 'worldairports'
        cache_dir.mkdir(parents=True, exist_ok=True)
        
        shutil.copy(test_csv_dir / 'airports_test.csv', cache_dir / 'airports.csv')
        shutil.copy(test_csv_dir / 'runways_test.csv', cache_dir / 'runways.csv')
        
        return temp_dir
    
    def test_aipexport_with_database_storage(self, test_csv_files):
        """Test aipexport.py with the new DatabaseStorage option."""
        # Create temporary output files
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name
        
        try:
            # Run aipexport.py with WorldAirports source and DatabaseStorage
            cmd = [
                sys.executable, 'example/aipexport.py',
                'EBOS', 'EGKB',  # Specific airports
                '--worldairports',
                '--worldairports-db', 'test_airports.db',
                '--worldairports-filter', 'all',
                '--database-storage', db_path,
                '--cache-dir', str(Path(test_csv_files) / 'cache')
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, cwd=Path.cwd())
            
            # Check that the command succeeded
            assert result.returncode == 0, f"Command failed: {result.stderr}"
            
            # Verify the database was created and contains data
            storage = DatabaseStorage(db_path)
            db_info = storage.get_database_info()
            
            # Should have airports
            assert db_info['tables']['airports'] >= 2
            assert db_info['tables']['runways'] > 0
            
            # Load the model and verify data
            model = storage.load_model()
            assert 'EBOS' in model.airports
            assert 'EGKB' in model.airports
            
            ebos = model.airports['EBOS']
            assert ebos.name == 'Oostende-Brugge International Airport'
            assert 'worldairports' in ebos.sources
            
        finally:
            # Cleanup
            try:
                Path(db_path).unlink(missing_ok=True)
            except:
                pass
    
    def test_aipexport_multiple_sources(self, test_csv_files):
        """Test aipexport.py with multiple sources and DatabaseStorage."""
        # Create temporary output files
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name
        
        try:
            # Run aipexport.py with multiple sources
            cmd = [
                sys.executable, 'example/aipexport.py',
                'EBOS', 'EGKB',
                '--worldairports',
                '--worldairports-db', 'test_airports.db',
                '--worldairports-filter', 'all',
                '--database-storage', db_path,
                '--json', str(Path(test_csv_files) / 'output.json'),  # Also test JSON output
                '--cache-dir', str(Path(test_csv_files) / 'cache')
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, cwd=Path.cwd())
            
            # Check that the command succeeded
            assert result.returncode == 0, f"Command failed: {result.stderr}"
            
            # Verify both outputs were created
            assert Path(db_path).exists()
            assert Path(test_csv_files) / 'output.json' in Path(test_csv_files).iterdir()
            
            # Verify database content
            storage = DatabaseStorage(db_path)
            model = storage.load_model()
            assert len(model.airports) >= 2
            
        finally:
            # Cleanup
            try:
                Path(db_path).unlink(missing_ok=True)
            except:
                pass
    
    def test_aipexport_change_tracking(self, test_csv_files):
        """Test that aipexport.py properly tracks changes with DatabaseStorage."""
        # Create temporary output files
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name
        
        try:
            # First run - create initial data
            cmd1 = [
                sys.executable, 'example/aipexport.py',
                'EBOS',
                '--worldairports',
                '--worldairports-db', 'test_airports.db',
                '--worldairports-filter', 'all',
                '--database-storage', db_path,
                '--cache-dir', str(Path(test_csv_files) / 'cache')
            ]
            
            result1 = subprocess.run(cmd1, capture_output=True, text=True, cwd=Path.cwd())
            assert result1.returncode == 0
            
            # Second run - should detect no changes
            result2 = subprocess.run(cmd1, capture_output=True, text=True, cwd=Path.cwd())
            assert result2.returncode == 0
            
            # Verify change tracking
            storage = DatabaseStorage(db_path)
            changes = storage.get_changes_for_airport('EBOS', days=1)
            
            # Should have no changes when saving the same again
            assert len(changes['airport']) == 0
            
            # The second run with identical data should not create new changes
            # (this is tested by the fact that the command succeeds without errors)
            
        finally:
            # Cleanup
            try:
                Path(db_path).unlink(missing_ok=True)
            except:
                pass
    
    def test_aipexport_cli_help(self):
        """Test that aipexport.py help shows the new DatabaseStorage option."""
        cmd = [sys.executable, 'example/aipexport.py', '--help']
        
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=Path.cwd())
        
        assert result.returncode == 0
        assert '--database-storage' in result.stdout
        assert 'New unified database storage file with change tracking' in result.stdout
    

class TestAIPExportModelBuilder:
    """Test the ModelBuilder class from aipexport.py."""
    
    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for test files."""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        # Cleanup
        shutil.rmtree(temp_dir, ignore_errors=True)
    
    @pytest.fixture
    def test_csv_files(self, temp_dir):
        """Set up test CSV files for WorldAirports source."""
        # Copy test CSV files
        test_csv_dir = Path(__file__).parent.parent / 'assets' / 'csv'
        cache_dir = Path(temp_dir) / 'cache' / 'worldairports'
        cache_dir.mkdir(parents=True, exist_ok=True)
        
        shutil.copy(test_csv_dir / 'airports_test.csv', cache_dir / 'airports.csv')
        shutil.copy(test_csv_dir / 'runways_test.csv', cache_dir / 'runways.csv')
        
        return temp_dir
    
    def test_model_builder_with_worldairports(self, test_csv_files):
        """Test ModelBuilder with WorldAirports source."""
        # Import the ModelBuilder class
        sys.path.insert(0, str(Path.cwd() / 'example'))
        from aipexport import ModelBuilder
        
        # Create mock args
        args = MagicMock()
        args.worldairports = True
        args.worldairports_db = 'test_airports.db'
        args.worldairports_filter = 'all'
        args.cache_dir = str(Path(test_csv_files) / 'cache')
        args.france_eaip = None
        args.uk_eaip = None
        args.autorouter = False
        args.pointdepassage = False
        args.force_refresh = False
        args.never_refresh = False
        
        # Create ModelBuilder
        builder = ModelBuilder(args)
        
        # Build model with specific airports
        model = builder.build_model(['EBOS', 'EGKB'])
        
        # Verify model
        assert len(model.airports) >= 2
        assert 'EBOS' in model.airports
        assert 'EGKB' in model.airports
        
        ebos = model.airports['EBOS']
        assert ebos.name == 'Oostende-Brugge International Airport'
        assert 'worldairports' in ebos.sources
        
        # Verify runways
        assert len(ebos.runways) > 0
    
    def test_model_builder_get_all_airports(self, test_csv_files):
        """Test ModelBuilder.get_all_airports method."""
        # Import the ModelBuilder class
        sys.path.insert(0, str(Path.cwd() / 'example'))
        from aipexport import ModelBuilder
        
        # Create mock args
        args = MagicMock()
        args.worldairports = True
        args.worldairports_db = 'test_airports.db'
        args.worldairports_filter = 'all'
        args.cache_dir = str(Path(test_csv_files) / 'cache')
        args.france_eaip = None
        args.uk_eaip = None
        args.autorouter = False
        args.pointdepassage = False
        args.force_refresh = False
        args.never_refresh = False
        
        # Create ModelBuilder
        builder = ModelBuilder(args)
        
        # Get all airports
        airports = builder.get_all_airports()
        
        # Should return airports from test data
        assert len(airports) > 0
        assert 'EBOS' in airports
        assert 'EGKB' in airports
        assert 'EHRD' in airports 