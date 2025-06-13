from typing import List, Dict, Any, Optional
from .aip_default import DefaultAIPParser

class EBCAIPParser(DefaultAIPParser):
    """Parser for Belgium (EBC) AIP documents."""
    
    PREFERRED_PARSER = 'pdfplumber'  # Use pdfplumber for better table extraction
    
    # Custom table settings for Belgian AIP documents
    TABLE_SETTINGS = {
        'vertical_strategy': 'lines',  # Use lines for vertical detection
        'horizontal_strategy': 'lines',  # Use lines for horizontal detection
        'snap_tolerance': 5,  # More lenient line snapping
        'join_tolerance': 3,  # Standard text joining
        'edge_min_length': 2,  # Consider shorter lines
        'min_words_vertical': 2,  # Fewer words needed for vertical lines
        'min_words_horizontal': 1  # Standard horizontal word requirement
    }
    
    def get_supported_authorities(self) -> List[str]:
        """Get list of supported authority codes."""
        return ['EBC']
    
    def parse(self, pdf_data: bytes, icao: str) -> List[Dict[str, Any]]:
        """
        Parse Belgium AIP document data.
        
        Args:
            pdf_data: Raw PDF data
            icao: ICAO airport code
            
        Returns:
            List of dictionaries containing parsed data
        """
        # Use the default parser's implementation
        return super().parse(pdf_data, icao) 