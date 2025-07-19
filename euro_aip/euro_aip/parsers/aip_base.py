from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, Literal
from pathlib import Path
import tempfile
import pandas as pd
from io import BytesIO
import logging

logger = logging.getLogger(__name__)

# Constants for authority codes
DEFAULT_AUTHORITY = 'DEFAULT'

# Define parser types
ParserType = Literal['camelot_stream', 'camelot_lattice', 'pdfplumber']

class AIPParser(ABC):
    """Base interface for AIP document parsers."""
    
    # Override this in subclasses to specify which parser to use
    PREFERRED_PARSER: ParserType = 'camelot_lattice'
    
    # Default table settings for pdfplumber
    TABLE_SETTINGS = {
        'vertical_strategy': 'lines',  # Use text positions for vertical lines
        'horizontal_strategy': 'lines',  # Use text positions for horizontal lines
        'snap_tolerance': 3,  # How close lines need to be to snap together
        'join_tolerance': 3,  # How close text needs to be to join
        'edge_min_length': 3,  # Minimum length of edges to consider
        'min_words_vertical': 3,  # Minimum words to consider a vertical line
        'min_words_horizontal': 1  # Minimum words to consider a horizontal line
    }

    def _extract_tables_camelot(self, temp_file: str, flavor: Literal['stream', 'lattice']) -> List[pd.DataFrame]:
        """Extract tables using Camelot with specified flavor."""
        logger.debug(f"Extracting tables with Camelot ({flavor})")
        import camelot.io as camelot
        tables = camelot.read_pdf(
            temp_file, 
            pages='1-3',
            flavor=flavor,
        )
        if tables:
            logger.debug(f"Successfully extracted {len(tables)} tables with Camelot ({flavor})")
            return [table.df for table in tables]
        return []

    def _extract_tables_pdfplumber(self, temp_file: str) -> List[pd.DataFrame]:
        """
        Extract tables using pdfplumber with configurable options.
        
        Args:
            temp_file: Path to the PDF file
            
        Returns:
            List of pandas DataFrames containing the tables
        """
        logger.debug("Extracting tables with pdfplumber")
        import pdfplumber
        tables = []
        with pdfplumber.open(temp_file) as pdf:
            # Process first two pages
            for page in pdf.pages[:2]:
                # Extract tables from the page with custom options
                page_tables = page.extract_tables(self.TABLE_SETTINGS)
                if page_tables:
                    # Convert each table to DataFrame
                    for table in page_tables:
                        if table and len(table) > 1:  # Ensure table has header and data
                            # Convert to DataFrame with RangeIndex for columns
                            df = pd.DataFrame(table)
                            # Rename columns to match Camelot's format (0, 1, 2, etc.)
                            df.columns = range(len(df.columns))
                            tables.append(df)
        if tables:
            logger.debug(f"Successfully extracted {len(tables)} tables with pdfplumber")
        return tables

    def _pdf_to_tables(self, pdf_data: bytes) -> List[pd.DataFrame]:
        """
        Convert PDF data to tables using the preferred parser for this authority.
        
        Args:
            pdf_data: Raw PDF data
            
        Returns:
            List of pandas DataFrames containing the tables
        """
        # Create a temporary file to store the PDF
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as temp_file:
            temp_file.write(pdf_data)
            temp_file.flush()
            
            try:
                if self.PREFERRED_PARSER == 'camelot_stream':
                    return self._extract_tables_camelot(temp_file.name, 'stream')
                elif self.PREFERRED_PARSER == 'camelot_lattice':
                    return self._extract_tables_camelot(temp_file.name, 'lattice')
                elif self.PREFERRED_PARSER == 'pdfplumber':
                    return self._extract_tables_pdfplumber(temp_file.name)
                else:
                    logger.error(f"Unknown parser type: {self.PREFERRED_PARSER}")
                    return []
            except Exception as e:
                logger.error(f"Table extraction failed with {self.PREFERRED_PARSER}: {str(e)}")
                return []

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
        from pdfminer.high_level import extract_text
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