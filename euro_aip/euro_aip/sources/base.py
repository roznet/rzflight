from abc import ABC, abstractmethod
from typing import List, Optional
from ..models.euro_aip_model import EuroAipModel

class SourceInterface(ABC):
    """
    Base interface for all data sources.
    
    This interface defines the contract that all sources must implement
    to be compatible with the EuroAipModel architecture.
    """
    
    @abstractmethod
    def update_model(self, model: EuroAipModel, airports: Optional[List[str]] = None) -> None:
        """
        Update the EuroAipModel with data from this source.
        
        This is the main method that each source must implement. It should:
        1. Determine which airports to process (from airports parameter or find_available_airports)
        2. Collect data for each airport from this source
        3. Create or update Airport objects with the collected data
        4. Add the Airport objects to the model
        
        Args:
            model: The EuroAipModel to update
            airports: Optional list of specific airports to process. If None, 
                     the source should process all available airports.
        """
        pass
    
    def find_available_airports(self) -> List[str]:
        """
        Find all available airports that this source can process.
        
        This method should return a list of ICAO airport codes that this source
        has data for. Sources that cannot discover available airports should
        return an empty list.
        
        Returns:
            List of ICAO airport codes available in this source
        """
        return []
    
    def get_source_name(self) -> str:
        """
        Get the name of this source.
        
        Returns:
            String identifier for this source
        """
        return self.__class__.__name__.lower() 