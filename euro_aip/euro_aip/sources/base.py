from abc import ABC, abstractmethod
from typing import List, Optional
from ..models.euro_aip_model import EuroAipModel
import re

class SourceInterface(ABC):
    """
    Base interface for all data sources.

    This interface defines the contract that all sources must implement
    to be compatible with the EuroAipModel architecture.
    """

    def supported_icao_prefixes(self) -> List[str]:
        """
        Return list of ICAO prefixes this source can handle.

        Override in subclasses to restrict which airports this source processes.
        For example, France eAIP returns ['LF'], UK eAIP returns ['EG'].

        Returns:
            List of ICAO prefixes (e.g., ['LF', 'EG']) or empty list for all airports
        """
        return []

    def filter_airports(self, airports: Optional[List[str]]) -> Optional[List[str]]:
        """
        Filter airports to only those this source can handle.

        Args:
            airports: List of ICAO codes or None

        Returns:
            Filtered list or None if input was None
        """
        if airports is None:
            return None

        prefixes = self.supported_icao_prefixes()
        if not prefixes:
            return airports  # No filtering - source handles all airports

        filtered = [icao for icao in airports if any(icao.startswith(p) for p in prefixes)]
        return filtered

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
        Removes 'Source' suffix and returns the class name (minus suffix) as a single lowercase word, with no underscores.
        For example:
        - FranceEAIPSource -> franceeaip
        - UKEAIPSource -> ukeaip
        - AutorouterSource -> autorouter
        - WorldAirportsSource -> worldairports
        Returns:
            String identifier for this source
        """
        class_name = self.__class__.__name__.lower()
        if class_name.endswith('source'):
            class_name = class_name[:-6]
        return class_name