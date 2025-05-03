from typing import List, Dict, Any, Optional
import re
from .procedure import ProcedureParser
from .procedure_factory import DEFAULT_AUTHORITY

class DefaultProcedureParser(ProcedureParser):
    """Default parser for procedure names."""
    
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
        self.runway_pattern = re.compile(r'\s+([0-3][0-9])([RLC])?')
    
    def get_supported_authorities(self) -> List[str]:
        """Get list of supported authority codes."""
        return [DEFAULT_AUTHORITY]
    
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
    
    def _parse_procedure_name(self, name: str, icao: str) -> Dict[str, Any]:
        """
        Parse a cleaned procedure name into structured data.
        
        Args:
            name: Cleaned procedure name
            icao: ICAO airport code
            
        Returns:
            Dictionary containing parsed procedure data
        """
        # First try to identify the approach type
        approach_types = ['ILS', 'RNAV', 'RNP', 'LOC', 'VOR', 'NDB']
        approach_type = None
        for type_name in approach_types:
            if type_name in name:
                approach_type = type_name
                break
                
        # Then look for runway number
        runway_match = self.runway_pattern.search(name)
        
        if runway_match:
            runway_number = runway_match.group(1)
            runway_letter = runway_match.group(2) if runway_match.group(2) else None
        else:
            runway_number = None
            runway_letter = None
            
        return {
            'icao': icao,
            'name': name,
            'type': 'approach',  # Default to approach since we filter for these
            'raw_name': name,
            'approach_type': approach_type,
            'runway_number': runway_number,
            'runway_letter': runway_letter
        }