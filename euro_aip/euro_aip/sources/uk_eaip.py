"""
Source for parsing UK eAIP (Electronic Aeronautical Information Publication) data.

This source reads the official UK eAIP data from the UK CAA (Civil Aviation Authority) 
website. The eAIP data can be downloaded from:
https://nats-uk.ead-it.com/cms-nats/opencms/en/Publications/AIP/

To use this source:
1. Download the UK eAIP from the NATS website
2. Extract the ZIP file to a directory
3. Point this source to the extracted directory as the root directory

The eAIP contains comprehensive aeronautical information including:
- Airport information
- Navigation procedures
- Airspace structures
- ATC procedures
- And more

Note: The eAIP is updated every 28 days (AIRAC cycle). Make sure to use the
latest version for current information.

This source supports both HTML and PDF formats automatically.
"""

import os
import logging
from typing import Dict, List, Any, Optional
from pathlib import Path
import glob
import re

from .cached import CachedSource
from ..parsers.aip_factory import AIPParserFactory
from ..parsers.procedure_factory import ProcedureParserFactory
from euro_aip.sources.base import SourceInterface

logger = logging.getLogger(__name__)

class UKEAIPSource(CachedSource, SourceInterface):
    """
    A source that provides access to UK eAIP data.
    
    This source reads the official UK eAIP data from the UK CAA website.
    The eAIP data should be downloaded from:
    https://www.nats-uk.ead-it.com/cms-nats/opencms/en/Publications/Aeronautical-Information-Publications/
    
    To use this source:
    1. Download the UK eAIP from the NATS website
    2. Extract the ZIP file to a directory
    3. Point this source to the extracted directory as the root directory
    
    The source will parse both HTML and PDF files in the eAIP to extract relevant
    aeronautical information. It automatically detects the format and uses the
    appropriate parser.
    """
    
    # Precompiled regex patterns for better performance
    AIRPORT_HTML_PATTERN = re.compile(r'(EG[A-Z][A-Z])-en-GB')
    AIRPORT_PDF_PATTERN = re.compile(r'EG-AD-2\.(EG[A-Z][A-Z])-en')

    def __init__(self, cache_dir: str, root_dir: str):
        """
        Initialize the source.
        
        Args:
            root_dir: Path to the root directory of the extracted UK eAIP.
                     This should be the directory containing the UK eAIP files
                     from the downloaded ZIP file.
        """
        super().__init__(cache_dir)
        self.root_dir = Path(root_dir)

    def find_available_airports(self) -> List[str]:
        """
        Find all available airports in the UK eAIP.
        """
        # Look for both HTML and PDF files
        html_pattern = '**/EG-AD-2.EG*-en-GB.html'
        pdf_pattern = '**/EG-AD-2.EG*.pdf'
        
        logger.debug(f"Searching for HTML files with pattern: {html_pattern}")
        logger.debug(f"Searching for PDF files with pattern: {pdf_pattern}")
        logger.debug(f"Root directory: {self.root_dir}")
        
        # check root_dir exists
        if not self.root_dir.exists():
            logger.warning(f"Root directory does not exist: {self.root_dir}")
            return []
        
        # Find HTML files
        html_files = list(self.root_dir.glob(html_pattern))
        logger.debug(f"Found HTML files: {[str(f) for f in html_files]}")
        
        # Find PDF files
        pdf_files = list(self.root_dir.glob(pdf_pattern))
        logger.debug(f"Found PDF files: {[str(f) for f in pdf_files]}")
        
        # Extract ICAO codes from both HTML and PDF files
        rv = []
        
        # Extract from HTML files
        for f in html_files:
            match = self.AIRPORT_HTML_PATTERN.search(f.stem)
            if match:
                icao = match.group(1)
                if icao not in rv:
                    rv.append(icao)
        
        # Extract from PDF files
        for f in pdf_files:
            match = self.AIRPORT_PDF_PATTERN.search(f.stem)
            if match:
                icao = match.group(1)
                if icao not in rv:
                    rv.append(icao)
        
        return rv

    def _find_airport_file(self, icao: str) -> Optional[Path]:
        """
        Find the airport file (HTML or PDF) in the eAIP directory.
        
        Args:
            icao: ICAO airport code
            
        Returns:
            Path to the airport file or None if not found
        """
        # Look for both HTML and PDF files
        html_pattern = f'**/EG-AD-2.{icao}-en-GB.html'
        pdf_pattern = f'**/EG-AD-2.{icao}*.pdf'
        
        logger.debug(f"Searching for HTML files with pattern: {html_pattern}")
        logger.debug(f"Searching for PDF files with pattern: {pdf_pattern}")
        logger.debug(f"Root directory: {self.root_dir}")
        
        # check root_dir exists
        if not self.root_dir.exists():
            logger.warning(f"Root directory does not exist: {self.root_dir}")
            return None
        
        # Try HTML first (preferred)
        html_files = list(self.root_dir.glob(html_pattern))
        if html_files:
            logger.debug(f"Found HTML file: {html_files[0]}")
            return html_files[0]
        
        # Try PDF as fallback
        pdf_files = list(self.root_dir.glob(pdf_pattern))
        if pdf_files:
            logger.debug(f"Found PDF file: {pdf_files[0]}")
            return pdf_files[0]
        
        logger.debug(f"No airport file found for {icao}")
        return None
        
    def _find_procedure_files(self, icao: str) -> List[Path]:
        """
        Find all procedure files for an airport.
        
        Args:
            icao: ICAO airport code
            
        Returns:
            List of paths to procedure files (HTML or PDF)
        """
        # Look for procedures in the eAIP directory
        # UK eAIP typically has procedures in a charts or procedures subdirectory
        procedure_patterns = [
            f"**/charts/{icao}/*.html",
            f"**/charts/{icao}/*.pdf",
            f"**/procedures/{icao}/*.html",
            f"**/procedures/{icao}/*.pdf",
            f"**/{icao}/charts/*.html",
            f"**/{icao}/charts/*.pdf",
            f"**/{icao}/procedures/*.html",
            f"**/{icao}/procedures/*.pdf"
        ]
        
        files = []
        for pattern in procedure_patterns:
            logger.debug(f"Looking for procedures with pattern: {pattern}")
            found_files = list(self.root_dir.glob(pattern))
            files.extend(found_files)
            
        logger.debug(f"Found procedure files: {[str(f) for f in files]}")
        
        return files
        
    def fetch_airport_aip(self, icao: str) -> Dict[str, Any]:
        """
        Fetch airport data from local file (HTML or PDF).
        
        Args:
            icao: ICAO airport code
            
        Returns:
            Dictionary containing airport data
        """
        file_path = self._find_airport_file(icao)
        if not file_path:
            raise FileNotFoundError(f"No airport file found for {icao}")
            
        # Read the file
        with open(file_path, 'rb') as f:
            file_data = f.read()
            
        # Parse using the EGC parser (automatically detects format)
        parser = AIPParserFactory.get_parser('EGC', 'dual')
        parsed_data = parser.parse(file_data, icao)
        
        return {
            'icao': icao,
            'authority': 'EGC',
            'parsed_data': parsed_data
        }
        
    def fetch_procedures(self, icao: str) -> List[Dict[str, Any]]:
        """
        Fetch procedures from local files.
        
        Args:
            icao: ICAO airport code
            
        Returns:
            List of dictionaries containing procedures data
        """
        file = self._find_airport_file(icao)
        if not file:
            return []
            
        rv = []
        # Read the file
        with open(file, 'rb') as f:
            file_data = f.read()

        parser = AIPParserFactory.get_parser('EGC', 'html')
        procedures = parser.extract_procedures(file_data, icao)
        return procedures
        
    def get_airport_aip(self, icao: str, max_age_days: int = 28) -> Dict[str, Any]:
        """
        Get airport data from cache or fetch it if not available.
        
        Args:
            icao: ICAO airport code
            max_age_days: Maximum age of cache in days
            
        Returns:
            Dictionary containing airport data
        """
        return self.get_data('airport_aip', 'json', icao, max_age_days=max_age_days)
        
    def get_procedures(self, icao: str, max_age_days: int = 28) -> List[Dict[str, Any]]:
        """
        Get procedures data from cache or fetch it if not available.
        
        Args:
            icao: ICAO airport code
            max_age_days: Maximum age of cache in days
            
        Returns:
            List of dictionaries containing procedures data
        """
        return self.get_data('procedures', 'json', icao, max_age_days=max_age_days)
    
    def update_model(self, model: 'EuroAipModel', airports: Optional[List[str]] = None) -> None:
        """
        Update the EuroAipModel with data from this source.
        
        Args:
            model: The EuroAipModel to update
            airports: Optional list of specific airports to process. If None, 
                     the source will process all available airports.
        """
        from ..models import Airport, Procedure
        from ..utils.field_standardization_service import FieldStandardizationService
        
        # Initialize field standardization service
        field_service = FieldStandardizationService()
        
        # Determine which airports to process
        if airports is None:
            airports = self.find_available_airports()
        
        if not airports:
            logger.warning("No airports found to process")
            return
        
        logger.info(f"Updating model with {len(airports)} airports from UK eAIP")
        
        for icao in airports:
            try:
                # Get or create airport in model
                if icao not in model.airports:
                    model.airports[icao] = Airport(ident=icao)
                
                airport = model.airports[icao]
                
                # Get AIP data and convert to AIPEntry objects
                try:
                    aip_data = self.get_airport_aip(icao)
                    if aip_data and 'parsed_data' in aip_data:
                        # Create AIPEntry objects from parsed data
                        entries = field_service.create_aip_entries_from_parsed_data(icao, aip_data['parsed_data'])
                        
                        if entries:
                            airport.add_aip_entries(entries)
                            airport.add_source('uk_eaip')
                            logger.debug(f"Added {len(entries)} AIP entries for {icao}")
                except FileNotFoundError:
                    logger.info(f"Airport {icao} not found in UK eAIP source - skipping")
                    continue
                
                # Get procedures and create enhanced Procedure objects
                try:
                    procedures_data = self.get_procedures(icao)
                    if procedures_data:
                        for proc_data in procedures_data:
                            if proc_data:
                                # Extract runway information from procedure name
                                runway_info = self._extract_runway_from_procedure_name(proc_data.get('name', ''))
                                
                                procedure = Procedure(
                                    name=proc_data.get('name', ''),
                                    procedure_type=proc_data.get('type', 'unknown'),
                                    approach_type=proc_data.get('approach_type', ''),
                                    runway_ident=runway_info.get('runway_ident'),
                                    runway_letter=runway_info.get('runway_letter'),
                                    runway=runway_info.get('full_runway'),
                                    category=proc_data.get('category'),
                                    minima=proc_data.get('minima'),
                                    notes=proc_data.get('notes'),
                                    source='uk_eaip',
                                    authority='EGC',
                                    raw_name=proc_data.get('name', ''),
                                    data=proc_data
                                )
                                airport.add_procedure(procedure)
                        
                        logger.debug(f"Added {len(procedures_data)} procedures for {icao}")
                except FileNotFoundError:
                    logger.debug(f"No procedures found for {icao} in UK eAIP source")
                
                logger.debug(f"Updated {icao} with UK eAIP data")
                
            except Exception as e:
                logger.error(f"Error updating {icao} with UK eAIP data: {e}")
                # Continue with next airport instead of failing completely
    
    def _extract_runway_from_procedure_name(self, procedure_name: str) -> dict:
        """
        Extract runway information from procedure name.
        
        Args:
            procedure_name: Name of the procedure
            
        Returns:
            Dictionary with runway_ident, runway_letter, and full_runway
        """
        import re
        
        # Common patterns for runway extraction
        patterns = [
            r'RWY\s*(\d{1,2})([LRC]?)',  # RWY 13L, RWY 31R, etc.
            r'(\d{1,2})([LRC]?)\s*ILS',  # 13L ILS, 31R ILS, etc.
            r'ILS\s*(\d{1,2})([LRC]?)',  # ILS 13L, ILS 31R, etc.
            r'(\d{1,2})([LRC]?)\s*VOR',  # 13L VOR, 31R VOR, etc.
            r'VOR\s*(\d{1,2})([LRC]?)',  # VOR 13L, VOR 31R, etc.
            r'(\d{1,2})([LRC]?)\s*NDB',  # 13L NDB, 31R NDB, etc.
            r'NDB\s*(\d{1,2})([LRC]?)',  # NDB 13L, NDB 31R, etc.
            r'(\d{1,2})([LRC]?)\s*RNAV', # 13L RNAV, 31R RNAV, etc.
            r'RNAV\s*(\d{1,2})([LRC]?)', # RNAV 13L, RNAV 31R, etc.
        ]
        
        for pattern in patterns:
            match = re.search(pattern, procedure_name, re.IGNORECASE)
            if match:
                runway_ident = match.group(1)
                runway_letter = match.group(2) if len(match.groups()) > 1 else None
                full_runway = f"{runway_ident}{runway_letter}" if runway_letter else runway_ident
                
                return {
                    'runway_ident': runway_ident,
                    'runway_letter': runway_letter,
                    'full_runway': full_runway
                }
        
        return {'runway_ident': None, 'runway_letter': None, 'full_runway': None}
    
    def _extract_approach_type(self, procedure_name: str) -> Optional[str]:
        """
        Extract approach type from procedure name.
        
        Args:
            procedure_name: Name of the procedure
            
        Returns:
            Approach type (ILS, VOR, NDB, etc.) or None
        """
        import re
        
        # Common approach types
        approach_types = ['ILS', 'VOR', 'NDB', 'RNAV', 'GNSS', 'LOC', 'LDA', 'SDF']
        
        for approach_type in approach_types:
            if re.search(rf'\b{approach_type}\b', procedure_name, re.IGNORECASE):
                return approach_type
        
        return None
    
    def get_source_name(self) -> str:
        """Get the name of this source."""
        return 'uk_eaip' 