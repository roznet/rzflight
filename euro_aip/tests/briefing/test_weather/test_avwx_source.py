"""Tests for AvWxSource — aviationweather.gov API fetcher."""

from unittest.mock import MagicMock, patch
import pytest

from euro_aip.briefing.sources.avwx import AvWxSource
from euro_aip.briefing.weather.models import WeatherType, FlightCategory


class MockResponse:
    """Minimal mock for requests.Response."""

    def __init__(self, text="", status_code=200, json_data=None):
        self.text = text
        self.status_code = status_code
        self._json_data = json_data

    def raise_for_status(self):
        if self.status_code >= 400:
            from requests.exceptions import HTTPError
            raise HTTPError(f"HTTP {self.status_code}")

    def json(self):
        if self._json_data is None:
            import json
            return json.loads(self.text)
        return self._json_data


def make_session(response_text="", status_code=200):
    """Create a mock session returning a fixed response."""
    session = MagicMock()
    session.headers = {}
    session.get.return_value = MockResponse(response_text, status_code)
    return session


def make_json_session(json_data, status_code=200):
    """Create a mock session returning a fixed JSON payload."""
    session = MagicMock()
    session.headers = {}
    session.get.return_value = MockResponse(status_code=status_code, json_data=json_data)
    return session


SAMPLE_ISIGMET = [
    {
        "icaoId": "EGTT",
        "firId": "EGTT",
        "firName": "LONDON",
        "validTimeFrom": "2026-05-20 10:00:00",
        "validTimeTo": "2026-05-20 14:00:00",
        "dir": "NE",
        "spd": 15,
        "hazard": "TURB",
        "qualifier": "SEV",
        "base": 10000,
        "top": 24000,
        "coords": [
            {"lat": 51.0, "lon": -2.0},
            {"lat": 52.0, "lon": -2.0},
            {"lat": 52.0, "lon": 0.0},
            {"lat": 51.0, "lon": 0.0},
            {"lat": 51.0, "lon": -2.0},
        ],
        "rawSigmet": "EGTT SIGMET 01 VALID 201000/201400 SEV TURB",
    }
]


class TestFetchIsigmet:
    """Test SIGMET fetching and parsing."""

    def test_single_sigmet(self):
        session = make_json_session(SAMPLE_ISIGMET)
        source = AvWxSource(session=session)

        sigmets = source.fetch_isigmet()

        assert len(sigmets) == 1
        assert sigmets[0].fir_id == "EGTT"
        assert sigmets[0].hazard == "TURB"
        assert sigmets[0].source == "avwx"

    def test_default_params(self):
        session = make_json_session([])
        source = AvWxSource(session=session)
        source.fetch_isigmet()

        params = session.get.call_args[1]["params"]
        assert params["format"] == "json"
        assert params["region"] == "eur"

    def test_hazard_param_forwarded(self):
        session = make_json_session([])
        source = AvWxSource(session=session)
        source.fetch_isigmet(hazard="turb")

        params = session.get.call_args[1]["params"]
        assert params["hazard"] == "turb"

    def test_level_param_forwarded(self):
        session = make_json_session([])
        source = AvWxSource(session=session)
        source.fetch_isigmet(level=10000)

        params = session.get.call_args[1]["params"]
        assert params["level"] == "10000"

    def test_204_no_content(self):
        session = make_session("", status_code=204)
        source = AvWxSource(session=session)
        assert source.fetch_isigmet() == []

    def test_http_error_returns_empty(self):
        session = make_json_session([], status_code=500)
        source = AvWxSource(session=session)
        assert source.fetch_isigmet() == []

    def test_unexpected_payload_returns_empty(self):
        session = make_json_session({"error": "bad request"})
        source = AvWxSource(session=session)
        assert source.fetch_isigmet() == []

    def test_skips_non_dict_entries(self):
        session = make_json_session([SAMPLE_ISIGMET[0], "garbage", 42])
        source = AvWxSource(session=session)
        sigmets = source.fetch_isigmet()
        assert len(sigmets) == 1


