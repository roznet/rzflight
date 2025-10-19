"""
Tests for AIRAC date calculation utilities.
"""

import pytest
from datetime import datetime, timedelta
from euro_aip.utils.airac_date_calculator import (
    AIRACDateCalculator,
    is_airac_date,
    get_next_airac_date
)


class TestAIRACDateCalculator:
    """Test cases for AIRAC date calculation."""
    
    def setup_method(self):
        """Set up test fixtures."""
        # Use October 2, 2025 as reference (known AIRAC date - Thursday)
        self.calculator = AIRACDateCalculator('2025-10-02')
    
    def test_initialization_with_valid_date(self):
        """Test initialization with a valid AIRAC date."""
        calc = AIRACDateCalculator('2025-10-02')
        assert calc.get_reference_date() == '2025-10-02'
    
    def test_initialization_with_invalid_date_format(self):
        """Test initialization with invalid date format."""
        with pytest.raises(ValueError, match="Invalid date format"):
            AIRACDateCalculator('2025/10/02')
    
    def test_initialization_with_non_thursday(self):
        """Test initialization with a date that's not a Thursday."""
        with pytest.raises(ValueError, match="must be a Thursday"):
            AIRACDateCalculator('2025-10-01')  # Wednesday
    
    def test_is_airac_date_valid_dates(self):
        """Test identification of valid AIRAC dates."""
        valid_airac_dates = [
            '2025-10-02',  # Reference date (Thursday)
            '2025-10-30',  # Next AIRAC (Thursday, +28 days)
            '2025-11-27',  # Next AIRAC (Thursday, +56 days)
            '2025-12-25',  # Next AIRAC (Thursday, +84 days)
        ]
        
        for date in valid_airac_dates:
            assert self.calculator.is_airac_date(date) is True
            assert is_airac_date(date) is True
    
    def test_is_airac_date_invalid_dates(self):
        """Test identification of invalid AIRAC dates."""
        invalid_dates = [
            '2025-10-01',  # Wednesday (not Thursday)
            '2025-10-03',  # Friday (not Thursday)
            '2025-10-09',  # Thursday but not multiple of 28 days
            '2025-10-16',  # Thursday but not multiple of 28 days
        ]
        
        for date in invalid_dates:
            assert self.calculator.is_airac_date(date) is False
            assert is_airac_date(date) is False
    
    def test_next_airac_date(self):
        """Test calculation of next AIRAC date."""
        # Test from a known date
        next_date = self.calculator.next_airac_date('2025-10-15')
        assert next_date == '2025-10-30'
        
        # Test from the reference date itself
        next_date = self.calculator.next_airac_date('2025-10-02')
        assert next_date == '2025-10-30'
        
        # Test from an AIRAC date
        next_date = self.calculator.next_airac_date('2025-10-30')
        assert next_date == '2025-11-27'
    
    def test_previous_airac_date(self):
        """Test calculation of previous AIRAC date."""
        # Test from a known date
        prev_date = self.calculator.previous_airac_date('2025-10-15')
        assert prev_date == '2025-10-02'
        
        # Test from the reference date itself
        prev_date = self.calculator.previous_airac_date('2025-10-02')
        assert prev_date == '2025-09-04'  # 28 days before
        
        # Test from an AIRAC date
        prev_date = self.calculator.previous_airac_date('2025-10-30')
        assert prev_date == '2025-10-02'
    
    def test_get_airac_dates_range_with_count(self):
        """Test getting a range of AIRAC dates with count."""
        dates = self.calculator.get_airac_dates_range(start_date='2025-10-15', count=5)
        expected = [
            '2025-10-30',
            '2025-11-27', 
            '2025-12-25',
            '2026-01-22',
            '2026-02-19'
        ]
        assert dates == expected
    
    def test_get_airac_dates_range_with_end_date(self):
        """Test getting a range of AIRAC dates with end date."""
        dates = self.calculator.get_airac_dates_range(
            start_date='2025-10-02',
            end_date='2025-12-31'
        )
        expected = ['2025-10-02', '2025-10-30', '2025-11-27', '2025-12-25']
        assert dates == expected
    
    def test_get_airac_dates_range_invalid_params(self):
        """Test range method with invalid parameters."""
        with pytest.raises(ValueError, match="Either end_date or count must be provided"):
            self.calculator.get_airac_dates_range()
        
        with pytest.raises(ValueError, match="Either end_date or count must be provided"):
            self.calculator.get_airac_dates_range(
                start_date='2025-10-02',
                end_date='2025-12-31',
                count=5
            )
    
    def test_days_until_next_airac(self):
        """Test calculation of days until next AIRAC."""
        # Test from reference date
        days = self.calculator.days_until_next_airac('2025-10-02')
        assert days == 28
        
        # Test from a date close to next AIRAC
        days = self.calculator.days_until_next_airac('2025-10-25')
        assert days == 5  # 5 days until Oct 30
    
    def test_days_since_previous_airac(self):
        """Test calculation of days since previous AIRAC."""
        # Test from reference date
        days = self.calculator.days_since_previous_airac('2025-10-02')
        assert days == 28  # 28 days since Sep 4
        
        # Test from a date close to reference
        days = self.calculator.days_since_previous_airac('2025-10-05')
        assert days == 3  # 3 days since Oct 2 (reference date)
    
    def test_get_current_airac_date(self):
        """Test getting current effective AIRAC date."""
        # Test from reference date
        current = self.calculator.get_current_airac_date('2025-10-02')
        assert current == '2025-09-04'  # Previous AIRAC
        
        # Test from a date after reference
        current = self.calculator.get_current_airac_date('2025-10-15')
        assert current == '2025-10-02'  # Reference date is current
    
    def test_convenience_functions(self):
        """Test convenience functions."""
        # Test get_next_airac_date
        next_date = get_next_airac_date('2025-10-15')
        assert next_date == '2025-10-30'
        
        # Test is_airac_date
        assert is_airac_date('2025-10-02') is True
        assert is_airac_date('2025-10-01') is False
    
    def test_datetime_input_support(self):
        """Test that datetime objects are supported as input."""
        test_date = datetime(2025, 10, 15)
        
        next_date = self.calculator.next_airac_date(test_date)
        assert next_date == '2025-10-30'
        
        prev_date = self.calculator.previous_airac_date(test_date)
        assert prev_date == '2025-10-02'
        
        is_airac = self.calculator.is_airac_date(datetime(2025, 10, 2))
        assert is_airac is True
    
    def test_default_reference_date(self):
        """Test that default reference date works."""
        calc = AIRACDateCalculator()  # Should use default reference date
        assert calc.get_reference_date() == '2025-10-02'
        
        # Test that it works correctly
        assert calc.is_airac_date('2025-10-30') is True
        assert calc.next_airac_date('2025-10-15') == '2025-10-30'
