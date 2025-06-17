from typing import List, Dict, Any, Optional
from .aip_default import DefaultAIPParser

class EKCAIPParser(DefaultAIPParser):
    """Parser for Danemark (EKC) AIP documents."""
    
    PREFERRED_PARSER = 'pdfplumber'  # Use pdfplumber for better table extraction
    
    # Custom table settings for Spanish AIP documents
    TABLE_SETTINGS = {
        'vertical_strategy': 'text',  # Use text positions for vertical lines
        'horizontal_strategy': 'text',  # Use text positions for horizontal lines
        'snap_tolerance': 3,  # Standard line snapping
        'join_tolerance': 5,  # More lenient text joining for Spanish documents
        'edge_min_length': 3,  # Standard edge length
        'min_words_vertical': 2,  # Fewer words needed for vertical lines
        'min_words_horizontal': 1  # Standard horizontal word requirement
    }
    
    def get_supported_authorities(self) -> List[str]:
        """Get list of supported authority codes."""
        return ['EKC']
    
    def parse(self, pdf_data: bytes, icao: str) -> List[Dict[str, Any]]:
        """
        Parse Spanish AIP document data.
        
        Args:
            pdf_data: Raw PDF data
            icao: ICAO airport code
            
        Returns:
            List of dictionaries containing parsed data
        """
        # Use the default parser's implementation
        return super().parse(pdf_data, icao) 