from typing import List, Dict, Any, Optional
from .aip_default import DefaultAIPParser

class LICAIPParser(DefaultAIPParser):
    """Parser for Italy (LIC) AIP documents."""

    FIELD_SEPARATOR = '\n'

    def get_supported_authorities(self) -> List[str]:
        """Get list of supported authority codes."""
        return ['LIC']
    
    def parse(self, pdf_data: bytes, icao: str) -> List[Dict[str, Any]]:
        # Use the default parser's implementation
        return super().parse(pdf_data, icao) 