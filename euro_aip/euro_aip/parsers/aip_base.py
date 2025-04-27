from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional
from pathlib import Path
import camelot.io as camelot
import tempfile
from pdfminer.high_level import extract_text
import pandas as pd

class AIPParser(ABC):
    """Base interface for AIP document parsers."""

    def _pdf_to_tables(self, pdf_data: bytes) -> List[pd.DataFrame]:
        # Create a temporary file to store the PDF
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as temp_file:
            temp_file.write(pdf_data)
            temp_file.flush()
            
            # Parse the PDF
            tables = camelot.read_pdf(temp_file.name, pages='1-2', 
                                        flavor='stream',
                                        row_tol=12,
                                        )
        return tables

    def _pdf_to_text(self, pdf_data: bytes) -> str:
        """
        Convert PDF data to text, separating Spanish and English columns.
        
        Args:
            pdf_data: Raw PDF data
            
        Returns:
            Text content of the PDF
        """
        # Create a BytesIO object from the PDF data
        pdf_file = BytesIO(pdf_data)
        
        # Extract text from PDF
        text = extract_text(pdf_file)
        return text
    
    @abstractmethod
    def parse(self, pdf_data: bytes, icao: str) -> List[Dict[str, Any]]:
        """
        Parse AIP document data.
        
        Args:
            pdf_data: Raw PDF data
            icao: ICAO airport code
            
        Returns:
            List of dictionaries containing parsed data
        """
        pass

    @abstractmethod
    def get_supported_authorities(self) -> List[str]:
        """
        Get list of supported authority codes.
        
        Returns:
            List of authority codes (e.g., ['LEC', 'LIC'])
        """
        pass 