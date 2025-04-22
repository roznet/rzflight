from abc import ABC, abstractmethod
from datetime import datetime
from typing import List, Optional

from ..core.models import Airport, Runway, Procedure

class StorageInterface(ABC):
    """Base interface for storage backends."""
    
    @abstractmethod
    def get_airport(self, icao: str, as_of: Optional[datetime] = None) -> Airport:
        """
        Get airport data as of a specific date.
        
        Args:
            icao: ICAO airport code
            as_of: Optional datetime to get historical data
            
        Returns:
            Airport object containing the requested data
        """
        pass

    @abstractmethod
    def save_airport(self, airport: Airport) -> None:
        """
        Save airport data with versioning.
        
        Args:
            airport: Airport object to save
        """
        pass

    @abstractmethod
    def get_runways(self, airport_icao: str, as_of: Optional[datetime] = None) -> List[Runway]:
        """
        Get runway data as of a specific date.
        
        Args:
            airport_icao: ICAO airport code
            as_of: Optional datetime to get historical data
            
        Returns:
            List of Runway objects
        """
        pass

    @abstractmethod
    def save_runways(self, runways: List[Runway]) -> None:
        """
        Save runway data with versioning.
        
        Args:
            runways: List of Runway objects to save
        """
        pass 