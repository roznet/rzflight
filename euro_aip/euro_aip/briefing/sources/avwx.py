"""Aviation Weather (aviationweather.gov) API source for live METAR/TAF/SIGMET data."""

import logging
import time
from typing import Any, List, Optional

import requests

from euro_aip.briefing.weather.models import WeatherReport
from euro_aip.briefing.weather.parser import WeatherParser
from euro_aip.briefing.weather.sigmet import SigmetReport

logger = logging.getLogger(__name__)


class AvWxSource:
    """
    Fetch live METAR, TAF and SIGMET data from the aviationweather.gov API.

    METAR/TAF are returned as raw text and parsed via WeatherParser into
    WeatherReport objects; SIGMETs are fetched as JSON and parsed into
    SigmetReport objects. Supports batching for large ICAO lists
    (API limit ~400 per request).

    Example:
        source = AvWxSource()
        reports = source.fetch_weather(["EGLL", "LFPG"])
        for r in reports:
            print(r.icao, r.flight_category)
    """

    BASE_URL = "https://aviationweather.gov/api/data"
    BATCH_SIZE = 400
    DEFAULT_TIMEOUT = 15
    DEFAULT_MAX_RETRIES = 2
    DEFAULT_RETRY_BACKOFF = 0.5
    USER_AGENT = "euro-aip/1.0 (aviation weather tool)"

    def __init__(
        self,
        session: Optional[requests.Session] = None,
        timeout: int = DEFAULT_TIMEOUT,
        max_retries: int = DEFAULT_MAX_RETRIES,
        retry_backoff: float = DEFAULT_RETRY_BACKOFF,
    ):
        """
        Args:
            session: Optional requests.Session for dependency injection (testing).
            timeout: HTTP request timeout in seconds.
            max_retries: Extra attempts on transient failures (timeouts,
                connection errors, 5xx). 0 disables retrying.
            retry_backoff: Base seconds for linear backoff between attempts
                (attempt N waits ``retry_backoff * N``).
        """
        self._session = session or requests.Session()
        self._timeout = timeout
        self._max_retries = max(0, max_retries)
        self._retry_backoff = retry_backoff
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

    def fetch_isigmet(
        self,
        region: str = "eur",
        hazard: Optional[str] = None,
        level: Optional[int] = None,
        date: Optional[str] = None,
    ) -> List[SigmetReport]:
        """
        Fetch international (FIR) SIGMETs from the isigmet endpoint.

        Args:
            region: Region code, kept for forward-compatibility. NB: the AWC
                isigmet endpoint currently ignores it and always returns the
                global SIGMET set — filter geographically on the client
                (RouteSigmetService does this via route geometry).
            hazard: Optional hazard filter (server-side), e.g. ``"turb"``,
                ``"ice"`` or ``"conv"``.
            level: Optional flight-level filter (server-side), in hundreds of
                feet — e.g. ``100`` means FL100 (10,000 ft), not 100 ft. Matches
                SIGMETs whose vertical band brackets that level.
            date: Optional ISO timestamp to query historical SIGMETs.

        Returns:
            List of parsed SigmetReport objects. Empty on any fetch/parse failure.
        """
        params: dict = {"format": "json"}
        if region:
            params["region"] = region
        if hazard:
            params["hazard"] = hazard
        if level is not None:
            params["level"] = str(level)
        if date:
            params["date"] = date

        payload = self._fetch_json("isigmet", params)
        if not isinstance(payload, list):
            if payload:
                logger.warning("AvWx isigmet returned unexpected payload type: %s", type(payload))
            return []

        reports = []
        for entry in payload:
            if not isinstance(entry, dict):
                continue
            try:
                reports.append(SigmetReport.from_awc(entry, source="avwx"))
            except Exception as e:
                logger.warning("Failed to parse SIGMET entry: %s", e)
        return reports

    def _get_with_retry(self, url: str, params: dict) -> requests.Response:
        """GET ``url`` with retries on transient failures.

        aviationweather.gov intermittently read-times-out; because METAR/TAF
        are fetched in batches of up to ``BATCH_SIZE``, a single un-retried
        timeout silently drops a whole batch of airports for that ingest cycle.
        Retries cover connection errors, read timeouts, and 5xx responses
        (4xx are returned as-is — retrying a client error won't help). Raises
        the last exception if every attempt fails, so callers keep their
        existing fail-open (return empty) behaviour.
        """
        last_exc: Exception = RuntimeError("no request attempted")
        for attempt in range(self._max_retries + 1):
            try:
                response = self._session.get(url, params=params, timeout=self._timeout)
                if response.status_code < 500:
                    return response
                last_exc = requests.HTTPError(
                    f"{response.status_code} Server Error", response=response,
                )
            except requests.RequestException as e:
                last_exc = e
            if attempt < self._max_retries:
                logger.debug(
                    "AvWx GET attempt %d/%d failed (%s) — retrying",
                    attempt + 1, self._max_retries + 1, last_exc,
                )
                time.sleep(self._retry_backoff * (attempt + 1))
        raise last_exc

    def _fetch_raw(self, endpoint: str, params: dict) -> str:
        """
        Make HTTP GET request and return raw text.

        Handles 204 (no data) by returning empty string.
        """
        url = f"{self.BASE_URL}/{endpoint}"
        try:
            response = self._get_with_retry(url, params)
            if response.status_code == 204:
                return ""
            response.raise_for_status()
            return response.text
        except Exception as e:
            logger.warning("AvWx fetch failed for %s: %s", endpoint, e)
            return ""

    def _fetch_json(self, endpoint: str, params: dict) -> Any:
        """
        Make HTTP GET request and return parsed JSON.

        Handles 204 (no data) by returning an empty list. Returns an empty list
        on any request or decode failure, matching the graceful-failure pattern
        of the raw-text fetchers.
        """
        url = f"{self.BASE_URL}/{endpoint}"
        try:
            response = self._get_with_retry(url, params)
            if response.status_code == 204:
                return []
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.warning("AvWx JSON fetch failed for %s: %s", endpoint, e)
            return []

    def _batches(self, icaos: List[str]):
        """Yield batches of valid ICAOs respecting the API batch size limit.

        Drops anything that isn't a 4-letter ICAO code. The API returns HTTP 400
        for the whole request if a single id is malformed (e.g. a lat/lon route
        waypoint like ``5117N00009E``), which would silently zero out every
        airport in the batch — so non-ICAO ids are filtered out before sending.
        """
        cleaned = []
        for icao in icaos:
            token = icao.strip().upper()
            if not token:
                continue
            if len(token) == 4 and token.isalpha():
                cleaned.append(token)
            else:
                logger.debug("AvWx skipping non-ICAO id: %r", token)
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