class TestFetchMetars:
    """Test METAR fetching and parsing."""

    def test_single_metar(self):
        raw = "METAR EGLL 211250Z 27010KT 9999 SCT030 BKN045 15/08 Q1020"
        session = make_session(raw)
        source = AvWxSource(session=session)

        reports = source.fetch_metars(["EGLL"])

        assert len(reports) == 1
        assert reports[0].icao == "EGLL"
        assert reports[0].report_type == WeatherType.METAR
        assert reports[0].source == "avwx"

    def test_multiple_metars(self):
        raw = (
            "METAR EGLL 211250Z 27010KT 9999 SCT030 BKN045 15/08 Q1020\n"
            "METAR LFPG 211230Z 24015KT 9999 FEW040 18/09 Q1015\n"
        )
        session = make_session(raw)
        source = AvWxSource(session=session)

        reports = source.fetch_metars(["EGLL", "LFPG"])

        assert len(reports) == 2
        icaos = {r.icao for r in reports}
        assert icaos == {"EGLL", "LFPG"}

    def test_empty_lines_skipped(self):
        raw = "\n\nMETAR EGLL 211250Z 27010KT 9999 SCT030 15/08 Q1020\n\n\n"
        session = make_session(raw)
        source = AvWxSource(session=session)

        reports = source.fetch_metars(["EGLL"])
        assert len(reports) == 1

    def test_204_no_content(self):
        session = make_session("", status_code=204)
        source = AvWxSource(session=session)

        reports = source.fetch_metars(["XXXX"])
        assert reports == []

    def test_unparseable_lines_skipped(self):
        raw = (
            "METAR EGLL 211250Z 27010KT 9999 SCT030 15/08 Q1020\n"
            "GARBAGE NOT A METAR\n"
        )
        session = make_session(raw)
        source = AvWxSource(session=session)

        reports = source.fetch_metars(["EGLL"])
        # Should get at least the valid one; garbage may or may not parse
        assert any(r.icao == "EGLL" for r in reports)

    def test_metar_hours_param(self):
        session = make_session("")
        source = AvWxSource(session=session)
        source.fetch_metars(["EGLL"], hours=6)

        call_kwargs = session.get.call_args
        assert call_kwargs[1]["params"]["hours"] == "6"

    def test_source_tag(self):
        raw = "METAR EGLL 211250Z 27010KT 9999 SCT030 15/08 Q1020"
        session = make_session(raw)
        source = AvWxSource(session=session)

        reports = source.fetch_metars(["EGLL"])
        assert reports[0].source == "avwx"


class TestFetchTafs:
    """Test TAF fetching and parsing."""

    def test_single_taf(self):
        raw = "TAF EGLL 211100Z 2112/2218 24012KT 9999 FEW040"
        session = make_session(raw)
        source = AvWxSource(session=session)

        reports = source.fetch_tafs(["EGLL"])

        assert len(reports) == 1
        assert reports[0].icao == "EGLL"
        assert reports[0].report_type == WeatherType.TAF

    def test_multiline_taf(self):
        raw = (
            "TAF EGLL 211100Z 2112/2218 24012KT 9999 FEW040\n"
            "     TEMPO 2114/2118 4000 TSRA BKN020CB\n"
        )
        session = make_session(raw)
        source = AvWxSource(session=session)

        reports = source.fetch_tafs(["EGLL"])
        assert len(reports) == 1
        assert reports[0].icao == "EGLL"

    def test_multiple_tafs(self):
        raw = (
            "TAF EGLL 211100Z 2112/2218 24012KT 9999 FEW040\n"
            "     TEMPO 2114/2118 4000 TSRA BKN020CB\n"
            "TAF LFPG 211100Z 2112/2218 18008KT 9999 SCT035\n"
        )
        session = make_session(raw)
        source = AvWxSource(session=session)

        reports = source.fetch_tafs(["EGLL", "LFPG"])
        assert len(reports) == 2
        icaos = {r.icao for r in reports}
        assert icaos == {"EGLL", "LFPG"}

    def test_204_no_content(self):
        session = make_session("", status_code=204)
        source = AvWxSource(session=session)

        reports = source.fetch_tafs(["XXXX"])
        assert reports == []


