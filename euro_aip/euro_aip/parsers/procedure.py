from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional

class ProcedureParser(ABC):
    """Base class for procedure parsers."""
    
    @abstractmethod
    def get_supported_authorities(self) -> List[str]:
        """Get list of supported authority codes."""
        pass
    
    @abstractmethod
    def parse(self, heading: str, icao: str) -> Optional[Dict[str, Any]]:
        """
        Parse a procedure heading into structured data.
        
        Args:
            heading: Procedure heading text
            icao: ICAO airport code
            
        Returns:
            Dictionary containing parsed procedure data or None if invalid
        """
        pass 