from typing import List, Optional
from datetime import datetime

from .core.models import Airport
from .storage.base import StorageInterface
from .sources.base import SourceInterface

class EuroAIP:
    """
    Main interface for the Euro AIP library.
    
    This class provides methods to interact with European AIP data,
    including retrieval, parsing, and storage of airport information.
    """
    
    def __init__(self, storage: StorageInterface, source: SourceInterface):
        """
        Initialize the Euro AIP interface.
        
        Args:
            storage: Storage backend for persisting data
            source: Data source for retrieving AIP information
        """
        self.storage = storage
        self.source = source

    def get_airport(self, icao: str, as_of: Optional[datetime] = None) -> Airport:
        """
        Get airport data as of a specific date.
        
        Args:
            icao: ICAO airport code
            as_of: Optional datetime to get historical data
            
        Returns:
            Airport object containing the requested data
        """
        return self.storage.get_airport(icao, as_of)

    def update_airport(self, icao: str) -> None:
        """
        Update airport data from the configured source.
        
        Args:
            icao: ICAO airport code to update
        """
        raw_data = self.source.get_airport_data(icao)
        airport = self.parser.parse(raw_data)
        self.storage.save_airport(airport) 