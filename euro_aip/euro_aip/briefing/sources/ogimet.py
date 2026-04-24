"""Ogimet historical METAR/TAF source.

Fetches historical METAR and TAF data from ogimet.com by scraping
the display_metars2.php HTML pages. Supports date ranges for a single
ICAO airport, which is the natural access pattern for ogimet.

Example:
    source = OgimetSource()
    reports = source.fetch_history("EGLL", date(2026, 4, 1), date(2026, 4, 3))
"""

import logging
import re
from datetime import date, datetime, timezone
from typing import List, Optional

import requests
from bs4 import BeautifulSoup

from euro_aip.briefing.weather.models import WeatherReport
from euro_aip.briefing.weather.parser import WeatherParser

logger = logging.getLogger(__name__)


class OgimetSource:
    """
    Fetch historical METAR/TAF data from ogimet.com.

    Ogimet provides historical weather reports for a single airport
    over a date range. This complements AvWxSource (live, multi-airport)
    by providing historical data access.

    Example:
        source = OgimetSource()
        reports = source.fetch_history("EGLL", date(2026, 4, 1), date(2026, 4, 3))
        for r in reports:
            print(r.icao, r.observation_time, r.flight_category)
    """

    BASE_URL = "https://www.ogimet.com/display_metars2.php"
    FORM_URL = "https://www.ogimet.com/metars.phtml.en"
    DEFAULT_TIMEOUT = 30
    # Ogimet returns an empty stub page to non-browser clients. A realistic UA
    # plus a warm-up visit to the form page (which sets ogimet_serverid) is
    # required to get actual data.
    USER_AGENT = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/122.0 Safari/537.36"
    )

    def __init__(
        self,
        session: Optional[requests.Session] = None,
        timeout: int = DEFAULT_TIMEOUT,
    ):
        self._session = session or requests.Session()
        self._timeout = timeout
        self._warmed_up = False
        self._session.headers.setdefault("User-Agent", self.USER_AGENT)
        self._session.headers.setdefault(
            "Accept",
            "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        )
        self._session.headers.setdefault("Accept-Language", "en-US,en;q=0.9")

    def fetch_history(
        self,
        icao: str,
        start_date: date,
        end_date: Optional[date] = None,
    ) -> List[WeatherReport]:
        """
        Fetch historical METAR and TAF reports for an airport.

        Args:
            icao: ICAO airport code (e.g. "EGLL").
            start_date: Start date (inclusive).
            end_date: End date (inclusive). Defaults to start_date (single day).

        Returns:
            List of WeatherReport objects sorted chronologically.
        """
        if end_date is None:
            end_date = start_date
        icao = icao.strip().upper()

        html = self._fetch_html(icao, start_date, end_date)
        if not html:
            return []

        raw_reports = self._parse_html(html)
        return self._to_weather_reports(raw_reports)

    def fetch_metars(
        self,
        icao: str,
        start_date: date,
        end_date: Optional[date] = None,
    ) -> List[WeatherReport]:
        """Fetch only METARs (and SPECIs) for the given date range."""
        reports = self.fetch_history(icao, start_date, end_date)
        return [r for r in reports if r.report_type.value in ("METAR", "SPECI")]

    def fetch_tafs(
        self,
        icao: str,
        start_date: date,
        end_date: Optional[date] = None,
    ) -> List[WeatherReport]:
        """Fetch only TAFs for the given date range."""
        reports = self.fetch_history(icao, start_date, end_date)
        return [r for r in reports if r.report_type.value == "TAF"]

    def _fetch_html(self, icao: str, start_date: date, end_date: date) -> str:
        """Fetch raw HTML from ogimet."""
        params = {
            "lang": "en",
            "lugar": icao,
            "tipo": "ALL",
            "ord": "REV",
            "nil": "SI",
            "fmt": "html",
            "ano": start_date.year,
            "mes": start_date.month,
            "day": start_date.day,
            "hora": "00",
            "anof": end_date.year,
            "mesf": end_date.month,
            "dayf": end_date.day,
            "horaf": "23",
            "minf": "59",
            "send": "send",
        }
        try:
            self._ensure_warmed_up()
            response = self._session.get(
                self.BASE_URL,
                params=params,
                timeout=self._timeout,
                headers={"Referer": self.FORM_URL},
            )
            if response.status_code == 204:
                return ""
            response.raise_for_status()
            return response.text
        except Exception as e:
            logger.warning("Ogimet fetch failed for %s: %s", icao, e)
            return ""

    def _ensure_warmed_up(self) -> None:
        """Visit the form page once per session to pick up ogimet_serverid.

        Without this cookie ogimet returns an empty page skeleton instead
        of METAR data, regardless of User-Agent.
        """
        if self._warmed_up:
            return
        try:
            self._session.get(self.FORM_URL, timeout=self._timeout)
        except Exception as e:
            logger.debug("Ogimet warm-up failed (continuing): %s", e)
        self._warmed_up = True

    def _parse_html(self, html: str) -> List[dict]:
        """
        Parse ogimet HTML into raw report dicts.

        Ogimet returns nested tables with captions like
        "METAR from EGLL, ..." or "TAF from EGLL, ...".
        Each row has 3 cells: [source_type, datetime, report_text].
        """
        soup = BeautifulSoup(html, "html.parser")
        reports = []
        icao_pattern = re.compile(r"from ([A-Z]{4}),")

        for table in soup.find_all("table"):
            if not table.find_parent("table"):
                continue
            caption = table.find("caption")
            if not caption:
                continue
            caption_text = caption.get_text()
            match = icao_pattern.search(caption_text)
            if not match:
                continue

            icao = match.group(1)
            if "METAR" not in caption_text and "TAF" not in caption_text:
                continue

            for row in table.find_all("tr"):
                cells = [c.get_text() for c in row.find_all(["td", "th"])]
                if len(cells) != 3:
                    continue
                report_type = "METAR" if "METAR" in cells[2] else "TAF"
                try:
                    dt = datetime.strptime(
                        cells[1].split("->")[0], "%d/%m/%Y %H:%M"
                    ).replace(tzinfo=timezone.utc)
                except ValueError:
                    continue
                reports.append({
                    "icao": icao,
                    "report_datetime": dt,
                    "report_type": report_type,
                    "report_data": cells[2],
                })

        return reports

    def _to_weather_reports(self, raw_reports: List[dict]) -> List[WeatherReport]:
        """Convert raw parsed dicts to WeatherReport objects."""
        results = []
        for raw in raw_reports:
            text = raw["report_data"]
            ref_time = raw["report_datetime"]

            if raw["report_type"] == "TAF":
                report = WeatherParser.parse_taf(text, source="ogimet")
            else:
                report = WeatherParser.parse_metar(text, source="ogimet")

            if not report:
                continue

            # Override observation_time with the datetime from ogimet
            # (more reliable than what the parser infers from day/hour)
            report.observation_time = ref_time

            # Fix validity dates for historical data: the parser uses
            # datetime.now() for year/month, but we need the actual date
            self._fix_validity_dates(report, ref_time)

            results.append(report)

        # Sort chronologically
        results.sort(key=lambda r: r.observation_time or datetime.min.replace(tzinfo=timezone.utc))
        return results

    @staticmethod
    def _fix_validity_dates(report: WeatherReport, ref_time: datetime) -> None:
        """Fix year/month on validity dates that the parser built from now().

        The metar_taf_parser only gets day/hour from TAF validity strings
        (e.g. 1518/1624), so the parser fills in year/month from now().
        For historical data we replace year/month based on the actual
        report time from ogimet.
        """
        def _adjust(dt: Optional[datetime]) -> Optional[datetime]:
            if dt is None:
                return None
            try:
                return dt.replace(year=ref_time.year, month=ref_time.month)
            except ValueError:
                # Day doesn't exist in target month — likely spans to next month
                next_month = ref_time.month % 12 + 1
                next_year = ref_time.year + (1 if next_month == 1 else 0)
                try:
                    return dt.replace(year=next_year, month=next_month)
                except ValueError:
                    return dt

        report.validity_start = _adjust(report.validity_start)
        report.validity_end = _adjust(report.validity_end)

        for trend in report.trends:
            trend.validity_start = _adjust(trend.validity_start)
            trend.validity_end = _adjust(trend.validity_end)
            if (
                trend.validity_start
                and trend.validity_end
                and trend.validity_end < trend.validity_start
            ):
                next_month = trend.validity_start.month % 12 + 1
                next_year = trend.validity_start.year + (1 if next_month == 1 else 0)
                try:
                    trend.validity_end = trend.validity_end.replace(
                        year=next_year, month=next_month
                    )
                except ValueError:
                    pass
