"""
Tests for runway surface classification utilities.
"""

import pytest
from euro_aip.utils.runway_classifier import (
    classify_runway_surface,
    is_hard_surface,
    is_soft_surface,
    is_water_surface,
    is_snow_surface,
    get_surface_statistics
)


class TestRunwayClassifier:
    """Test cases for runway surface classification."""
    
    def test_hard_surfaces(self):
        """Test classification of hard surfaces."""
        hard_surfaces = [
            'ASP', 'CON', 'PEM', 'TAR', 'ASPHALT', 'CONCRETE', 'CEMENT',
            'asphalt', 'concrete', 'paved', 'tarmac', 'asfalt'
        ]
        
        for surface in hard_surfaces:
            assert classify_runway_surface(surface) == 'hard'
            assert is_hard_surface(surface) is True
            assert is_soft_surface(surface) is False
            assert is_water_surface(surface) is False
            assert is_snow_surface(surface) is False
    
    def test_soft_surfaces(self):
        """Test classification of soft surfaces."""
        soft_surfaces = [
            'GRASS', 'TURF', 'DIRT', 'GRAVEL', 'SOIL', 'SAND', 'EARTH',
            'grass', 'turf', 'dirt', 'gravel', 'soil', 'sand', 'earth',
            'GRV', 'GRA', 'GRE', 'SAN', 'CLA'
        ]
        
        for surface in soft_surfaces:
            assert classify_runway_surface(surface) == 'soft'
            assert is_soft_surface(surface) is True
            assert is_hard_surface(surface) is False
            assert is_water_surface(surface) is False
            assert is_snow_surface(surface) is False
    
    def test_water_surfaces(self):
        """Test classification of water surfaces."""
        water_surfaces = ['WATER', 'water', 'WAT', 'wat']
        
        for surface in water_surfaces:
            assert classify_runway_surface(surface) == 'water'
            assert is_water_surface(surface) is True
            assert is_hard_surface(surface) is False
            assert is_soft_surface(surface) is False
            assert is_snow_surface(surface) is False
    
    def test_snow_surfaces(self):
        """Test classification of snow surfaces."""
        snow_surfaces = ['SNOW', 'snow', 'SNO', 'sno']
        
        for surface in snow_surfaces:
            assert classify_runway_surface(surface) == 'snow'
            assert is_snow_surface(surface) is True
            assert is_hard_surface(surface) is False
            assert is_soft_surface(surface) is False
            assert is_water_surface(surface) is False
    
    def test_unknown_surfaces(self):
        """Test handling of unknown surface types."""
        unknown_surfaces = ['UNKNOWN', 'xyz', '123', '', None]
        
        for surface in unknown_surfaces:
            assert classify_runway_surface(surface) is None
            assert is_hard_surface(surface) is False
            assert is_soft_surface(surface) is False
            assert is_water_surface(surface) is False
            assert is_snow_surface(surface) is False
    
    def test_surface_statistics(self):
        """Test surface statistics calculation."""
        surfaces = ['ASP', 'GRASS', 'WATER', 'SNOW', 'UNKNOWN', None]
        stats = get_surface_statistics(surfaces)
        
        assert stats['hard'] == 1
        assert stats['soft'] == 1
        assert stats['water'] == 1
        assert stats['snow'] == 1
        assert stats['unknown'] == 2  # 'UNKNOWN' and None
        assert stats['total'] == 6
    
    def test_case_insensitive_matching(self):
        """Test that matching is case insensitive."""
        assert classify_runway_surface('asphalt') == 'hard'
        assert classify_runway_surface('ASPHALT') == 'hard'
        assert classify_runway_surface('Asphalt') == 'hard'
        
        assert classify_runway_surface('grass') == 'soft'
        assert classify_runway_surface('GRASS') == 'soft'
        assert classify_runway_surface('Grass') == 'soft'
    
    def test_whitespace_handling(self):
        """Test that whitespace is properly handled."""
        assert classify_runway_surface('  ASP  ') == 'hard'
        assert classify_runway_surface('  grass  ') == 'soft'
        assert classify_runway_surface('  water  ') == 'water'
        assert classify_runway_surface('  snow  ') == 'snow' 