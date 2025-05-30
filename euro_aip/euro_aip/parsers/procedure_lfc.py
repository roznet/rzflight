from typing import List, Dict, Any, Optional
from .procedure_default import DefaultProcedureParser
import re
class LFCProcedureParser(DefaultProcedureParser):
    """Parser for LFC (France) procedure names."""

    def __init__(self):
        super().__init__()
        self.runway_pattern = re.compile(r'RWY([0-3][0-9])([RLC])?')
    
    def get_supported_authorities(self) -> List[str]:
        """Get list of supported authority codes."""
        return ['LFC']
    
    def parse(self, heading: str, icao: str) -> Optional[Dict[str, Any]]:
        """
        Parse a procedure heading into structured data.
        
        Args:
            heading: Procedure heading text
            icao: ICAO airport code
            
        Returns:
            Dictionary containing parsed procedure data or None if invalid
        """
        # Replace underscores with spaces
        heading = heading.replace('_', ' ')
        
        # Use the default parser's implementation
        return super().parse(heading, icao) 