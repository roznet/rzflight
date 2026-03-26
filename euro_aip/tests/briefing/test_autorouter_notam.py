"""Tests for AutorouterNotamSource."""

import pytest
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock

from euro_aip.briefing.sources.autorouter_notam import AutorouterNotamSource
from euro_aip.briefing.models.notam import NotamCategory


# Sample API response row matching the Autorouter NOTAM API format
SAMPLE_ROW = {
    "id": 123456,
    "series": "A",
    "number": 1234,
    "year": 2024,
    "fir": "LFFF",
    "itema": "LFPG",
    "iteme": "RWY 09L/27R CLSD DUE TO MAINTENANCE",
    "code23": "MR",
    "code45": "LC",
    "traffic": "IV",
    "purpose": "NBO",
    "scope": "A",
    "lower": 0,
    "upper": 999,
    "lat": 49.01,
    "lon": 2.55,
    "startvalidity": 1711929600,  # 2024-04-01 00:00:00 UTC
    "endvalidity": 1711972800,    # 2024-04-01 12:00:00 UTC
    "suppressed": False,
    "type": "N",
    "nof": "LFFA",
    "modified": 1711900000,
}

SAMPLE_PERMANENT_ROW = {
    "id": 789,
    "series": "C",
    "number": 42,
    "year": 2024,
    "fir": "EGTT",
    "itema": "EGLL",
    "iteme": "CRANE ERECTED AT 512800N 0001200W",
    "code23": "OB",
    "code45": "CE",
    "traffic": "IV",
    "purpose": "BO",
    "scope": "W",
    "lower": 0,
    "upper": 20,
    "lat": 51.47,
    "lon": -0.20,
    "startvalidity": 1711929600,
    "endvalidity": 0,  # permanent
    "suppressed": False,
    "type": "N",
    "nof": "EGFA",
    "modified": 1711900000,
}

SAMPLE_NO_COORDS_ROW = {
    "id": 456,
    "series": "B",
    "number": 99,
    "year": 2024,
    "fir": "EDGG",
    "itema": "EDGG",
    "iteme": "FIR FRANKFURT NOTAM TEXT",
    "code23": "AF",
    "code45": "AH",
    "traffic": "I",
    "purpose": "N",
    "scope": "E",
    "lower": 0,
    "upper": 999,
    "lat": None,
    "lon": None,
    "startvalidity": 1711929600,
    "endvalidity": 1712016000,
    "suppressed": False,
    "type": "N",
    "nof": "EDFA",
    "modified": 1711900000,
}


class TestRowToNotam:
    """Tests for _row_to_notam field mapping."""

    def test_basic_field_mapping(self):
        """Test that all fields are correctly mapped from API row."""
        notam = AutorouterNotamSource._row_to_notam(SAMPLE_ROW)

        assert notam.id == "A1234/24"
        assert notam.location == "LFPG"
        assert notam.fir == "LFFF"
        assert notam.message == "RWY 09L/27R CLSD DUE TO MAINTENANCE"
        assert notam.raw_text == notam.message
        assert notam.series == "A"
        assert notam.number == 1234
        assert notam.year == 2024
        assert notam.source == "autorouter"

    def test_q_code_reconstruction(self):
        """Test Q-code is reconstructed from code23 + code45."""
        notam = AutorouterNotamSource._row_to_notam(SAMPLE_ROW)

        assert notam.q_code == "QMRLC"
        assert notam.category == NotamCategory.AGA_MOVEMENT

    def test_q_line_fields(self):
        """Test traffic, purpose, scope are mapped."""
        notam = AutorouterNotamSource._row_to_notam(SAMPLE_ROW)

        assert notam.traffic_type == "IV"
        assert notam.purpose == "NBO"
        assert notam.scope == "A"

    def test_altitude_conversion(self):
        """Test flight levels are converted to feet (FL * 100)."""
        notam = AutorouterNotamSource._row_to_notam(SAMPLE_ROW)

        assert notam.lower_limit == 0
        assert notam.upper_limit == 99900  # FL999 * 100

    def test_coordinates(self):
        """Test coordinates are mapped as (lat, lon) tuple."""
        notam = AutorouterNotamSource._row_to_notam(SAMPLE_ROW)

        assert notam.coordinates == (49.01, 2.55)

    def test_no_coordinates(self):
        """Test missing coordinates result in None."""
        notam = AutorouterNotamSource._row_to_notam(SAMPLE_NO_COORDS_ROW)

        assert notam.coordinates is None

    def test_validity_times(self):
        """Test unix epoch times are converted to UTC datetimes."""
        notam = AutorouterNotamSource._row_to_notam(SAMPLE_ROW)

        assert notam.effective_from is not None
        assert notam.effective_from.tzinfo == timezone.utc
        assert notam.effective_from == datetime(2024, 4, 1, 0, 0, 0, tzinfo=timezone.utc)
        assert notam.effective_to is not None
        assert notam.effective_to == datetime(2024, 4, 1, 12, 0, 0, tzinfo=timezone.utc)
        assert notam.is_permanent is False

    def test_permanent_notam(self):
        """Test endvalidity=0 is treated as permanent."""
        notam = AutorouterNotamSource._row_to_notam(SAMPLE_PERMANENT_ROW)

        assert notam.is_permanent is True
        assert notam.effective_to is None

    def test_obstacle_category(self):
        """Test obstacle Q-code (OB) maps to OTHER_INFO category."""
        notam = AutorouterNotamSource._row_to_notam(SAMPLE_PERMANENT_ROW)

        assert notam.q_code == "QOBCE"
        assert notam.category == NotamCategory.OTHER_INFO

    def test_missing_q_code_fields(self):
        """Test graceful handling when code23/code45 are empty."""
        row = {**SAMPLE_ROW, "code23": "", "code45": ""}
        notam = AutorouterNotamSource._row_to_notam(row)

        assert notam.q_code is None
        assert notam.category is None


