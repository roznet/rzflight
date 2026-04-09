"""Tests for AutorouterGrametSource."""

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from euro_aip.briefing.sources.autorouter_gramet import (
    AutorouterGrametSource,
    GRAMET_URL,
)


def _make_source(token="test-token"):
    cred = MagicMock()
    cred.get_token.return_value = token
    return AutorouterGrametSource(cred)


class TestFetchGramet:
    """Tests for AutorouterGrametSource.fetch_gramet."""

    def test_returns_image_bytes(self):
        """Returns raw bytes from the API response."""
        fake_png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
        source = _make_source()

        mock_resp = MagicMock()
        mock_resp.content = fake_png
        source.session = MagicMock()
        source.session.get.return_value = mock_resp

        result = source.fetch_gramet(
            waypoints=["EGTK", "LFPB", "LSGS"],
            altitude_ft=8000,
            departure_time=datetime(2026, 2, 14, 9, 0, 0),
            duration_hours=4.5,
        )

        assert result == fake_png

    def test_sends_correct_params(self):
        """Sends correct query parameters to the API."""
        source = _make_source()
        mock_resp = MagicMock()
        mock_resp.content = b"image"
        source.session = MagicMock()
        source.session.get.return_value = mock_resp

        departure = datetime(2026, 2, 14, 9, 0, 0)
        source.fetch_gramet(
            waypoints=["EGTK", "LFPB"],
            altitude_ft=8000,
            departure_time=departure,
            duration_hours=4.5,
            fmt="pdf",
        )

        _, kwargs = source.session.get.call_args
        assert kwargs["params"]["waypoints"] == "EGTK LFPB"
        assert kwargs["params"]["altitude"] == 8000
        assert kwargs["params"]["departuretime"] == int(departure.timestamp())
        assert kwargs["params"]["totaleet"] == 16200  # 4.5h in seconds
        assert kwargs["params"]["format"] == "pdf"

    def test_sends_bearer_auth(self):
        """Sends Authorization header with bearer token."""
        source = _make_source(token="my-oauth-token")
        mock_resp = MagicMock()
        mock_resp.content = b"image"
        source.session = MagicMock()
        source.session.get.return_value = mock_resp

        source.fetch_gramet(
            waypoints=["EGTK", "LSGS"],
            altitude_ft=6000,
            departure_time=datetime(2026, 2, 14, 9, 0),
            duration_hours=3.0,
        )

        _, kwargs = source.session.get.call_args
        assert kwargs["headers"]["Authorization"] == "Bearer my-oauth-token"

    def test_raises_on_http_error(self):
        """Raises when the API returns an error status."""
        source = _make_source()
        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = Exception("403 Forbidden")
        source.session = MagicMock()
        source.session.get.return_value = mock_resp

        with pytest.raises(Exception, match="403"):
            source.fetch_gramet(
                waypoints=["EGTK", "LFPB"],
                altitude_ft=8000,
                departure_time=datetime(2026, 2, 14, 9, 0),
                duration_hours=2.0,
            )

    def test_default_format_is_png(self):
        """Default format parameter is png."""
        source = _make_source()
        mock_resp = MagicMock()
        mock_resp.content = b"image"
        source.session = MagicMock()
        source.session.get.return_value = mock_resp

        source.fetch_gramet(
            waypoints=["EGTK", "LSGS"],
            altitude_ft=6000,
            departure_time=datetime(2026, 2, 14, 9, 0),
            duration_hours=2.0,
        )

        _, kwargs = source.session.get.call_args
        assert kwargs["params"]["format"] == "png"

    def test_calls_correct_url(self):
        """Calls the GRAMET API endpoint."""
        source = _make_source()
        mock_resp = MagicMock()
        mock_resp.content = b"image"
        source.session = MagicMock()
        source.session.get.return_value = mock_resp

        source.fetch_gramet(
            waypoints=["EGTK"],
            altitude_ft=6000,
            departure_time=datetime(2026, 2, 14, 9, 0),
            duration_hours=1.0,
        )

        args, _ = source.session.get.call_args
        assert args[0] == GRAMET_URL
