from typing import List, Dict, Any, Optional
from .procedure_default import DefaultProcedureParser
import re
class EGCProcedureParser(DefaultProcedureParser):
    """Parser for EGC (UK) procedure names."""

    def __init__(self):
        super().__init__()
        self.valid_patterns = [
            'RNP','ILS','VOR','NDB'
        ]
    
    def get_supported_authorities(self) -> List[str]:
        """Get list of supported authority codes."""
        return ['EGC']
    
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
    
