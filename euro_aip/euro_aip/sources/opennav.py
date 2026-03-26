"""
OpenNav waypoint source.

Fetches named waypoints from opennav.com, which provides per-country
waypoint lists covering all published fixes (not just FRA-significant ones).
Complements the Eurocontrol FRA source with broader coverage.

URL pattern: https://opennav.com/waypoint/{country_code}
Country codes are ISO alpha-2, except UK (not GB) for United Kingdom.
"""

import logging
import re
from typing import Dict, List, Optional

import requests

from ..models.euro_aip_model import EuroAipModel
from ..models.waypoint import Waypoint
from ..utils.dms_parser import parse_dms
from .base import SourceInterface
from .cached import CachedSource

logger = logging.getLogger(__name__)

BASE_URL = "https://opennav.com/waypoint"

# European country codes to fetch (ISO alpha-2)
# OpenNav uses "UK" instead of "GB"
EUROPEAN_COUNTRIES = [
    "AT",  # Austria
    "BE",  # Belgium
    "BG",  # Bulgaria
    "CH",  # Switzerland
    "CY",  # Cyprus
    "CZ",  # Czech Republic
    "DE",  # Germany
    "DK",  # Denmark
    "EE",  # Estonia
    "ES",  # Spain
    "FI",  # Finland
    "FR",  # France
    "GR",  # Greece
    "HR",  # Croatia
    "HU",  # Hungary
    "IE",  # Ireland
    "IS",  # Iceland
    "IT",  # Italy
    "LT",  # Lithuania
    "LU",  # Luxembourg
    "LV",  # Latvia
    "MT",  # Malta
    "NL",  # Netherlands
    "NO",  # Norway
    "PL",  # Poland
    "PT",  # Portugal
    "RO",  # Romania
    "SE",  # Sweden
    "SI",  # Slovenia
    "SK",  # Slovakia
    "TR",  # Turkey
    "UK",  # United Kingdom (not GB!)
]

# Regex to extract table rows. OpenNav has spacer <td> columns between data columns:
# <tr><td><a href="...">IDENT</a></td><td class="layout_col50">&nbsp;</td><td>LAT</td><td ...>&nbsp;</td><td>LON</td></tr>
_ROW_PATTERN = re.compile(
    r'<tr>\s*<td>\s*<a[^>]*>([^<]+)</a>\s*</td>'   # IDENT
    r'(?:\s*<td[^>]*>[^<]*</td>)*?'                  # spacer td(s)
    r'\s*<td>(\d+°[^<]+)</td>'                        # LAT (starts with digits°)
    r'(?:\s*<td[^>]*>[^<]*</td>)*?'                  # spacer td(s)
    r'\s*<td>(\d+°[^<]+)</td>'                        # LON (starts with digits°)
    r'\s*</tr>',
    re.IGNORECASE,
)


class OpenNavSource(CachedSource, SourceInterface):
    """Source for OpenNav waypoint data.

    Fetches per-country waypoint pages and parses the HTML table.
    All waypoints on a country page are on a single page (no pagination).
    """

    def __init__(self, cache_dir: str, countries: Optional[List[str]] = None):
        """
        Args:
            cache_dir: Directory for caching downloaded pages.
            countries: List of country codes to fetch. Defaults to EUROPEAN_COUNTRIES.
        """
        super().__init__(cache_dir)
        self.countries = countries or EUROPEAN_COUNTRIES

    def update_model(self, model: EuroAipModel, airports: Optional[List[str]] = None) -> None:
        """Update the model with OpenNav waypoints for all configured countries."""
        all_waypoints = self.get_waypoints()
        result = model.bulk_add_waypoints(all_waypoints)
        logger.info(
            "OpenNav: added %d, updated %d waypoints from %d countries",
            result["added"], result["updated"], len(self.countries),
        )

    def get_waypoints(self, max_age_days: int = 28) -> List[Waypoint]:
        """Get waypoints from all configured countries."""
        all_waypoints: Dict[str, Waypoint] = {}

        for country in self.countries:
            try:
                country_wps = self._get_country_waypoints(country, max_age_days)
                for wp in country_wps:
                    if wp.name not in all_waypoints:
                        all_waypoints[wp.name] = wp
                    else:
                        # Merge: waypoint exists from another country, keep first
                        pass
                logger.info("OpenNav %s: %d waypoints", country, len(country_wps))
            except Exception as e:
                logger.warning("OpenNav %s: failed to fetch: %s", country, e)

        logger.info("OpenNav total: %d unique waypoints from %d countries",
                     len(all_waypoints), len(self.countries))
        return list(all_waypoints.values())

    def _get_country_waypoints(self, country: str, max_age_days: int) -> List[Waypoint]:
        """Get waypoints for a single country, using cache if available."""
        cache_key = f"waypoints_{country}"
        cache_file = self._get_cache_file(cache_key, "html")
        is_valid, reason = self._is_cache_valid(cache_file, max_age_days)

        if is_valid:
            html = cache_file.read_text(encoding="utf-8")
        else:
            html = self._download_country(country)
            if html:
                cache_file.write_text(html, encoding="utf-8")

        if not html:
            return []

        return self._parse_html(html, country)

    def _download_country(self, country: str) -> Optional[str]:
        """Download the waypoint page for a country."""
        url = f"{BASE_URL}/{country}"
        try:
            response = requests.get(url, timeout=30)
            if response.status_code == 404:
                logger.debug("OpenNav: no page for %s", country)
                return None
            response.raise_for_status()
            return response.text
        except requests.RequestException as e:
            logger.warning("OpenNav: failed to download %s: %s", country, e)
            return None

    def _parse_html(self, html: str, country: str) -> List[Waypoint]:
        """Parse waypoints from the HTML table."""
        waypoints = []

        for match in _ROW_PATTERN.finditer(html):
            ident = match.group(1).strip().upper()
            lat_str = match.group(2).strip()
            lon_str = match.group(3).strip()

            if not ident or not lat_str or not lon_str:
                continue

            try:
                lat = parse_dms(lat_str)
                lon = parse_dms(lon_str)
            except ValueError as e:
                logger.debug("OpenNav %s/%s: coordinate parse error: %s", country, ident, e)
                continue

            # Classify point type by name length convention
            # 5-letter = 5LNC fix, 2-3 letter = likely NAVAID
            if len(ident) == 5 and ident.isalpha():
                point_type = "5LNC"
            else:
                point_type = None  # Unknown — could be NAVAID or procedural fix

            waypoints.append(Waypoint(
                name=ident,
                latitude_deg=lat,
                longitude_deg=lon,
                point_type=point_type,
                source="opennav",
            ))

        return waypoints
