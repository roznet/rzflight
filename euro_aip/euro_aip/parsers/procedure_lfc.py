from typing import List, Dict, Any, Optional
from .procedure_default import DefaultProcedureParser
import re
class LFCProcedureParser(DefaultProcedureParser):
    """Parser for LFC (France) procedure names."""

    def __init__(self):
        super().__init__()
    
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
        
        # Use the default parser's implementation
        return super().parse(heading, icao) 
    
    def _cleanup_heading(self, heading: str, icao: str) -> str:
        """Clean up the procedure heading."""
        cleaned = super()._cleanup_heading(heading, icao)
        prefix = f"AD 2 {icao} IAC "
        if cleaned.startswith(prefix):
            cleaned = cleaned[len(prefix):]
        return cleaned