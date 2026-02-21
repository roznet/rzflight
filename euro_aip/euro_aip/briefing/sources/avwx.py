"""Aviation Weather (aviationweather.gov) API source for live METAR/TAF data."""

import logging
from typing import List, Optional

import requests

from euro_aip.briefing.weather.models import WeatherReport
from euro_aip.briefing.weather.parser import WeatherParser

logger = logging.getLogger(__name__)


class AvWxSource:
    """
    Fetch live METAR and TAF data from the aviationweather.gov API.

    Returns raw text format, parsed via WeatherParser into WeatherReport objects.
    Supports batching for large ICAO lists (API limit ~400 per request).

    Example:
        source = AvWxSource()
        reports = source.fetch_weather(["EGLL", "LFPG"])
        for r in reports:
            print(r.icao, r.flight_category)
    """

    BASE_URL = "https://aviationweather.gov/api/data"
    BATCH_SIZE = 400
    DEFAULT_TIMEOUT = 15
    USER_AGENT = "euro-aip/1.0 (aviation weather tool)"

    def __init__(self, session: Optional[requests.Session] = None, timeout: int = DEFAULT_TIMEOUT):
        """
        Args:
            session: Optional requests.Session for dependency injection (testing).
            timeout: HTTP request timeout in seconds.
        """
        self._session = session or requests.Session()
        self._timeout = timeout
        self._session.headers.setdefault("User-Agent", self.USER_AGENT)

    def fetch_metars(self, icaos: List[str], hours: float = 3) -> List[WeatherReport]:
        """
        Fetch METARs for a list of airports.

        Args:
            icaos: List of ICAO airport codes.
            hours: Number of hours of history to fetch (default 3).

        Returns:
            List of parsed WeatherReport objects (METARs/SPECIs).
        """
        reports = []
        for batch in self._batches(icaos):
            raw = self._fetch_raw("metar", {
                "ids": ",".join(batch),
                "format": "raw",
                "hours": str(hours),
            })
            for line in raw.splitlines():
                line = line.strip()
                if not line:
                    continue
                report = WeatherParser.parse_metar(line, source="avwx")
                if report:
                    reports.append(report)
        return reports

    def fetch_tafs(self, icaos: List[str]) -> List[WeatherReport]:
        """
        Fetch TAFs for a list of airports.

        Args:
            icaos: List of ICAO airport codes.

        Returns:
            List of parsed WeatherReport objects (TAFs).
        """
        reports = []
        for batch in self._batches(icaos):
            raw = self._fetch_raw("taf", {
                "ids": ",".join(batch),
                "format": "raw",
            })
            for block in self._split_taf_blocks(raw):
                block = block.strip()
                if not block:
                    continue
                report = WeatherParser.parse_taf(block, source="avwx")
                if report:
                    reports.append(report)
        return reports

    def fetch_weather(self, icaos: List[str], metar_hours: float = 3) -> List[WeatherReport]:
        """
        Fetch both METARs and TAFs for a list of airports.

        Args:
            icaos: List of ICAO airport codes.
            metar_hours: Hours of METAR history to fetch.

        Returns:
            Combined list of WeatherReport objects.
        """
        metars = self.fetch_metars(icaos, hours=metar_hours)
        tafs = self.fetch_tafs(icaos)
        return metars + tafs

    def _fetch_raw(self, endpoint: str, params: dict) -> str:
        """
        Make HTTP GET request and return raw text.

        Handles 204 (no data) by returning empty string.
        """
        url = f"{self.BASE_URL}/{endpoint}"
        try:
            response = self._session.get(url, params=params, timeout=self._timeout)
            if response.status_code == 204:
                return ""
            response.raise_for_status()
            return response.text
        except Exception as e:
            logger.warning("AvWx fetch failed for %s: %s", endpoint, e)
            return ""

    def _batches(self, icaos: List[str]):
        """Yield batches of ICAOs respecting the API batch size limit."""
        cleaned = [icao.strip().upper() for icao in icaos if icao.strip()]
        for i in range(0, len(cleaned), self.BATCH_SIZE):
            yield cleaned[i:i + self.BATCH_SIZE]

    @staticmethod
    def _split_taf_blocks(raw_text: str) -> List[str]:
        """
        Split multi-TAF raw text into individual TAF blocks.

        The API returns TAFs separated by blank lines or TAF headers.
        Each TAF may span multiple lines (continuation lines).
        """
        if not raw_text or not raw_text.strip():
            return []

        blocks = []
        current = []

        for line in raw_text.splitlines():
            stripped = line.strip()
            if not stripped:
                # Blank line ends current block
                if current:
                    blocks.append("\n".join(current))
                    current = []
                continue

            if stripped.startswith("TAF") and current:
                # New TAF starts — flush previous
                blocks.append("\n".join(current))
                current = [stripped]
            else:
                current.append(stripped)

        if current:
            blocks.append("\n".join(current))

        return blocks
