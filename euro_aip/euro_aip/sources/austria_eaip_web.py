#!/usr/bin/env python3
"""
Austria eAIP Web Source

Fetches Austrian AIP data from the official Austro Control eAIP portal.
Airport data is in PDF format (bilingual German/English), parsed by LOCAIPParser.

Covers PRI (primary airports), SRY (secondary airfields), and MIL (military).
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


class AustriaEAIPWebSource(CachedSource, SourceInterface):
    """
    Online source for Austria eAIP using the public Austro Control portal.

    Airport data is published as PDF documents at eaip.austrocontrol.at.
    The index page (ad_2.htm) lists all airports with direct PDF links
    categorised as PRI (airports), SRY (airfields), MIL (military).

    Uses the LOC authority parser which handles the bilingual German/English
    row-pair format in the PDFs.
    """

    SUPPORTED_PREFIXES = ["LO"]
    # Match PDF links like PART_3/AD_2/SRY/AD_2_LOAV/LO_AD_2_LOAV_en.pdf
    PDF_LINK_PATTERN = re.compile(
        r'PART_3/AD_2/(\w+)/AD_2_(LO\w+)/LO_AD_2_\2_en\.pdf'
    )

    AIP_BASE_URL = "https://eaip.austrocontrol.at"

    AUTHORITY = "LOC"
    SOURCE_NAME = "austria_eaip_pdf"

    def __init__(self, cache_dir: str, airac_date: str):
        super().__init__(cache_dir)
        self.airac_date = airac_date
        self._airac_code = self._date_to_code(airac_date)
        self._validate_airac_date()

    def supported_icao_prefixes(self) -> List[str]:
        return self.SUPPORTED_PREFIXES

    def _validate_airac_date(self):
        try:
            datetime.strptime(self.airac_date, '%Y-%m-%d')
        except ValueError:
            raise ValueError(f"Invalid AIRAC date format: {self.airac_date}. Expected YYYY-MM-DD")

    @staticmethod
    def _date_to_code(airac_date: str) -> str:
        """Convert YYYY-MM-DD to YYMMDD format used in Austria URLs."""
        dt = datetime.strptime(airac_date, '%Y-%m-%d')
        return dt.strftime('%y%m%d')

    def _build_url(self, path: str) -> str:
        return f"{self.AIP_BASE_URL}/lo/{self._airac_code}/{path}"

    def _get_index_url(self) -> str:
        return self._build_url("ad_2.htm")

    def _get_cache_key(self, resource_type: str, identifier: str = None) -> str:
        suffix = 'pdf' if resource_type == 'airport' else 'html'
        if identifier:
            return f"{self.airac_date}_{resource_type}_{identifier}.{suffix}"
        return f"{self.airac_date}_{resource_type}.{suffix}"

    def _fetch_with_cache(self, resource_type: str, identifier: str = None, url: str = None) -> bytes:
        cache_key = self._get_cache_key(resource_type, identifier)

        if url is None:
            if resource_type == 'index':
                url = self._get_index_url()
            else:
                raise ValueError(f"URL required for resource_type={resource_type}")

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
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        return resp.content

    def _parse_index_for_airports(self, index_html: bytes) -> Dict[str, Dict[str, str]]:
        """Return mapping of ICAO -> {url, category}."""
        soup = BeautifulSoup(index_html.decode('utf-8', errors='ignore'), 'html.parser')

        airports = {}
        for a_tag in soup.find_all('a', href=True):
            href = a_tag.get('href', '')
            m = self.PDF_LINK_PATTERN.search(href)
            if m:
                category = m.group(1)  # PRI, SRY, MIL
                icao = m.group(2)
                pdf_url = self._build_url(href)
                airports[icao] = {
                    'url': pdf_url,
                    'category': category,
                }

        logger.info(
            f"Discovered {len(airports)} Austrian airports from index "
            f"({sum(1 for a in airports.values() if a['category'] == 'PRI')} PRI, "
            f"{sum(1 for a in airports.values() if a['category'] == 'SRY')} SRY, "
            f"{sum(1 for a in airports.values() if a['category'] == 'MIL')} MIL)"
        )
        return airports

    def find_available_airports(self) -> List[str]:
        try:
            index_html = self._fetch_with_cache('index')
            mapping = self._parse_index_for_airports(index_html)
            return sorted(mapping.keys())
        except Exception as e:
            logger.error(f"Failed to fetch or parse Austria eAIP index: {e}")
            return []

    def fetch_airport_pdf(self, icao: str, url: str = None) -> Optional[bytes]:
        """Fetch PDF data for an airport."""
        try:
            if url is None:
                # Look up from index
                index_html = self._fetch_with_cache('index')
                airport_info = self._parse_index_for_airports(index_html)
                if icao not in airport_info:
                    logger.warning(f"Airport {icao} not found in Austria eAIP index")
                    return None
                url = airport_info[icao]['url']
            return self._fetch_with_cache('airport', icao, url=url)
        except Exception as e:
            logger.warning(f"Failed to fetch airport PDF for {icao}: {e}")
            return None

    def fetch_airport_aip(self, icao: str) -> Optional[Dict[str, Any]]:
        pdf_data = self.fetch_airport_pdf(icao)
        if not pdf_data:
            return None
        parser = AIPParserFactory.get_parser(self.AUTHORITY, 'pdf')
        parsed_data = parser.parse(pdf_data, icao)
        return {
            'icao': icao,
            'authority': self.AUTHORITY,
            'parsed_data': parsed_data,
        }

    def get_airport_aip(self, icao: str, max_age_days: int = 28) -> Optional[Dict[str, Any]]:
        return self.fetch_airport_aip(icao)

    def get_procedures(self, icao: str, max_age_days: int = 28) -> List[Dict[str, Any]]:
        # Austrian PDFs don't contain procedure charts in parseable form
        return []

    def update_model(self, model: 'EuroAipModel', airports: Optional[List[str]] = None) -> None:
        from ..models import Airport
        from ..utils.field_standardization_service import FieldStandardizationService

        field_service = FieldStandardizationService()

        airports_to_process = self.filter_airports(airports)

        if airports_to_process is None:
            airports_to_process = self.find_available_airports()
        if not airports_to_process:
            logger.warning("No Austrian airports found via web index")
            return

        # Get index for PDF URLs
        index_html = self._fetch_with_cache('index')
        airport_info = self._parse_index_for_airports(index_html)

        logger.info(f"Updating model from Austria eAIP for {len(airports_to_process)} airports")

        parser = AIPParserFactory.get_parser(self.AUTHORITY, 'pdf')

        for icao in airports_to_process:
            try:
                info = airport_info.get(icao)
                if not info:
                    logger.debug(f"Skipping {icao} — not in Austria eAIP index")
                    continue

                pdf_data = self.fetch_airport_pdf(icao, url=info['url'])
                if not pdf_data:
                    continue

                if icao not in model.airports:
                    model.add_airport(Airport(ident=icao))

                airport = model.airports[icao]

                parsed_data = parser.parse(pdf_data, icao)
                if parsed_data:
                    entries = field_service.create_aip_entries_from_parsed_data(icao, parsed_data)
                    if entries:
                        airport.add_aip_entries(entries)
                        airport.add_source(self.SOURCE_NAME)

                logger.debug(f"Updated {icao} from Austria eAIP ({info['category']})")

            except Exception as e:
                logger.error(f"Error updating {icao} from Austria eAIP: {e}")
