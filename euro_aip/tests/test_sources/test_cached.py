import pytest
from pathlib import Path
import json
import pandas as pd
from euro_aip.sources.cached import CachedSource

class MockSource(CachedSource):
    """Mock implementation of CachedSource for testing."""
    
    def fetch_test(self, param: str) -> dict:
        """Test fetch method that returns a simple dict."""
        return {'param': param, 'data': 'test'}

def test_cached_source_basic(test_cache_dir):
    """Test basic caching functionality."""
    source = MockSource(str(test_cache_dir))
    
    # First call should fetch
    result1 = source.get_data('test', 'json', 'param1')
    assert result1['param'] == 'param1'
    assert result1['data'] == 'test'
    
    # Second call should use cache
    result2 = source.get_data('test', 'json', 'param1')
    assert result2 == result1
    
    # Different param should fetch again
    result3 = source.get_data('test', 'json', 'param2')
    assert result3['param'] == 'param2'
    assert result3['data'] == 'test'

def test_cached_source_force_refresh(test_cache_dir):
    """Test force refresh functionality."""
    source = MockSource(str(test_cache_dir))
    
    # First call
    result1 = source.get_data('test', 'json', 'param1')
    
    # Force refresh
    source.set_force_refresh()
    result2 = source.get_data('test', 'json', 'param1')
    
    # Results should be equal but from different fetches
    assert result1 == result2 