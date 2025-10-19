"""
AIRAC date calculation utilities.

This module provides functionality to calculate AIRAC (Aeronautical Information Regulation and Control)
dates, which follow a 28-day cycle and always fall on Thursdays.
"""

import logging
from datetime import datetime, timedelta
from typing import Optional, List, Union

logger = logging.getLogger(__name__)

class AIRACDateCalculator:
    """
    Utility for calculating AIRAC dates based on the 28-day cycle.
    
    AIRAC dates follow a predictable pattern:
    - 28-day cycle
    - Always fall on Thursdays
    - Can be calculated from any known AIRAC date
    """
    
    # AIRAC cycle length in days
    AIRAC_CYCLE_DAYS = 28
    
    # Thursday weekday number (Monday=0, Tuesday=1, ..., Thursday=3)
    THURSDAY_WEEKDAY = 3
    
    def __init__(self, reference_airac_date: str = '2025-10-02'):
        """
        Initialize the AIRAC date calculator with a reference date.
        
        Args:
            reference_airac_date: Known AIRAC date in YYYY-MM-DD format (defaults to 2025-10-02)
            
        Raises:
            ValueError: If the reference date is invalid or not a Thursday
        """
        self.reference_date = self._parse_date(reference_airac_date)
        self._validate_reference_date()
        
    def _parse_date(self, date_str: str) -> datetime:
        """Parse a date string in YYYY-MM-DD format."""
        try:
            return datetime.strptime(date_str, '%Y-%m-%d')
        except ValueError:
            raise ValueError(f"Invalid date format: {date_str}. Expected YYYY-MM-DD")
    
    def _validate_reference_date(self) -> None:
        """Validate that the reference date is a Thursday (AIRAC dates always fall on Thursdays)."""
        if self.reference_date.weekday() != self.THURSDAY_WEEKDAY:
            raise ValueError(f"Reference AIRAC date must be a Thursday, but {self.reference_date.strftime('%Y-%m-%d')} is a {self.reference_date.strftime('%A')}")
    
    def next_airac_date(self, from_date: Optional[Union[str, datetime]] = None) -> str:
        """
        Get the next AIRAC date from a given date.
        
        Args:
            from_date: Date to calculate from (defaults to today). Can be string (YYYY-MM-DD) or datetime
            
        Returns:
            Next AIRAC date in YYYY-MM-DD format
        """
        if from_date is None:
            from_date = datetime.now()
        elif isinstance(from_date, str):
            from_date = self._parse_date(from_date)
            
        # Calculate days since reference date
        days_diff = (from_date - self.reference_date).days
        
        # Find the next AIRAC cycle
        cycles_since_ref = days_diff // self.AIRAC_CYCLE_DAYS
        if days_diff < 0:
            cycles_since_ref -= 1
        
        next_cycle = cycles_since_ref + 1
        next_airac = self.reference_date + timedelta(days=next_cycle * self.AIRAC_CYCLE_DAYS)
        
        return next_airac.strftime('%Y-%m-%d')
    
    def previous_airac_date(self, from_date: Optional[Union[str, datetime]] = None) -> str:
        """
        Get the previous AIRAC date from a given date.
        
        Args:
            from_date: Date to calculate from (defaults to today). Can be string (YYYY-MM-DD) or datetime
            
        Returns:
            Previous AIRAC date in YYYY-MM-DD format
        """
        if from_date is None:
            from_date = datetime.now()
        elif isinstance(from_date, str):
            from_date = self._parse_date(from_date)
            
        # Calculate days since reference date
        days_diff = (from_date - self.reference_date).days
        
        # Find the previous AIRAC cycle
        if days_diff < 0:
            cycles_since_ref = (days_diff // self.AIRAC_CYCLE_DAYS) - 1
        elif days_diff == 0:
            # If we're exactly on the reference date, previous is one cycle before
            cycles_since_ref = -1
        else:
            # If we're after the reference date, previous is reference cycle (0) unless we've passed the next cycle
            cycles_since_ref = (days_diff - 1) // self.AIRAC_CYCLE_DAYS
        
        prev_cycle = cycles_since_ref
        prev_airac = self.reference_date + timedelta(days=prev_cycle * self.AIRAC_CYCLE_DAYS)
        
        return prev_airac.strftime('%Y-%m-%d')
    
    def is_airac_date(self, date: Union[str, datetime]) -> bool:
        """
        Check if a given date is an AIRAC date.
        
        Args:
            date: Date to check. Can be string (YYYY-MM-DD) or datetime
            
        Returns:
            True if the date is an AIRAC date, False otherwise
        """
        if isinstance(date, str):
            date = self._parse_date(date)
            
        # Check if it's a Thursday
        if date.weekday() != self.THURSDAY_WEEKDAY:
            return False
            
        # Check if it's a multiple of 28 days from the reference
        days_diff = (date - self.reference_date).days
        return days_diff % self.AIRAC_CYCLE_DAYS == 0
    
    def get_airac_dates_range(self, start_date: Optional[Union[str, datetime]] = None, 
                            end_date: Optional[Union[str, datetime]] = None, 
                            count: Optional[int] = None) -> List[str]:
        """
        Get a range of AIRAC dates.
        
        Args:
            start_date: Starting date (defaults to today). Can be string (YYYY-MM-DD) or datetime
            end_date: Ending date. Can be string (YYYY-MM-DD) or datetime
            count: Number of dates to return (alternative to end_date)
            
        Returns:
            List of AIRAC dates in YYYY-MM-DD format
            
        Raises:
            ValueError: If both end_date and count are provided, or neither is provided
        """
        if (end_date is None and count is None) or (end_date is not None and count is not None):
            raise ValueError("Either end_date or count must be provided, but not both")
            
        if start_date is None:
            start_date = datetime.now()
        elif isinstance(start_date, str):
            start_date = self._parse_date(start_date)
            
        dates = []
        
        # Find the first AIRAC date (either start_date if it's an AIRAC date, or next one)
        if self.is_airac_date(start_date):
            current = start_date
        else:
            current = self._parse_date(self.next_airac_date(start_date))
        
        if count is not None:
            # Generate count number of dates
            for _ in range(count):
                dates.append(current.strftime('%Y-%m-%d'))
                current += timedelta(days=self.AIRAC_CYCLE_DAYS)
        else:
            # Generate dates until end_date
            if isinstance(end_date, str):
                end_date = self._parse_date(end_date)
                
            while current <= end_date:
                dates.append(current.strftime('%Y-%m-%d'))
                current += timedelta(days=self.AIRAC_CYCLE_DAYS)
        
        return dates
    
    def days_until_next_airac(self, from_date: Optional[Union[str, datetime]] = None) -> int:
        """
        Calculate the number of days until the next AIRAC date.
        
        Args:
            from_date: Date to calculate from (defaults to today). Can be string (YYYY-MM-DD) or datetime
            
        Returns:
            Number of days until the next AIRAC date
        """
        if from_date is None:
            from_date = datetime.now()
        elif isinstance(from_date, str):
            from_date = self._parse_date(from_date)
            
        next_airac = self._parse_date(self.next_airac_date(from_date))
        return (next_airac - from_date).days
    
    def days_since_previous_airac(self, from_date: Optional[Union[str, datetime]] = None) -> int:
        """
        Calculate the number of days since the previous AIRAC date.
        
        Args:
            from_date: Date to calculate from (defaults to today). Can be string (YYYY-MM-DD) or datetime
            
        Returns:
            Number of days since the previous AIRAC date
        """
        if from_date is None:
            from_date = datetime.now()
        elif isinstance(from_date, str):
            from_date = self._parse_date(from_date)
            
        prev_airac = self._parse_date(self.previous_airac_date(from_date))
        return (from_date - prev_airac).days
    
    def get_current_airac_date(self, from_date: Optional[Union[str, datetime]] = None) -> str:
        """
        Get the current effective AIRAC date (the most recent AIRAC date not in the future).
        
        Args:
            from_date: Date to calculate from (defaults to today). Can be string (YYYY-MM-DD) or datetime
            
        Returns:
            Current effective AIRAC date in YYYY-MM-DD format
        """
        if from_date is None:
            from_date = datetime.now()
        elif isinstance(from_date, str):
            from_date = self._parse_date(from_date)
            
        # Get the previous AIRAC date (current effective one)
        return self.previous_airac_date(from_date)
    
    def get_reference_date(self) -> str:
        """Get the reference AIRAC date used for calculations."""
        return self.reference_date.strftime('%Y-%m-%d')


# Convenience functions for common operations
def is_airac_date(date: Union[str, datetime], reference_date: str = '2025-10-02') -> bool:
    """
    Check if a date is an AIRAC date using a default reference.
    
    Args:
        date: Date to check
        reference_date: Reference AIRAC date
        
    Returns:
        True if the date is an AIRAC date
    """
    calculator = AIRACDateCalculator(reference_date)
    return calculator.is_airac_date(date)


def get_next_airac_date(from_date: Optional[Union[str, datetime]] = None, 
                       reference_date: str = '2025-10-02') -> str:
    """
    Get the next AIRAC date using a default reference.
    
    Args:
        from_date: Date to calculate from (defaults to today)
        reference_date: Reference AIRAC date
        
    Returns:
        Next AIRAC date in YYYY-MM-DD format
    """
    calculator = AIRACDateCalculator(reference_date)
    return calculator.next_airac_date(from_date)


