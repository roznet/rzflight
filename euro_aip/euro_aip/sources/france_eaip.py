"""
Source for parsing French eAIP (Electronic Aeronautical Information Publication) data.

This source reads the official French eAIP data from the DGAC (Direction Générale
de l'Aviation Civile) website. The eAIP data can be downloaded from:
https://www.sia.aviation-civile.gouv.fr/produits-numeriques-en-libre-disposition/eaip.html

To use this source:
1. Download the "ZIP eAIP complet" from the DGAC website
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


class FranceEAIPSource(CachedSource, SourceInterface):
    """
    A source that provides access to French eAIP data.
    
    This source reads the official French eAIP data from the DGAC website.
    The eAIP data should be downloaded from:
    https://www.sia.aviation-civile.gouv.fr/produits-numeriques-en-libre-disposition/eaip.html
    
    To use this source:
    1. Download the "ZIP eAIP complet" from the DGAC website
    2. Extract the ZIP file to a directory
    3. Point this source to the extracted directory as the root directory
    
    The source will parse the XML files in the eAIP to extract relevant
    aeronautical information.
    """
    
    # Precompiled regex patterns for better performance
    AIRPORT_PDF_PATTERN = re.compile(r'FR-AD-2\.(LF[A-Z][A-Z])-fr')

    def __init__(self, cache_dir: str, root_dir: str):
        """
        Initialize the source.
        
        Args:
            root_dir: Path to the root directory of the extracted eAIP.
                     This should be the directory containing the 'FRANCE' folder
                     from the downloaded eAIP ZIP file.
        """
        super().__init__(cache_dir)
        self.root_dir = Path(root_dir)

    def find_available_airports(self) -> List[str]:
        """
        Find all available airports in the eAIP.
        """
        airac_pattern = 'FRANCE/AIRAC*'
        logger.debug(f"Searching for AIRAC directories with pattern: {airac_pattern}")
        logger.debug(f"Root directory: {self.root_dir}")
        
        # check root_dir exists
        if not self.root_dir.exists():
            logger.warning(f"Root directory does not exist: {self.root_dir}")
            return None
        
        airac_dirs = sorted(self.root_dir.glob(airac_pattern), reverse=True)
        # look for pdf of pattern pdf/FR-AD-2.(LF[A-Z][A-Z]).pdf
        pdf_pattern = 'pdf/FR-AD-2.LF*.pdf'
        pdf_files = list(airac_dirs[0].glob(pdf_pattern))
        logger.debug(f"Found PDF files: {[str(f) for f in pdf_files]}")
        # now extract the icao code from the pdf file name using regex
        rv = []
        for f in pdf_files:
            match = self.AIRPORT_PDF_PATTERN.search(f.stem)
            if match:
                rv.append(match.group(1))
        return rv

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
        # Look for the most recent AIRAC directory
        airac_pattern = 'FRANCE/AIRAC*'
        airac_dirs = sorted(self.root_dir.glob(airac_pattern), reverse=True)
        if not airac_dirs:
            logger.warning(f"No AIRAC directories found in {self.root_dir}")
            return []
            
        # Look for procedures in the most recent AIRAC directory
        procedure_dir = airac_dirs[0] / "html" / "eAIP" / "Cartes" / icao
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
            parser = ProcedureParserFactory.get_parser('LFC')
            parsed = parser.parse(name, icao)
            if parsed:
                rv.append(parsed)
                
        return rv
        
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
        from ..parsers.procedure_default import DefaultProcedureParser
        
        # Initialize field standardization service and procedure parser
        field_service = FieldStandardizationService()
        procedure_parser = ProcedureParserFactory.get_parser('LFC')
        
        # Determine which airports to process
        if airports is None:
            airports = self.find_available_airports()
        
        if not airports:
            logger.warning("No airports found to process")
            return
        
        logger.info(f"Updating model with {len(airports)} airports from France eAIP")

        skipped = []
        
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
                            airport.add_source('france_eaip')
                            logger.debug(f"Added {len(entries)} AIP entries for {icao}")
                except FileNotFoundError:
                    skipped.append(icao)
                    continue

                # Get procedures and create enhanced Procedure objects
                try:
                    procedures_data = self.get_procedures(icao)
                    if procedures_data:
                        for proc_data in procedures_data:
                            if proc_data:
                                # Use the DefaultProcedureParser to parse procedure name
                                parsed_procedure = proc_data
                                
                                procedure = Procedure(
                                    name=proc_data.get('name', ''),
                                    procedure_type=proc_data.get('type', 'unknown'),
                                    approach_type=parsed_procedure.get('approach_type', ''),
                                    runway_ident=parsed_procedure.get('runway_ident'),
                                    runway_letter=parsed_procedure.get('runway_letter'),
                                    runway_number=parsed_procedure.get('runway_number'),
                                    source='france_eaip',
                                    authority='LFC',
                                    raw_name=proc_data.get('name', ''),
                                    data=proc_data
                                )
                                airport.add_procedure(procedure)
                        
                        logger.debug(f"Added {len(procedures_data)} procedures for {icao}")
                except FileNotFoundError:
                    logger.debug(f"No procedures found for {icao} in France eAIP source")
                
                logger.debug(f"Updated {icao} with France eAIP data")
                
            except Exception as e:
                logger.error(f"Error updating {icao} with France eAIP data: {e}")
                # Continue with next airport instead of failing completely 

        if len(skipped) > 0:
            logger.info(f"{len(skipped)}/{len(airports)} Airports not found in France eAIP source")
                