class TestFetchNotams:
    """Tests for fetch_notams pagination and deduplication."""

    def _make_source(self):
        """Create a source with mock credentials."""
        cred_mgr = MagicMock()
        cred_mgr.get_token.return_value = "mock-token"
        return AutorouterNotamSource(cred_mgr)

    @patch("euro_aip.briefing.sources.autorouter_notam.requests.get")
    def test_single_page(self, mock_get):
        """Test fetching when all results fit in one page."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "total": 2,
            "rows": [SAMPLE_ROW, SAMPLE_PERMANENT_ROW],
        }
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        source = self._make_source()
        notams = source.fetch_notams(["LFPG", "EGLL"])

        assert len(notams) == 2
        assert notams[0].id == "A1234/24"
        assert notams[1].location == "EGLL"
        mock_get.assert_called_once()

    @patch("euro_aip.briefing.sources.autorouter_notam.requests.get")
    def test_pagination(self, mock_get):
        """Test automatic pagination when results exceed page limit."""
        # First page: 100 items (triggers next page)
        page1_rows = [{**SAMPLE_ROW, "number": i, "id": i} for i in range(100)]
        # Second page: 50 items (done)
        page2_rows = [{**SAMPLE_ROW, "number": i + 100, "id": i + 100} for i in range(50)]

        mock_responses = [
            MagicMock(
                status_code=200,
                json=MagicMock(return_value={"total": 150, "rows": page1_rows}),
                raise_for_status=MagicMock(),
            ),
            MagicMock(
                status_code=200,
                json=MagicMock(return_value={"total": 150, "rows": page2_rows}),
                raise_for_status=MagicMock(),
            ),
        ]
        mock_get.side_effect = mock_responses

        source = self._make_source()
        notams = source.fetch_notams(["LFPG"])

        assert len(notams) == 150
        assert mock_get.call_count == 2

    @patch("euro_aip.briefing.sources.autorouter_notam.requests.get")
    def test_deduplication(self, mock_get):
        """Test that duplicate NOTAMs (same id) are removed."""
        # Same NOTAM appearing for two different query codes
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "total": 2,
            "rows": [SAMPLE_ROW, SAMPLE_ROW],  # duplicate
        }
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        source = self._make_source()
        notams = source.fetch_notams(["LFPG"])

        assert len(notams) == 1

    @patch("euro_aip.briefing.sources.autorouter_notam.requests.get")
    def test_empty_icaos(self, mock_get):
        """Test empty ICAO list returns empty result."""
        source = self._make_source()
        notams = source.fetch_notams([])

        assert notams == []
        mock_get.assert_not_called()

    @patch("euro_aip.briefing.sources.autorouter_notam.requests.get")
    def test_validity_time_params(self, mock_get):
        """Test that validity time params are passed to API."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"total": 0, "rows": []}
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        source = self._make_source()
        start = datetime(2024, 4, 1, tzinfo=timezone.utc)
        end = datetime(2024, 4, 2, tzinfo=timezone.utc)
        source.fetch_notams(["LFPG"], start_validity=start, end_validity=end)

        call_params = mock_get.call_args[1]["params"]
        assert call_params["startvalidity"] == int(start.timestamp())
        assert call_params["endvalidity"] == int(end.timestamp())
