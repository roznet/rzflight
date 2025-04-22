from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional
from pathlib import Path

class AIPParser(ABC):
    """Base interface for AIP document parsers."""
    
    @abstractmethod
    def parse(self, pdf_data: bytes, icao: str) -> List[Dict[str, Any]]:
        """
        Parse AIP document data.
        
        Args:
            pdf_data: Raw PDF data
            icao: ICAO airport code
            
        Returns:
            List of dictionaries containing parsed data
        """
        pass

    @abstractmethod
    def get_supported_authorities(self) -> List[str]:
        """
        Get list of supported authority codes.
        
        Returns:
            List of authority codes (e.g., ['LEC', 'LIC'])
        """
        pass 