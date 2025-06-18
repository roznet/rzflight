import re
import logging
from typing import List, Dict, Any, Optional, Type
from pathlib import Path
from .aip_base import AIPParser
from .aip_default import DefaultAIPParser

logger = logging.getLogger(__name__)

class DualFormatAIPParser(AIPParser):
    """
    A parser that can handle both HTML and PDF formats for AIP documents.
    
    This parser automatically detects the format of the input data and delegates
    to the appropriate parser (HTML or PDF) based on the content.
    """
    
    def __init__(self, authority: str, html_parser: AIPParser, 
                 pdf_parser: AIPParser):
        """
        Initialize the dual format parser.
        
        Args:
            authority: Authority code (e.g., 'EGC', 'LFC', etc.)
            html_parser_class: HTML parser class to use (optional)
            pdf_parser_class: PDF parser class to use (optional)
        """
        self.authority = authority
        
        # Initialize HTML parser
        if html_parser:
            self.html_parser = html_parser
        else:
            # Default HTML parser (could be a generic one)
            self.html_parser = None
        
        # Initialize PDF parser
        if pdf_parser:
            self.pdf_parser = pdf_parser
        else:
            self.pdf_parser = None
        
    def get_supported_authorities(self) -> List[str]:
        """Get list of supported authority codes."""
        return [self.authority]
    
    def parse(self, data: bytes, icao: str) -> List[Dict[str, Any]]:
        """
        Parse AIP document data, automatically detecting format.
        
        Args:
            data: Raw document data (HTML or PDF)
            icao: ICAO airport code
            
        Returns:
            List of dictionaries containing parsed data
        """
        # Detect format based on content
        if self._is_pdf(data):
            logger.debug(f"Detected PDF format for {icao}, using PDF parser")
            if self.pdf_parser:
                return self.pdf_parser.parse(data, icao)
            else:
                logger.error(f"No PDF parser available for {icao}")
                return []
        elif self._is_html(data):
            logger.debug(f"Detected HTML format for {icao}, using HTML parser")
            if self.html_parser:
                return self.html_parser.parse(data, icao)
            else:
                logger.error(f"No HTML parser available for {icao}")
                return []
        else:
            logger.warning(f"Unknown format for {icao}, attempting PDF parsing")
            if self.pdf_parser:
                return self.pdf_parser.parse(data, icao)
            else:
                logger.error(f"No parser available for {icao}")
                return []
    
    def _is_html(self, data: bytes) -> bool:
        """
        Check if the data appears to be HTML.
        
        Args:
            data: Raw document data
            
        Returns:
            True if the data appears to be HTML
        """
        try:
            # Convert to string and check for HTML indicators
            content = data.decode('utf-8', errors='ignore').lower()
            
            # Check for HTML tags
            html_indicators = [
                '<html',
                '<!doctype html',
                '<head>',
                '<body>',
                '<div',
                '<table>',
                '<tr>',
                '<td>',
                '<th>'
            ]
            
            for indicator in html_indicators:
                if indicator in content:
                    return True
            
            # Check for specific UK eAIP patterns
            if 'egc' in content and 'ad-2' in content:
                return True
                
            return False
            
        except Exception as e:
            logger.debug(f"Error checking HTML format: {e}")
            return False
    
    def _is_pdf(self, data: bytes) -> bool:
        """
        Check if the data appears to be PDF.
        
        Args:
            data: Raw document data
            
        Returns:
            True if the data appears to be PDF
        """
        # Check for PDF magic number
        return data.startswith(b'%PDF') 