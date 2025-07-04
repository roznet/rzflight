"""
Tests for the airport name cleaner utility.
"""

import pytest
from euro_aip.utils.airport_name_cleaner import AirportNameCleaner


class TestAirportNameCleaner:
    """Test cases for the AirportNameCleaner class."""
    
    @pytest.fixture
    def cleaner(self):
        """Create an AirportNameCleaner instance for testing."""
        return AirportNameCleaner()
    
    def test_clean_name_basic(self, cleaner):
        """Test basic airport name cleaning."""
        test_cases = [
            ("London Heathrow Airport", "London Heathrow"),
            ("Paris Charles de Gaulle Airport", "Paris Charles de Gaulle"),
            ("Amsterdam Schiphol Airport", "Amsterdam Schiphol"),
            ("Frankfurt International Airport", "Frankfurt"),
            ("Munich Airport", "Munich"),
            ("Berlin Tegel Airport", "Berlin Tegel"),
        ]
        
        for input_name, expected_cleaned in test_cases:
            result = cleaner.clean_name(input_name)
            assert result == expected_cleaned, f"Expected '{expected_cleaned}' for '{input_name}', got '{result}'"
    
    def test_clean_name_case_insensitive(self, cleaner):
        """Test case insensitive cleaning."""
        test_cases = [
            ("london heathrow AIRPORT", "london heathrow"),
            ("PARIS CHARLES DE GAULLE airport", "PARIS CHARLES DE GAULLE"),
            ("Amsterdam SCHIPHOL Airport", "Amsterdam SCHIPHOL"),
        ]
        
        for input_name, expected_cleaned in test_cases:
            result = cleaner.clean_name(input_name)
            assert result == expected_cleaned, f"Expected '{expected_cleaned}' for '{input_name}', got '{result}'"
    
    def test_clean_name_no_changes(self, cleaner):
        """Test names that don't need cleaning."""
        test_cases = [
            "London Heathrow",
            "Paris Charles de Gaulle",
            "Amsterdam Schiphol",
            "Frankfurt",
            "Munich",
            "Berlin Tegel",
        ]
        
        for input_name in test_cases:
            result = cleaner.clean_name(input_name)
            assert result == input_name, f"Expected no change for '{input_name}', got '{result}'"
    
    def test_clean_name_edge_cases(self, cleaner):
        """Test edge cases for name cleaning."""
        test_cases = [
            ("", ""),
            (None, ""),
            ("Airport", ""),
            ("   Airport   ", ""),
            ("Airport Airport", ""),
            ("London Airport Airport", "London"),
        ]
        
        for input_name, expected_cleaned in test_cases:
            result = cleaner.clean_name(input_name)
            assert result == expected_cleaned, f"Expected '{expected_cleaned}' for '{input_name}', got '{result}'"
    
    def test_clean_name_aggressive(self, cleaner):
        """Test aggressive name cleaning."""
        test_cases = [
            ("London Heathrow Intl Airport", "London Heathrow"),
            ("Paris CDG Int Airport", "Paris CDG"),
            ("Amsterdam Schiphol Intl", "Amsterdam Schiphol"),
            ("Frankfurt Int Airport", "Frankfurt"),
        ]
        
        for input_name, expected_cleaned in test_cases:
            result = cleaner.clean_name_aggressive(input_name)
            assert result == expected_cleaned, f"Expected '{expected_cleaned}' for '{input_name}', got '{result}'"
    
    def test_get_cleaned_variants(self, cleaner):
        """Test getting multiple cleaned variants."""
        # Test with a name that has multiple variants
        variants = cleaner.get_cleaned_variants("London Heathrow International Airport")
        
        # Should have at least the original and cleaned versions
        assert len(variants) >= 2
        assert "London Heathrow International Airport" in variants
        assert "London Heathrow" in variants  # The aggressive cleaning removes "International"
        
        # Test with a name that doesn't need cleaning
        variants = cleaner.get_cleaned_variants("London Heathrow")
        assert len(variants) == 1
        assert "London Heathrow" in variants
    
    def test_clean_name_with_abbreviations(self, cleaner):
        """Test cleaning names with abbreviations."""
        test_cases = [
            ("London Heathrow Intl", "London Heathrow"),
            ("Paris CDG Int", "Paris CDG"),
            ("Amsterdam Schiphol Intl", "Amsterdam Schiphol"),
            ("Frankfurt Int", "Frankfurt"),
        ]
        
        for input_name, expected_cleaned in test_cases:
            result = cleaner.clean_name_aggressive(input_name)
            assert result == expected_cleaned, f"Expected '{expected_cleaned}' for '{input_name}', got '{result}'"
    
    def test_clean_name_with_multiple_words_to_remove(self, cleaner):
        """Test cleaning names with multiple words to remove."""
        test_cases = [
            ("London Heathrow International Airport", "London Heathrow"),
            ("Paris Charles de Gaulle International Airport", "Paris Charles de Gaulle"),
            ("Amsterdam Schiphol International Airport", "Amsterdam Schiphol"),
        ]
        
        for input_name, expected_cleaned in test_cases:
            result = cleaner.clean_name(input_name)
            assert result == expected_cleaned, f"Expected '{expected_cleaned}' for '{input_name}', got '{result}'" 