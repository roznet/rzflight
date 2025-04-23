import os
import logging
from typing import Dict, List, Any, Optional
from pathlib import Path
import glob
import re

from .cached import CachedSource
from ..parsers.aip_factory import AIPParserFactory
from ..parsers.procedure_factory import ProcedureParserFactory

logger = logging.getLogger(__name__)

class FranceEAIPSource(CachedSource):
    """Source implementation for reading France eAIP data from local directories."""
    
    def __init__(self, root_dir: str):
        """
        Initialize the France eAIP source.
        
        Args:
            root_dir: Root directory containing the eAIP data
        """
        super().__init__(root_dir)
        self.root_dir = Path(root_dir)
        
    def _find_airport_pdf(self, icao: str) -> Optional[Path]:
        """
        Find the airport PDF file in the AIRAC directory.
        
        Args:
            icao: ICAO airport code
            
        Returns:
            Path to the PDF file or None if not found
        """
        # Look for the most recent AIRAC directory
        airac_pattern = 'FRANCE/AIRAC*'
        logger.debug(f"Searching for AIRAC directories with pattern: {airac_pattern}")
        logger.debug(f"Root directory: {self.root_dir}")
        
        # check root_dir exists
        if not self.root_dir.exists():
            logger.warning(f"Root directory does not exist: {self.root_dir}")
            return None
        
        airac_dirs = sorted(self.root_dir.glob(airac_pattern), reverse=True)
        logger.debug(f"Found AIRAC directories: {[str(d) for d in airac_dirs]}")
        
        if not airac_dirs:
            logger.warning(f"No AIRAC directories found in {self.root_dir}")
            return None
            
        # Look for the airport PDF in the most recent AIRAC directory
        pdf_pattern = f"pdf/*{icao}*.pdf"
        logger.debug(f"Searching for PDF files with pattern: {pdf_pattern}")
        logger.debug(f"Searching in directory: {airac_dirs[0]}")
        
        pdf_files = list(airac_dirs[0].glob(pdf_pattern))
        logger.debug(f"Found PDF files: {[str(f) for f in pdf_files]}")
        
        return pdf_files[0] if pdf_files else None
        
    def _find_procedure_pdfs(self, icao: str) -> List[Path]:
        """
        Find all procedure PDF files for an airport.
        
        Args:
            icao: ICAO airport code
            
        Returns:
            List of paths to procedure PDF files
        """
        procedure_dir = self.root_dir / "html" / "eAIP" / "Cartes" / icao
        logger.debug(f"Looking for procedures in directory: {procedure_dir}")
        
        if not procedure_dir.exists():
            logger.warning(f"Procedure directory does not exist: {procedure_dir}")
            return []
            
        pdf_files = list(procedure_dir.glob("*.pdf"))
        logger.debug(f"Found procedure PDF files: {[str(f) for f in pdf_files]}")
        
        return pdf_files
        
    def fetch_airport_aip(self, icao: str) -> Dict[str, Any]:
        """
        Fetch airport data from local PDF file.
        
        Args:
            icao: ICAO airport code
            
        Returns:
            Dictionary containing airport data
        """
        pdf_path = self._find_airport_pdf(icao)
        if not pdf_path:
            raise FileNotFoundError(f"No airport PDF found for {icao}")
            
        # Read the PDF file
        with open(pdf_path, 'rb') as f:
            pdf_data = f.read()
            
        # Parse the PDF using the LFC parser (France)
        parser = AIPParserFactory.get_parser('LFC')
        parsed_data = parser.parse(pdf_data, icao)
        
        return {
            'icao': icao,
            'authority': 'LFC',
            'parsed_data': parsed_data
        }
        
    def fetch_procedures(self, icao: str) -> List[Dict[str, Any]]:
        """
        Fetch procedures from local PDF files.
        
        Args:
            icao: ICAO airport code
            
        Returns:
            List of dictionaries containing procedures data
        """
        pdf_files = self._find_procedure_pdfs(icao)
        if not pdf_files:
            return []
            
        rv = []
        for pdf_path in pdf_files:
            # Extract procedure name from filename
            name = pdf_path.stem
            
            # Parse the procedure name
            parser = ProcedureParserFactory.get_parser('LEC')
            parsed = parser.parse(name, icao)
            if parsed:
                rv.append(parsed)
                
        return rv
        
    def get_airport_aip(self, icao: str, max_age_days: int = 7) -> Dict[str, Any]:
        """
        Get airport data from cache or fetch it if not available.
        
        Args:
            icao: ICAO airport code
            max_age_days: Maximum age of cache in days
            
        Returns:
            Dictionary containing airport data
        """
        return self.get_data('airport_aip', 'json', icao, max_age_days=max_age_days)
        
    def get_procedures(self, icao: str, max_age_days: int = 7) -> List[Dict[str, Any]]:
        """
        Get procedures data from cache or fetch it if not available.
        
        Args:
            icao: ICAO airport code
            max_age_days: Maximum age of cache in days
            
        Returns:
            List of dictionaries containing procedures data
        """
        return self.get_data('procedures', 'json', icao, max_age_days=max_age_days) 