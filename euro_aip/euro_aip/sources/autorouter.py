import requests
import logging
from typing import Dict, List, Any, Optional
from pathlib import Path
import json
import re
import os
from datetime import datetime

from .cached import CachedSource
from ..utils.autorouter_credentials import AutorouterCredentialManager
from euro_aip.sources.base import SourceInterface
from ..utils.field_standardization_service import FieldStandardizationService

logger = logging.getLogger(__name__)

class AutorouterSource(CachedSource, SourceInterface):
    """Source implementation for the Autorouter API."""
    
    def __init__(self, cache_dir: str, username: Optional[str] = None, password: Optional[str] = None):
        """
        Initialize the Autorouter source.
        
        Args:
            cache_dir: Base directory for caching
            username: Optional username for API authentication
            password: Optional password for API authentication
        """
        super().__init__(cache_dir)
        self.credential_manager = AutorouterCredentialManager(cache_dir)
        if username is not None or password is not None:
            self.credential_manager.set_credentials(username, password)
        self.base_url = "https://api.autorouter.aero/v1.0/pams"

    def _get_headers(self) -> Dict[str, str]:
        """Get headers for API requests."""
        return {
            "Authorization": f"Bearer {self.credential_manager.get_token()}",
            "Accept": "application/json"
        }

    def _extract_airport_doc_list(self, data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Extract airport document list from API response."""
        if not data:
            return []
        
        rv = []
        for info in data:
            icao = info['icao']
            airport = info['Airport']
            
            for one in airport:
                if one['section'] == 'AD 2':
                    filename = one['filename']
                    basename, ext = os.path.splitext(filename)
                    one['doccachefilename'] = f'docs/{basename}'
                    one['aipcachefilename'] = f'aip/{icao}'
                    one['icao'] = icao
                    rv.append(one)
                    break
        return rv

    def fetch_airport(self, icao: str) -> Dict[str, Any]:
        """
        Fetch airport data from Autorouter API.
        
        Args:
            icao: ICAO airport code
            
        Returns:
            Dictionary containing airport data
        """
        url = f"{self.base_url}/airport/{icao}"
        try:
            response = requests.get(url, headers=self._get_headers())
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.error(f"Error fetching airport data for {icao}: {e}")
            raise


    def get_airport_doclist(self, icao: str, max_age_days: int = 28) -> Dict[str, Any]:
        """
        Get airport data from cache or fetch it if not available.
        
        Args:
            icao: ICAO airport code
            max_age_days: Maximum age of cache in days
            
        Returns:
            Dictionary containing airport data
        """
        return self.get_data('airport_doclist', 'json', icao, max_age_days=max_age_days)

    def fetch_procedures(self, icao: str, max_age_days: int = 28) -> List[Dict[str, Any]]:
        """
        Get procedures data from cache or fetch it if not available.
        
        Args:
            icao: ICAO airport code
            max_age_days: Maximum age of cache in days
            
        Returns:
            List of dictionaries containing procedures data
        """
        # Get airport data
        data = self.get_airport_data(icao, max_age_days)
        if not data:
            return []
        
        return self.parse_procedure(data, icao)
        
    def parse_procedure(self, data: List[Dict[str, Any]], icao: str) -> List[Dict[str, Any]]:
        # Extract procedures from airport data
        rv = []
        for info in data:
            for section in ['Arrival','Departure','Approach']:
                lst = info[section]
                for x in lst: 
                    proc = {'airport':icao,'type':section.lower()}
                    for field in ['heading']:
                        proc[field] = x[field]
                    
                    # Parse the procedure name if it's an approach
                    if section == 'Approach':
                        from ..parsers.procedure_factory import ProcedureParserFactory
                        parser = ProcedureParserFactory.get_parser(info.get('authority', 'DEFAULT'))
                        parsed = parser.parse(proc['heading'], icao)
                        if parsed:
                            proc.update(parsed)
                    
                    rv.append(proc)
        return rv

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
    
    def fetch_document(self, doc_id: str) -> bytes:
        """
        Fetch a document from Autorouter API.
        
        Args:
            doc_id: Document ID
            
        Returns:
            Document content as bytes
        """
        url = f"{self.base_url}/id/{doc_id}"
        try:
            response = requests.get(url, headers=self._get_headers())
            response.raise_for_status()
            return response.content
        except requests.RequestException as e:
            logger.error(f"Error fetching document {doc_id}: {e}")
            raise

    def get_document(self, doc_id: str, icao: str, max_age_days: int = 28) -> bytes:
        """
        Get document from cache or fetch it if not available.
        
        Args:
            doc_id: Document ID
            icao: ICAO airport code (used as cache parameter)
            max_age_days: Maximum age of cache in days
            
        Returns:
            Document content as bytes
        """
        return self.get_data('document', 'pdf', doc_id, cache_param=icao, max_age_days=max_age_days)


    def fetch_airport_aip(self, icao: str, max_age_days: int = 28) -> Optional[Dict[str, Any]]:
        """
        Get airport AIP data from cache or fetch and parse it if not available.
        
        Args:
            icao: ICAO airport code
            max_age_days: Maximum age of cache in days
            
        Returns:
            Dictionary containing parsed AIP data or None if not available
        """
        data = self.get_airport_doclist(icao, max_age_days)
        docs = self._extract_airport_doc_list(data)
        if not docs:
            return None
            
        for doc in docs:
            if doc.get('section') == 'AD 2':
                doc_id = doc['docid']
                pdf_data = self.get_document(doc_id, icao, max_age_days)
                
                # Get the appropriate parser using the factory
                authority = doc.get('authority')
                from ..parsers.aip_factory import AIPParserFactory
                parser = AIPParserFactory.get_parser(authority)
                
                # Parse the PDF data
                parsed_data = parser.parse(pdf_data, icao)
                
                return {
                    'icao': icao,
                    'authority': authority,
                    'parsed_data': parsed_data
                }
        return None
    
    def get_airport_aip(self, icao: str, max_age_days: int = 28) -> Optional[Dict[str, Any]]:
        """
        Get airport AIP data from cache or fetch and parse it if not available.
        
        Args:
            icao: ICAO airport code
            max_age_days: Maximum age of cache in days
            
        Returns:
            Dictionary containing parsed AIP data or None if not available
        """
        return self.get_data('airport_aip', 'json', icao, max_age_days=max_age_days)

    def get_approach_data(self, icao: str, max_age_days: int = 28) -> List[Dict[str, Any]]:
        """
        Get approach data from cache or fetch and parse it if not available.
        """
        procedures = self.get_procedures(icao, max_age_days)
        rv = []
        authority = 'DEFAULT'
        for proc in procedures:
            if proc['type'] == 'approach':
                from ..parsers.procedure_factory import ProcedureParserFactory
                parser = ProcedureParserFactory.get_parser(authority)
                parsed = parser.parse(proc['heading'], icao)
                if parsed:
                    rv.append(parsed)
        return rv

    def update_model(self, model: 'EuroAipModel', airports: Optional[List[str]] = None) -> None:
        """
        Update the EuroAipModel with data from this source.
        
        Args:
            model: The EuroAipModel to update
            airports: Optional list of specific airports to process. If None, 
                     the source will process all available airports.
        """
        from ..models import Airport, Procedure
        
        # Initialize field standardization service
        field_service = FieldStandardizationService()
        
        # Determine which airports to process
        if airports is None:
            # Autorouter doesn't have find_available_airports, so we need airports to be provided
            logger.warning("Autorouter source requires specific airports to be provided")
            return
        
        logger.info(f"Updating model with {len(airports)} airports from Autorouter")
        
        for icao in airports:
            try:
                # Get or create airport in model
                if icao not in model.airports:
                    model.airports[icao] = Airport(ident=icao)
                
                airport = model.airports[icao]
                
                # Get basic airport data
                airport_data = self.get_airport_data(icao)
                if airport_data:
                    # Extract basic airport information if available
                    for info in airport_data:
                        if 'name' in info and not airport.name:
                            airport.name = info['name']
                        if 'country' in info and not airport.country:
                            airport.country = info['country']
                        if 'city' in info and not airport.city:
                            airport.city = info['city']
                        if 'latitude' in info and not airport.latitude_deg:
                            airport.latitude_deg = info['latitude']
                        if 'longitude' in info and not airport.longitude_deg:
                            airport.longitude_deg = info['longitude']
                        if 'elevation' in info and not airport.elevation_ft:
                            airport.elevation_ft = info['elevation']
                
                # Get AIP data and convert to AIPEntry objects
                aip_data = self.get_airport_aip(icao)
                if aip_data and 'parsed_data' in aip_data:
                    # Create AIPEntry objects from parsed data
                    entries = field_service.create_aip_entries_from_parsed_data(icao, aip_data['parsed_data'])
                    
                    if entries:
                        airport.add_aip_entries(entries)
                        airport.add_source('autorouter')
                        logger.debug(f"Added {len(entries)} AIP entries for {icao}")
                
                # Get procedures
                procedures_data = self.get_procedures(icao)
                if procedures_data:
                    for proc_data in procedures_data:
                        if proc_data:
                            proc_type = proc_data.get('type', 'unknown')
                            if proc_type != 'approach':
                                continue
                            approach_type = proc_data.get('approach_type', 'unknown')
                            if approach_type == 'unknown':
                                continue
                            procedure = Procedure(
                                name=proc_data.get('name', ''),
                                procedure_type=proc_type,
                                approach_type=approach_type,
                                runway_number=proc_data.get('runway_number'),
                                runway_letter=proc_data.get('runway_letter'),
                                runway_ident=proc_data.get('runway_ident'),
                                category=proc_data.get('category'),
                                notes=proc_data.get('notes'),
                                source='autorouter',
                                raw_name=proc_data.get('raw_name', ''),
                                data=proc_data
                            )

                            airport.procedures.append(procedure)
                
                logger.debug(f"Updated {icao} with Autorouter data")
                
            except Exception as e:
                logger.error(f"Error updating {icao} with Autorouter data: {e}")
