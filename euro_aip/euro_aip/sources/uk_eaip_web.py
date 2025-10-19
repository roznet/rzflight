#!/usr/bin/env python3

import logging
import re
from typing import Dict, List, Any, Optional
from urllib.parse import urljoin, urldefrag
from datetime import datetime

import requests
from bs4 import BeautifulSoup

from .cached import CachedSource
from euro_aip.sources.base import SourceInterface
from ..parsers.aip_factory import AIPParserFactory
from ..parsers.procedure_factory import ProcedureParserFactory

logger = logging.getLogger(__name__)


class UKEAIPWebSource(CachedSource, SourceInterface):
    """
    Online source for UK eAIP using the public HTML index.
    
    This source fetches UK eAIP data from the official Aurora NATS web interface.
    It constructs URLs dynamically based on AIRAC dates and caches content
    with human-readable cache keys.
    """

    AIRPORT_LINK_PATTERN = re.compile(r"EG-AD-2\.(EG[A-Z]{2})-en-GB\.html")
    
    # Base URL components
    BASE_URL = "https://www.aurora.nats.co.uk/htmlAIP/Publications"

    def __init__(self, cache_dir: str, airac_date: str):
        """
        Initialize UK eAIP web source.
        
        Args:
            cache_dir: Directory for caching files
            airac_date: AIRAC effective date in YYYY-MM-DD format
        """
        super().__init__(cache_dir)
        self.airac_date = airac_date
        self._validate_airac_date()

    def _validate_airac_date(self):
        """Validate AIRAC date format."""
        try:
            datetime.strptime(self.airac_date, '%Y-%m-%d')
        except ValueError:
            raise ValueError(f"Invalid AIRAC date format: {self.airac_date}. Expected YYYY-MM-DD")

    def _build_url(self, path: str) -> str:
        """
        Build URL for any path within the UK eAIP structure.
        
        Args:
            path: Relative path from the AIRAC root (e.g., 'html/index-en-GB.html')
            
        Returns:
            Complete URL
        """
        airac_root = f"{self.airac_date}-AIRAC"
        return f"{self.BASE_URL}/{airac_root}/{path}"

    def _get_index_url(self) -> str:
        """Get the main index URL."""
        return self._build_url("html/eAIP/EG-menu-en-GB.html")

    def _get_airport_url(self, icao: str) -> str:
        """Get URL for a specific airport page."""
        return self._build_url(f"html/eAIP/EG-AD-2.{icao}-en-GB.html")

    def _get_cache_key(self, resource_type: str, identifier: str = None) -> str:
        """
        Generate human-readable cache key.
        
        Args:
            resource_type: Type of resource ('index', 'airport', 'toc', 'nav')
            identifier: Optional identifier (e.g., ICAO code for airports)
            
        Returns:
            Human-readable cache key
        """
        if identifier:
            return f"{self.airac_date}_{resource_type}_{identifier}.html"
        else:
            return f"{self.airac_date}_{resource_type}.html"

    def _fetch_with_cache(self, resource_type: str, identifier: str = None, url: str = None) -> bytes:
        """
        Fetch content with caching using human-readable keys.
        
        Args:
            resource_type: Type of resource ('index', 'airport', 'toc', 'nav')
            identifier: Optional identifier (e.g., ICAO code)
            url: URL to fetch (if None, will be constructed)
            
        Returns:
            HTML content as bytes
        """
        cache_key = self._get_cache_key(resource_type, identifier)
        
        if url is None:
            if resource_type == 'index':
                url = self._get_index_url()
            elif resource_type == 'airport' and identifier:
                url = self._get_airport_url(identifier)
            else:
                raise ValueError(f"Cannot construct URL for resource_type={resource_type}, identifier={identifier}")
        
        logger.debug(f"Fetching {resource_type} {identifier or ''} from {url}")
        
        # Simple file-based caching
        cache_file = self.cache_path / cache_key
        
        # Check if cache is valid (7 days)
        if cache_file.exists():
            file_age = datetime.now() - datetime.fromtimestamp(cache_file.stat().st_mtime)
            if file_age.days <= 7:
                logger.info(f"Using cached {cache_key}")
                with open(cache_file, 'rb') as f:
                    return f.read()
        
        # Download and cache
        logger.info(f"Downloading {url}")
        content = self._download(url)
        
        # Save to cache
        with open(cache_file, 'wb') as f:
            f.write(content)
        logger.info(f"Cached {cache_key}")
        
        return content

    def _download(self, url: str) -> bytes:
        """Download content from URL."""
        logger.info(f"Downloading {url}")
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        return resp.content

    def _parse_index_for_airports(self, index_html: bytes) -> Dict[str, str]:
        """Return mapping of ICAO -> absolute airport page URL (no fragment)."""
        soup = BeautifulSoup(index_html.decode('utf-8', errors='ignore'), 'html.parser')
        
        # Look for the ADdetails div containing airport information
        ad_details_div = soup.find('div', id='ADdetails')
        if not ad_details_div:
            logger.warning("Could not find ADdetails div in UK eAIP index")
            return {}
        
        links = {}
        all_links = []
        
        # Find all sub-divs with pattern AD-2.EGXXdetails
        airport_divs = ad_details_div.find_all('div', id=re.compile(r'AD-2\.EG[A-Z]{2}details'))
        
        logger.debug(f"Found {len(airport_divs)} airport detail divs")
        
        for div in airport_divs:
            # Find links within each airport div
            for a in div.find_all('a'):
                href = a.get('href')
                if not href:
                    continue
                    
                all_links.append(href)
                
                # Extract ICAO code from href pattern
                m = self.AIRPORT_LINK_PATTERN.search(href)
                if not m:
                    continue
                    
                icao = m.group(1)
                # Store ICAO -> URL mapping
                links[icao] = self._get_airport_url(icao)
        
        logger.debug(f"Found {len(all_links)} total links in ADdetails")
        logger.debug(f"First 10 links: {all_links[:10]}")
        logger.info(f"Discovered {len(links)} UK airports from index")
        return links

    def find_available_airports(self) -> List[str]:
        try:
            index_html = self._fetch_with_cache('index')
            mapping = self._parse_index_for_airports(index_html)
            return sorted(mapping.keys())
        except Exception as e:
            logger.error(f"Failed to fetch or parse UK eAIP index: {e}")
            return []

    def fetch_airport_html(self, icao: str) -> Optional[bytes]:
        try:
            return self._fetch_with_cache('airport', icao)
        except Exception as e:
            logger.warning(f"Failed to fetch airport page for {icao}: {e}")
            return None

    def fetch_airport_aip(self, icao: str) -> Optional[Dict[str, Any]]:
        html_bytes = self.fetch_airport_html(icao)
        if not html_bytes:
            return None
        parser = AIPParserFactory.get_parser('EGC', 'html')
        parsed_data = parser.parse(html_bytes, icao)
        return {
            'icao': icao,
            'authority': 'EGC',
            'parsed_data': parsed_data
        }

    def fetch_procedures(self, icao: str) -> List[Dict[str, Any]]:
        html_bytes = self.fetch_airport_html(icao)
        if not html_bytes:
            return []
        parser = AIPParserFactory.get_parser('EGC', 'html')
        return parser.extract_procedures(html_bytes, icao)

    def get_airport_aip(self, icao: str, max_age_days: int = 28) -> Optional[Dict[str, Any]]:
        # Use caching keyed by URL for index and airport pages via _http_get.
        # Here we just wrap to a JSON-like payload consistent with other sources.
        return self.fetch_airport_aip(icao)

    def get_procedures(self, icao: str, max_age_days: int = 28) -> List[Dict[str, Any]]:
        return self.fetch_procedures(icao)

    def update_model(self, model: 'EuroAipModel', airports: Optional[List[str]] = None) -> None:
        from ..models import Airport, Procedure
        from ..utils.field_standardization_service import FieldStandardizationService

        field_service = FieldStandardizationService()
        procedure_parser = ProcedureParserFactory.get_parser('EGC')

        if airports is None:
            airports = self.find_available_airports()
        if not airports:
            logger.warning("No UK airports found via web index")
            return

        logger.info(f"Updating model from UK eAIP web source for {len(airports)} airports")

        for icao in airports:
            try:
                if icao not in model.airports:
                    model.airports[icao] = Airport(ident=icao)

                airport = model.airports[icao]

                # AIP entries
                aip_payload = self.get_airport_aip(icao)
                if aip_payload and 'parsed_data' in aip_payload:
                    entries = field_service.create_aip_entries_from_parsed_data(icao, aip_payload['parsed_data'])
                    if entries:
                        airport.add_aip_entries(entries)
                        airport.add_source('uk_eaip_html')

                # Procedures
                procedures_data = self.get_procedures(icao)
                if procedures_data:
                    for proc_data in procedures_data:
                        parsed = proc_data  # already parsed via EGC parser
                        procedure = Procedure(
                            name=parsed.get('name', ''),
                            procedure_type=parsed.get('type', 'approach'),
                            approach_type=parsed.get('approach_type', ''),
                            runway_ident=parsed.get('runway_ident'),
                            runway_letter=parsed.get('runway_letter'),
                            runway_number=parsed.get('runway_number'),
                            source='uk_eaip_html',
                            authority='EGC',
                            raw_name=parsed.get('name', ''),
                            data=parsed
                        )
                        airport.add_procedure(procedure)

                logger.debug(f"Updated {icao} from UK eAIP web source")

            except Exception as e:
                logger.error(f"Error updating {icao} from UK eAIP web source: {e}")