class TestSplitTafBlocks:
    """Test TAF text splitting logic."""

    def test_single_block(self):
        raw = "TAF EGLL 211100Z 2112/2218 24012KT 9999 FEW040"
        blocks = AvWxSource._split_taf_blocks(raw)
        assert len(blocks) == 1

    def test_two_blocks_by_taf_prefix(self):
        raw = (
            "TAF EGLL 211100Z 2112/2218 24012KT 9999 FEW040\n"
            "TAF LFPG 211100Z 2112/2218 18008KT 9999 SCT035\n"
        )
        blocks = AvWxSource._split_taf_blocks(raw)
        assert len(blocks) == 2

    def test_multiline_block(self):
        raw = (
            "TAF EGLL 211100Z 2112/2218 24012KT 9999 FEW040\n"
            "     TEMPO 2114/2118 4000 TSRA BKN020CB\n"
            "     BECMG 2116/2118 27015KT\n"
        )
        blocks = AvWxSource._split_taf_blocks(raw)
        assert len(blocks) == 1
        assert "TEMPO" in blocks[0]
        assert "BECMG" in blocks[0]

    def test_blank_line_separated(self):
        raw = (
            "TAF EGLL 211100Z 2112/2218 24012KT 9999 FEW040\n"
            "\n"
            "TAF LFPG 211100Z 2112/2218 18008KT 9999 SCT035\n"
        )
        blocks = AvWxSource._split_taf_blocks(raw)
        assert len(blocks) == 2

    def test_empty_input(self):
        assert AvWxSource._split_taf_blocks("") == []
        assert AvWxSource._split_taf_blocks("   ") == []
        assert AvWxSource._split_taf_blocks(None) == []


class TestBatching:
    """Test ICAO batching for large requests."""

    def test_small_list_single_batch(self):
        session = make_session("")
        source = AvWxSource(session=session)

        source.fetch_metars(["EGLL", "LFPG"])

        # Should be called once
        assert session.get.call_count == 1

    def test_large_list_multiple_batches(self):
        session = make_session("")
        source = AvWxSource(session=session)

        # 500 ICAOs should split into 2 batches (400 + 100)
        icaos = [f"X{i:03d}" for i in range(500)]
        source.fetch_metars(icaos)

        assert session.get.call_count == 2

    def test_exact_batch_size(self):
        session = make_session("")
        source = AvWxSource(session=session)

        icaos = [f"X{i:03d}" for i in range(400)]
        source.fetch_metars(icaos)

        assert session.get.call_count == 1


class TestFetchWeather:
    """Test combined METAR + TAF fetch."""

    def test_combines_metars_and_tafs(self):
        session = make_session()
        source = AvWxSource(session=session)

        # First call for metars, second for tafs
        session.get.side_effect = [
            MockResponse("METAR EGLL 211250Z 27010KT 9999 SCT030 15/08 Q1020"),
            MockResponse("TAF EGLL 211100Z 2112/2218 24012KT 9999 FEW040"),
        ]

        reports = source.fetch_weather(["EGLL"])

        metars = [r for r in reports if r.report_type in (WeatherType.METAR, WeatherType.SPECI)]
        tafs = [r for r in reports if r.report_type == WeatherType.TAF]
        assert len(metars) == 1
        assert len(tafs) == 1


class TestErrorHandling:
    """Test graceful error handling."""

    def test_http_error_returns_empty(self):
        session = make_session("", status_code=500)
        source = AvWxSource(session=session)

        reports = source.fetch_metars(["EGLL"])
        assert reports == []

    def test_request_exception_returns_empty(self):
        session = make_session()
        session.get.side_effect = Exception("Connection timeout")
        source = AvWxSource(session=session)

        reports = source.fetch_metars(["EGLL"])
        assert reports == []

    def test_icao_cleaning(self):
        session = make_session("")
        source = AvWxSource(session=session)

        source.fetch_metars(["  egll  ", "lfpg"])

        call_kwargs = session.get.call_args
        ids = call_kwargs[1]["params"]["ids"]
        assert ids == "EGLL,LFPG"
