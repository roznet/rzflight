from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
import re

class ProcedureParser(ABC):
    """Base class for procedure parsers."""
    
    def __init__(self):
        # Common regex patterns for procedure names
        self.skip_patterns = [
            'CODING TABLE',
            'INSTRUMENT APPROACH PROCEDURE', 
            'APPENDIX',
            'TRANSITION',
            'APPROACH TERRAIN CHART',
            'INITIAL APPROACH PROCEDURE'
        ]
        self.valid_patterns = ['APPROACH CHART', ' IAC ', ' IAC/']
        self.cleanup_patterns = [
            r'.*(INSTRUMENT APPROACH CHART| IAC[ /])[- ]*',
            r'[- ]*ICAO[- ]*'
        ]
    
    @abstractmethod
    def get_supported_authorities(self) -> List[str]:
        """Get list of supported authority codes."""
        pass
    
    def parse(self, heading: str, icao: str) -> Optional[Dict[str, Any]]:
        """
        Parse a procedure heading into structured data.
        
        Args:
            heading: Procedure heading text
            icao: ICAO airport code
            
        Returns:
            Dictionary containing parsed procedure data or None if invalid
        """
        # Check if this is a valid approach procedure
        if not self._is_valid_procedure(heading):
            return None
            
        # Clean up the heading
        name = self._cleanup_heading(heading)
        
        # Parse the procedure name
        return self._parse_procedure_name(name, icao)
    
    def _is_valid_procedure(self, heading: str) -> bool:
        """Check if the heading represents a valid approach procedure."""
        heading_upper = heading.upper()
        
        # Check if it matches any valid patterns
        is_valid = any(pattern in heading_upper for pattern in self.valid_patterns)
        if not is_valid:
            return False
            
        # Check if it matches any skip patterns
        is_skip = any(pattern in heading_upper for pattern in self.skip_patterns)
        if is_skip:
            return False
            
        return True
    
    def _cleanup_heading(self, heading: str) -> str:
        """Clean up the procedure heading."""
        name = heading.upper()
        for pattern in self.cleanup_patterns:
            name = re.sub(pattern, '', name)
        return name.strip()
    
    @abstractmethod
    def _parse_procedure_name(self, name: str, icao: str) -> Dict[str, Any]:
        """
        Parse a cleaned procedure name into structured data.
        
        Args:
            name: Cleaned procedure name
            icao: ICAO airport code
            
        Returns:
            Dictionary containing parsed procedure data
        """
        pass 