"""Tests for OgimetSource — ogimet.com historical METAR/TAF fetcher."""

from datetime import date, datetime, timezone
from unittest.mock import MagicMock

import pytest

from euro_aip.briefing.sources.ogimet import OgimetSource
from euro_aip.briefing.weather.models import WeatherType


# Minimal ogimet-style HTML with nested tables
SAMPLE_HTML = """
<html><body>
<table>
  <table>
    <caption>METAR from EGLL, London Heathrow</caption>
    <tr><td>METAR</td><td>07/04/2026 12:50</td><td>METAR EGLL 071250Z 27010KT 9999 SCT030 BKN045 15/08 Q1020</td></tr>
    <tr><td>METAR</td><td>07/04/2026 11:50</td><td>METAR EGLL 071150Z 25008KT 9999 FEW035 14/07 Q1021</td></tr>
  </table>
  <table>
    <caption>TAF from EGLL, London Heathrow</caption>
    <tr><td>TAF</td><td>07/04/2026 11:00</td><td>TAF EGLL 071100Z 0712/0818 24012KT 9999 FEW040</td></tr>
  </table>
</table>
</body></html>
"""


class MockResponse:
    def __init__(self, text="", status_code=200):
        self.text = text
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            from requests.exceptions import HTTPError
            raise HTTPError(f"HTTP {self.status_code}")


def make_session(html="", status_code=200):
    session = MagicMock()
    session.headers = {}
    session.get.return_value = MockResponse(html, status_code)
    return session


class TestFetchHistory:
    """Test full fetch_history pipeline."""

    def test_parses_metars_and_tafs(self):
        session = make_session(SAMPLE_HTML)
        source = OgimetSource(session=session)

        reports = source.fetch_history("EGLL", date(2026, 4, 7))

        metars = [r for r in reports if r.report_type in (WeatherType.METAR, WeatherType.SPECI)]
        tafs = [r for r in reports if r.report_type == WeatherType.TAF]
        assert len(metars) == 2
        assert len(tafs) == 1

    def test_all_reports_tagged_ogimet(self):
        session = make_session(SAMPLE_HTML)
        source = OgimetSource(session=session)

        reports = source.fetch_history("EGLL", date(2026, 4, 7))
        assert all(r.source == "ogimet" for r in reports)

    def test_observation_times_from_html(self):
        session = make_session(SAMPLE_HTML)
        source = OgimetSource(session=session)

        reports = source.fetch_history("EGLL", date(2026, 4, 7))
        metars = [r for r in reports if r.report_type == WeatherType.METAR]

        times = sorted(r.observation_time for r in metars)
        assert times[0] == datetime(2026, 4, 7, 11, 50, tzinfo=timezone.utc)
        assert times[1] == datetime(2026, 4, 7, 12, 50, tzinfo=timezone.utc)

    def test_sorted_chronologically(self):
        session = make_session(SAMPLE_HTML)
        source = OgimetSource(session=session)

        reports = source.fetch_history("EGLL", date(2026, 4, 7))
        times = [r.observation_time for r in reports]
        assert times == sorted(times)

    def test_end_date_defaults_to_start(self):
        session = make_session("")
        source = OgimetSource(session=session)

        source.fetch_history("EGLL", date(2026, 4, 7))

        params = session.get.call_args[1]["params"]
        assert params["day"] == 7
        assert params["dayf"] == 7

    def test_date_range(self):
        session = make_session("")
        source = OgimetSource(session=session)

        source.fetch_history("EGLL", date(2026, 4, 1), date(2026, 4, 3))

        params = session.get.call_args[1]["params"]
        assert params["ano"] == 2026
        assert params["mes"] == 4
        assert params["day"] == 1
        assert params["dayf"] == 3


class TestFetchMetarsOnly:
    def test_filters_to_metars(self):
        session = make_session(SAMPLE_HTML)
        source = OgimetSource(session=session)

        reports = source.fetch_metars("EGLL", date(2026, 4, 7))
        assert len(reports) == 2
        assert all(r.report_type in (WeatherType.METAR, WeatherType.SPECI) for r in reports)


class TestFetchTafsOnly:
    def test_filters_to_tafs(self):
        session = make_session(SAMPLE_HTML)
        source = OgimetSource(session=session)

        reports = source.fetch_tafs("EGLL", date(2026, 4, 7))
        assert len(reports) == 1
        assert reports[0].report_type == WeatherType.TAF


class TestUrlBuilding:
    def test_url_params(self):
        session = make_session("")
        source = OgimetSource(session=session)

        source.fetch_history("EGLL", date(2026, 4, 7), date(2026, 4, 8))

        url = session.get.call_args[0][0]
        assert "display_metars2.php" in url
        params = session.get.call_args[1]["params"]
        assert params["lugar"] == "EGLL"
        assert params["tipo"] == "ALL"
        assert params["hora"] == "00"
        assert params["horaf"] == "23"


class TestErrorHandling:
    def test_http_error_returns_empty(self):
        session = make_session("", status_code=500)
        source = OgimetSource(session=session)

        reports = source.fetch_history("EGLL", date(2026, 4, 7))
        assert reports == []

    def test_connection_error_returns_empty(self):
        session = make_session()
        session.get.side_effect = Exception("Connection timeout")
        source = OgimetSource(session=session)

        reports = source.fetch_history("EGLL", date(2026, 4, 7))
        assert reports == []

    def test_empty_html_returns_empty(self):
        session = make_session("<html><body></body></html>")
        source = OgimetSource(session=session)

        reports = source.fetch_history("EGLL", date(2026, 4, 7))
        assert reports == []


class TestParseHtml:
    def test_ignores_non_weather_tables(self):
        html = """
        <html><body>
        <table>
          <table>
            <caption>Something else from EGLL, blah</caption>
            <tr><td>A</td><td>07/04/2026 12:00</td><td>not weather</td></tr>
          </table>
        </table>
        </body></html>
        """
        session = make_session(html)
        source = OgimetSource(session=session)

        reports = source.fetch_history("EGLL", date(2026, 4, 7))
        assert reports == []

    def test_skips_malformed_rows(self):
        html = """
        <html><body>
        <table>
          <table>
            <caption>METAR from EGLL, London</caption>
            <tr><td>only two cells</td><td>bad</td></tr>
            <tr><td>METAR</td><td>07/04/2026 12:50</td><td>METAR EGLL 071250Z 27010KT 9999 SCT030 15/08 Q1020</td></tr>
          </table>
        </table>
        </body></html>
        """
        session = make_session(html)
        source = OgimetSource(session=session)

        reports = source.fetch_history("EGLL", date(2026, 4, 7))
        assert len(reports) == 1
