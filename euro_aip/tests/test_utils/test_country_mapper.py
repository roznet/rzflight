"""
Tests for the country mapper utility.
"""

import pytest
from euro_aip.utils.country_mapper import CountryMapper


class TestCountryMapper:
    """Test cases for the CountryMapper class."""
    
    @pytest.fixture
    def mapper(self):
        """Create a CountryMapper instance for testing."""
        return CountryMapper()
    
    def test_get_iso_code_basic(self, mapper):
        """Test basic ISO code lookup."""
        test_cases = [
            ("FRANCE", "FR"),
            ("GERMANY", "DE"),
            ("ITALY", "IT"),
            ("SPAIN", "ES"),
            ("UNITED KINGDOM", "GB"),
            ("UK", "GB"),
        ]
        
        for country_name, expected_iso in test_cases:
            result = mapper.get_iso_code(country_name)
            assert result == expected_iso, f"Expected {expected_iso} for {country_name}, got {result}"
    
    def test_get_iso_code_case_insensitive(self, mapper):
        """Test case insensitive ISO code lookup."""
        test_cases = [
            ("france", "FR"),
            ("germany", "DE"),
            ("italy", "IT"),
        ]
        
        for country_name, expected_iso in test_cases:
            result = mapper.get_iso_code(country_name)
            assert result == expected_iso, f"Expected {expected_iso} for {country_name}, got {result}"
    
    def test_get_iso_code_not_found(self, mapper):
        """Test ISO code lookup for unknown countries."""
        test_cases = [
            "UNKNOWN_COUNTRY",
            "",
            None,
            "XYZ",
        ]
        
        for country_name in test_cases:
            result = mapper.get_iso_code(country_name)
            assert result is None, f"Expected None for {country_name}, got {result}"
    
    def test_get_country_name(self, mapper):
        """Test country name lookup from ISO code."""
        test_cases = [
            ("FR", "FRANCE"),
            ("DE", "GERMANY"),
            ("IT", "ITALY"),
            ("GB", "UK"),  # The implementation returns UK for GB
        ]
        
        for iso_code, expected_name in test_cases:
            result = mapper.get_country_name(iso_code)
            assert result == expected_name, f"Expected {expected_name} for {iso_code}, got {result}"
    
    def test_get_country_name_not_found(self, mapper):
        """Test country name lookup for unknown ISO codes."""
        test_cases = [
            "XX",
            "",
            None,
            "XYZ",
        ]
        
        for iso_code in test_cases:
            result = mapper.get_country_name(iso_code)
            assert result is None, f"Expected None for {iso_code}, got {result}"
    
    def test_get_all_countries(self, mapper):
        """Test getting all country mappings."""
        countries = mapper.get_all_countries()
        
        # Should have all the countries we defined
        assert len(countries) > 0
        assert "FRANCE" in countries
        assert "GERMANY" in countries
        assert "UNITED KINGDOM" in countries
        assert countries["FRANCE"] == "FR"
        assert countries["GERMANY"] == "DE"
    
    def test_get_all_iso_codes(self, mapper):
        """Test getting all ISO codes."""
        iso_codes = mapper.get_all_iso_codes()
        
        # Should have all the ISO codes we defined
        assert len(iso_codes) > 0
        assert "FR" in iso_codes
        assert "DE" in iso_codes
        assert "GB" in iso_codes
    
    def test_is_valid_country(self, mapper):
        """Test country validation."""
        # Valid countries
        assert mapper.is_valid_country("FRANCE") is True
        assert mapper.is_valid_country("GERMANY") is True
        assert mapper.is_valid_country("UK") is True
        
        # Invalid countries
        assert mapper.is_valid_country("UNKNOWN") is False
        assert mapper.is_valid_country("") is False
        assert mapper.is_valid_country(None) is False 