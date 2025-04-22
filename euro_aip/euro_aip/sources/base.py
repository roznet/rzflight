from abc import ABC, abstractmethod
from typing import List, Dict, Any

class SourceInterface(ABC):
    """Base interface for data sources."""
    
    @abstractmethod
    def get_airport_data(self, icao: str) -> Dict[str, Any]:
        """
        Get raw airport data from source.
        
        Args:
            icao: ICAO airport code
            
        Returns:
            Dictionary containing raw airport data
        """
        pass

    @abstractmethod
    def get_procedures(self, icao: str) -> List[Dict[str, Any]]:
        """
        Get raw procedures data from source.
        
        Args:
            icao: ICAO airport code
            
        Returns:
            List of dictionaries containing raw procedures data
        """
        pass 