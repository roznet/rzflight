"""Aviation Weather (aviationweather.gov) API source for live METAR/TAF/SIGMET data."""

import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

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
    #: Default spacing of the isigmet lookahead queries (see ``fetch_isigmet``).
    DEFAULT_SIGMET_LOOKAHEAD_STEP = timedelta(minutes=30)

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
        lookahead: Optional[timedelta] = None,
        step: timedelta = DEFAULT_SIGMET_LOOKAHEAD_STEP,
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
            lookahead: Also return SIGMETs already issued but not yet valid,
                up to this far ahead (ICAO: up to 4 h before validity starts,
                12 h for volcanic ash / tropical cyclone). None (default) makes
                the single query of old.
            step: Spacing of the lookahead queries. A pending SIGMET valid for
                less than ``step`` can fall between two of them.

        AWC's isigmet lists only the SIGMETs valid *at the query time* (``date``,
        default now): one issued at 06:32 to start at 07:00 is absent from a
        06:45 query. Its ``date`` parameter does accept a future time, and then
        returns the SIGMETs that will be valid then — all of them already
        received by AWC, i.e. genuinely issued (checked 2026-10-05: ``now+1h``
        gave 40 not-yet-valid SIGMETs; all 35 checked had ``receiptTime <= now``).
        Whether AWC rounds or caches ``date`` has not been checked.
        The lookahead adds queries at ``date = base + k·step`` (k = 1…n,
        ``n·step <= lookahead``, base = ``date`` or now) and merges them in:

        - The base query stays and is the source of truth for what is valid
          now. A shifted query alone would drop a SIGMET expiring before it.
        - A failed base query returns ``[]`` as before, and no lookahead query
          is made. A failed lookahead query is logged and ends the lookahead
          (the upstream is likely unhealthy; its slow timeouts would otherwise
          add up): the base result and the steps already made are kept.
          Lookahead queries are not retried.
        - Entries are deduplicated on ``(firId, seriesId, validTimeFrom)``,
          falling back to ``rawSigmet``: a SIGMET valid now is listed by
          every step until it expires. Base entries come first.

        Returns:
            List of parsed SigmetReport objects. Empty on any fetch/parse
            failure of the base query.
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

        try:
            entries = self._isigmet_entries(params)
        except Exception as e:
            logger.warning("AvWx JSON fetch failed for isigmet: %s", e)
            return []

        if lookahead is not None and lookahead > timedelta(0):
            entries = self._merge_lookahead(entries, params, date, lookahead, step)

        reports = []
        for entry in entries:
            try:
                reports.append(SigmetReport.from_awc(entry, source="avwx"))
            except Exception as e:
                logger.warning("Failed to parse SIGMET entry: %s", e)
        return reports

    def _isigmet_entries(self, params: dict, max_retries: Optional[int] = None) -> List[Dict[str, Any]]:
        """The isigmet JSON objects for one query. Raises on a failed request;
        an unexpected payload (not a list) is logged and reads as empty."""
        payload = self._get_json("isigmet", params, max_retries=max_retries)
        if not isinstance(payload, list):
            if payload:
                logger.warning("AvWx isigmet returned unexpected payload type: %s", type(payload))
            return []
        return [e for e in payload if isinstance(e, dict)]

    def _merge_lookahead(
        self,
        entries: List[Dict[str, Any]],
        params: dict,
        date: Optional[str],
        lookahead: timedelta,
        step: timedelta,
    ) -> List[Dict[str, Any]]:
        """``entries`` plus the lookahead queries' new entries (see fetch_isigmet)."""
        if step <= timedelta(0):
            raise ValueError("isigmet lookahead step must be positive")
        base = _parse_query_time(date) if date else datetime.now(timezone.utc)
        merged = list(entries)
        seen = {_isigmet_identity(e) for e in entries}
        n = int(lookahead / step)
        for k in range(1, n + 1):
            at = base + k * step
            try:
                step_entries = self._isigmet_entries(
                    {**params, "date": at.strftime("%Y-%m-%dT%H:%M:%SZ")}, max_retries=0,
                )
            except Exception as e:
                logger.warning(
                    "AvWx isigmet lookahead failed at +%s (%s); keeping %d SIGMET(s) "
                    "from the earlier queries", k * step, e, len(merged),
                )
                break
            for e in step_entries:
                ident = _isigmet_identity(e)
                if ident not in seen:
                    seen.add(ident)
                    merged.append(e)
        return merged

    def _get_with_retry(
        self, url: str, params: dict, max_retries: Optional[int] = None,
    ) -> requests.Response:
        """GET ``url`` with retries on transient failures.

        aviationweather.gov intermittently read-times-out; because METAR/TAF
        are fetched in batches of up to ``BATCH_SIZE``, a single un-retried
        timeout silently drops a whole batch of airports for that ingest cycle.
        Retries cover connection errors, read timeouts, and 5xx responses
        (4xx are returned as-is — retrying a client error won't help). Raises
        the last exception if every attempt fails, so callers keep their
        existing fail-open (return empty) behaviour. ``max_retries`` overrides
        the instance's setting for this call.
        """
        retries = self._max_retries if max_retries is None else max(0, max_retries)
        last_exc: Exception = RuntimeError("no request attempted")
        for attempt in range(retries + 1):
            try:
                response = self._session.get(url, params=params, timeout=self._timeout)
                if response.status_code < 500:
                    return response
                last_exc = requests.HTTPError(
                    f"{response.status_code} Server Error", response=response,
                )
            except requests.RequestException as e:
                last_exc = e
            if attempt < retries:
                logger.debug(
                    "AvWx GET attempt %d/%d failed (%s) — retrying",
                    attempt + 1, retries + 1, last_exc,
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

    def _get_json(self, endpoint: str, params: dict, max_retries: Optional[int] = None) -> Any:
        """HTTP GET returning parsed JSON; 204 (no data) is an empty list.
        Raises on a request or decode failure."""
        url = f"{self.BASE_URL}/{endpoint}"
        response = self._get_with_retry(url, params, max_retries=max_retries)
        if response.status_code == 204:
            return []
        response.raise_for_status()
        return response.json()

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


def _isigmet_identity(entry: Dict[str, Any]) -> tuple:
    """One SIGMET across isigmet queries: FIR + series + validity start, else
    its raw text."""
    fir, series, start = entry.get("firId"), entry.get("seriesId"), entry.get("validTimeFrom")
    if fir and series and start is not None:
        return ("id", fir, series, start)
    return ("raw", entry.get("rawSigmet") or entry.get("rawAirSigmet") or repr(sorted(entry.items(), key=lambda kv: kv[0])))


def _parse_query_time(value: str) -> datetime:
    """An isigmet ``date`` string as an aware UTC datetime."""
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)
