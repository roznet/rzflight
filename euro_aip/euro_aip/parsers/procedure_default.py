from typing import List, Dict, Any
import re
from .procedure import ProcedureParser
from .procedure_factory import DEFAULT_AUTHORITY

class DefaultProcedureParser(ProcedureParser):
    """Default parser for procedure names."""
    
    def get_supported_authorities(self) -> List[str]:
        """Get list of supported authority codes."""
        return [DEFAULT_AUTHORITY]
    
    def _parse_procedure_name(self, name: str, icao: str) -> Dict[str, Any]:
        """
        Parse a cleaned procedure name into structured data.
        
        Args:
            name: Cleaned procedure name
            icao: ICAO airport code
            
        Returns:
            Dictionary containing parsed procedure data
        """
        # Basic parsing of procedure name
        # This can be enhanced based on specific needs
        return {
            'icao': icao,
            'name': name,
            'type': 'approach',  # Default to approach since we filter for these
            'raw_name': name
        } 