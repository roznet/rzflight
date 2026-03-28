#!/usr/bin/env python3
"""
Slovenia eAIP Web Source

Fetches Slovenian AIP data from the official Slovenia Control AIM web interface.
Uses the same Eurocontrol MakeAIP format as UK/Norway eAIP.

Covers both AD-2 (IFR aerodromes) and AD-4 (VFR aerodromes).
"""

import logging
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

import requests
from bs4 import BeautifulSoup

from .cached import CachedSource
from euro_aip.sources.base import SourceInterface
from ..parsers.aip_factory import AIPParserFactory
from ..parsers.procedure_factory import ProcedureParserFactory

logger = logging.getLogger(__name__)


class SloveniaEAIPWebSource(CachedSource, SourceInterface):
    """
    Online source for Slovenia eAIP using the public Slovenia Control AIM interface.

    Uses the standard Eurocontrol MakeAIP HTML format (same as UK/Norway),
    so the EGC parser can be reused.

    Covers both AD-2 (IFR: LJLJ, LJMB, LJCE, LJPZ) and AD-4 (VFR aerodromes).
    AD-4 pages use section IDs like {ICAO}-AD-4.{N} which are normalised to AD-2
    before parsing so the standard EGC parser works unchanged.
    """

    SUPPORTED_PREFIXES = ["LJ"]
    AD2_LINK_PATTERN = re.compile(r"LJ-AD-2\.(LJ[A-Z]{2})-en-GB\.html")
    AD4_LINK_PATTERN = re.compile(r"LJ-AD-4\.(LJ[A-Z]{2})-en-GB\.html")

    AIP_BASE_URL = "https://aim.sloveniacontrol.si/aim/eAIP/Operations"

    # Parser authority code — reuse Eurocontrol (EGC) format
    AUTHORITY = "ENC"
    SOURCE_NAME = "slovenia_eaip_html"

    def __init__(self, cache_dir: str, airac_date: str):
        super().__init__(cache_dir)
        self.airac_date = airac_date
        self._validate_airac_date()

    def supported_icao_prefixes(self) -> List[str]:
        return self.SUPPORTED_PREFIXES

    def _validate_airac_date(self):
        try:
            datetime.strptime(self.airac_date, '%Y-%m-%d')
        except ValueError:
            raise ValueError(f"Invalid AIRAC date format: {self.airac_date}. Expected YYYY-MM-DD")

    def _build_url(self, path: str) -> str:
        airac_root = f"{self.airac_date}-AIRAC"
        return f"{self.AIP_BASE_URL}/{airac_root}/{path}"

    def _get_index_url(self) -> str:
        return self._build_url("html/eAIP/LJ-menu-en-GB.html")

    def _get_airport_url(self, icao: str, ad_section: str = "AD-2") -> str:
        return self._build_url(f"html/eAIP/LJ-{ad_section}.{icao}-en-GB.html")

    def _get_cache_key(self, resource_type: str, identifier: str = None) -> str:
        if identifier:
            return f"{self.airac_date}_{resource_type}_{identifier}.html"
        return f"{self.airac_date}_{resource_type}.html"

    def _fetch_with_cache(self, resource_type: str, identifier: str = None, url: str = None) -> bytes:
        cache_key = self._get_cache_key(resource_type, identifier)

        if url is None:
            if resource_type == 'index':
                url = self._get_index_url()
            elif resource_type == 'airport' and identifier:
                url = self._get_airport_url(identifier)
            else:
                raise ValueError(f"Cannot construct URL for resource_type={resource_type}, identifier={identifier}")

        cache_file = self.cache_path / cache_key

        if cache_file.exists():
            file_age = datetime.now() - datetime.fromtimestamp(cache_file.stat().st_mtime)
            if file_age.days <= 7:
                logger.info(f"Using cached {cache_key}")
                with open(cache_file, 'rb') as f:
                    return f.read()

        logger.info(f"Downloading {url}")
        content = self._download(url)

        with open(cache_file, 'wb') as f:
            f.write(content)
        logger.info(f"Cached {cache_key}")

        return content

    def _download(self, url: str) -> bytes:
        # Slovenia Control's SSL cert may have issues; verify=False is needed
        resp = requests.get(url, timeout=30, verify=False)
        resp.raise_for_status()
        return resp.content

    def _parse_index_for_airports(self, index_html: bytes) -> Dict[str, Dict[str, str]]:
        """Return mapping of ICAO -> {url, ad_section}."""
        soup = BeautifulSoup(index_html.decode('utf-8', errors='ignore'), 'html.parser')

        airports = {}

        for a_tag in soup.find_all('a', href=True):
            href = a_tag.get('href', '')

            m = self.AD2_LINK_PATTERN.search(href)
            if m:
                icao = m.group(1)
                airports[icao] = {
                    'url': self._get_airport_url(icao, "AD-2"),
                    'ad_section': 'AD-2',
                }
                continue

            m = self.AD4_LINK_PATTERN.search(href)
            if m:
                icao = m.group(1)
                if icao not in airports:  # AD-2 takes priority
                    airports[icao] = {
                        'url': self._get_airport_url(icao, "AD-4"),
                        'ad_section': 'AD-4',
                    }

        logger.info(
            f"Discovered {len(airports)} Slovenian airports from index "
            f"({sum(1 for a in airports.values() if a['ad_section'] == 'AD-2')} AD-2, "
            f"{sum(1 for a in airports.values() if a['ad_section'] == 'AD-4')} AD-4)"
        )
        return airports

    def find_available_airports(self) -> List[str]:
        try:
            index_html = self._fetch_with_cache('index')
            mapping = self._parse_index_for_airports(index_html)
            return sorted(mapping.keys())
        except Exception as e:
            logger.error(f"Failed to fetch or parse Slovenia eAIP index: {e}")
            return []

    def fetch_airport_html(self, icao: str, ad_section: str = "AD-2") -> Optional[bytes]:
        try:
            url = self._get_airport_url(icao, ad_section)
            return self._fetch_with_cache('airport', icao, url=url)
        except Exception as e:
            logger.warning(f"Failed to fetch airport page for {icao}: {e}")
            return None

    @staticmethod
    def _normalise_ad4_to_ad2(html_bytes: bytes) -> bytes:
        """Rewrite AD-4 section IDs to AD-2 so the standard EGC parser works."""
        return html_bytes.replace(b'-AD-4.', b'-AD-2.')

    def _resolve_ad_section(self, icao: str) -> str:
        """Determine whether an airport is AD-2 or AD-4 from the index."""
        try:
            index_html = self._fetch_with_cache('index')
            info = self._parse_index_for_airports(index_html)
            return info.get(icao, {}).get('ad_section', 'AD-2')
        except Exception:
            return 'AD-2'

    def _fetch_and_normalise(self, icao: str) -> Optional[bytes]:
        """Fetch airport HTML and normalise AD-4 to AD-2 if needed."""
        ad_section = self._resolve_ad_section(icao)
        html_bytes = self.fetch_airport_html(icao, ad_section)
        if html_bytes and ad_section == 'AD-4':
            html_bytes = self._normalise_ad4_to_ad2(html_bytes)
        return html_bytes

    def fetch_airport_aip(self, icao: str) -> Optional[Dict[str, Any]]:
        html_bytes = self._fetch_and_normalise(icao)
        if not html_bytes:
            return None
        parser = AIPParserFactory.get_parser(self.AUTHORITY, 'html')
        parsed_data = parser.parse(html_bytes, icao)
        return {
            'icao': icao,
            'authority': self.AUTHORITY,
            'parsed_data': parsed_data
        }

    def fetch_procedures(self, icao: str) -> List[Dict[str, Any]]:
        html_bytes = self._fetch_and_normalise(icao)
        if not html_bytes:
            return []
        parser = AIPParserFactory.get_parser(self.AUTHORITY, 'html')
        return parser.extract_procedures(html_bytes, icao)

    def get_airport_aip(self, icao: str, max_age_days: int = 28) -> Optional[Dict[str, Any]]:
        return self.fetch_airport_aip(icao)

    def get_procedures(self, icao: str, max_age_days: int = 28) -> List[Dict[str, Any]]:
        return self.fetch_procedures(icao)

    def update_model(self, model: 'EuroAipModel', airports: Optional[List[str]] = None) -> None:
        from ..models import Airport, Procedure
        from ..utils.field_standardization_service import FieldStandardizationService

        field_service = FieldStandardizationService()
        procedure_parser = ProcedureParserFactory.get_parser(self.AUTHORITY)

        airports_to_process = self.filter_airports(airports)

        if airports_to_process is None:
            airports_to_process = self.find_available_airports()
        if not airports_to_process:
            logger.warning("No Slovenian airports found via web index")
            return

        # Discover which airports are AD-2 vs AD-4
        index_html = self._fetch_with_cache('index')
        airport_info = self._parse_index_for_airports(index_html)

        logger.info(f"Updating model from Slovenia eAIP web source for {len(airports_to_process)} airports")

        for icao in airports_to_process:
            try:
                info = airport_info.get(icao, {'ad_section': 'AD-2'})
                ad_section = info['ad_section']

                html_bytes = self.fetch_airport_html(icao, ad_section)
                if not html_bytes:
                    continue

                # Normalise AD-4 section IDs to AD-2 for the parser
                if ad_section == 'AD-4':
                    html_bytes = self._normalise_ad4_to_ad2(html_bytes)

                if icao not in model.airports:
                    model.add_airport(Airport(ident=icao))

                airport = model.airports[icao]

                parser = AIPParserFactory.get_parser(self.AUTHORITY, 'html')
                parsed_data = parser.parse(html_bytes, icao)
                if parsed_data:
                    entries = field_service.create_aip_entries_from_parsed_data(icao, parsed_data)
                    if entries:
                        airport.add_aip_entries(entries)
                        airport.add_source(self.SOURCE_NAME)

                procedures_data = parser.extract_procedures(html_bytes, icao)
                if procedures_data:
                    for proc_data in procedures_data:
                        procedure = Procedure(
                            name=proc_data.get('name', ''),
                            procedure_type=proc_data.get('type', 'approach'),
                            approach_type=proc_data.get('approach_type', ''),
                            runway_ident=proc_data.get('runway_ident'),
                            runway_letter=proc_data.get('runway_letter'),
                            runway_number=proc_data.get('runway_number'),
                            source=self.SOURCE_NAME,
                            authority=self.AUTHORITY,
                            raw_name=proc_data.get('name', ''),
                            data=proc_data
                        )
                        airport.add_procedure(procedure)

                logger.debug(f"Updated {icao} from Slovenia eAIP ({ad_section})")

            except Exception as e:
                logger.error(f"Error updating {icao} from Slovenia eAIP: {e}")
