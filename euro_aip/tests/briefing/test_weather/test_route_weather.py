"""Tests for RouteWeatherService."""

from unittest.mock import MagicMock, patch
import pytest

from euro_aip.briefing.weather.route_weather import (
    RouteAirportWeather,
    RouteWeatherResult,
    RouteWeatherService,
)
from euro_aip.briefing.weather.collection import WeatherCollection
from euro_aip.briefing.weather.models import WeatherReport, WeatherType, FlightCategory


def make_metar(icao, category=FlightCategory.VFR):
    """Create a minimal WeatherReport for testing."""
    report = WeatherReport(
        icao=icao,
        report_type=WeatherType.METAR,
        raw_text=f"METAR {icao} 211230Z 24010KT 9999 FEW040 18/09 Q1015",
        flight_category=category,
        source="avwx",
    )
    return report


def make_taf(icao):
    """Create a minimal TAF report for testing."""
    return WeatherReport(
        icao=icao,
        report_type=WeatherType.TAF,
        raw_text=f"TAF {icao} 211100Z 2112/2218 24012KT 9999 FEW040",
        source="avwx",
    )


def make_airport(icao, name=None):
    """Create a mock airport object."""
    airport = MagicMock()
    airport.ident = icao
    airport.name = name or f"Airport {icao}"
    return airport


def make_model(nearby_airports):
    """Create a mock EuroAipModel with find_airports_near_route results."""
    model = MagicMock()
    model.find_airports_near_route.return_value = nearby_airports
    return model


def make_source(reports):
    """Create a mock AvWxSource that returns given reports."""
    source = MagicMock()
    source.fetch_weather.return_value = reports
    return source


class TestRouteAirportWeather:
    """Test RouteAirportWeather dataclass."""

    def test_has_weather_empty(self):
        apt = RouteAirportWeather(
            icao="EGLL", name="Heathrow",
            distance_from_route_nm=0.0, enroute_distance_nm=0.0,
        )
        assert not apt.has_weather

    def test_has_weather_with_reports(self):
        apt = RouteAirportWeather(
            icao="EGLL", name="Heathrow",
            distance_from_route_nm=0.0, enroute_distance_nm=0.0,
            reports=WeatherCollection([make_metar("EGLL")]),
        )
        assert apt.has_weather

    def test_latest_metar(self):
        metar = make_metar("EGLL")
        apt = RouteAirportWeather(
            icao="EGLL", name="Heathrow",
            distance_from_route_nm=0.0, enroute_distance_nm=0.0,
            reports=WeatherCollection([metar, make_taf("EGLL")]),
        )
        assert apt.latest_metar is not None
        assert apt.latest_metar.report_type == WeatherType.METAR

    def test_latest_taf(self):
        taf = make_taf("EGLL")
        apt = RouteAirportWeather(
            icao="EGLL", name="Heathrow",
            distance_from_route_nm=0.0, enroute_distance_nm=0.0,
            reports=WeatherCollection([make_metar("EGLL"), taf]),
        )
        assert apt.latest_taf is not None
        assert apt.latest_taf.report_type == WeatherType.TAF


class TestRouteWeatherResult:
    """Test RouteWeatherResult dataclass."""

    def test_airports_with_weather(self):
        apt_wx = RouteAirportWeather(
            icao="EGLL", name="Heathrow",
            distance_from_route_nm=0.0, enroute_distance_nm=0.0,
            reports=WeatherCollection([make_metar("EGLL")]),
        )
        apt_no_wx = RouteAirportWeather(
            icao="EGLF", name="Farnborough",
            distance_from_route_nm=10.0, enroute_distance_nm=20.0,
        )
        result = RouteWeatherResult(
            route_icaos=["EGLL", "LFPG"],
            corridor_nm=25,
            airports=[apt_wx, apt_no_wx],
        )
        assert len(result.airports_with_weather) == 1
        assert result.airports_with_weather[0].icao == "EGLL"

    def test_collection_merges_all_reports(self):
        apt1 = RouteAirportWeather(
            icao="EGLL", name="Heathrow",
            distance_from_route_nm=0.0, enroute_distance_nm=0.0,
            reports=WeatherCollection([make_metar("EGLL")]),
        )
        apt2 = RouteAirportWeather(
            icao="LFPG", name="CDG",
            distance_from_route_nm=0.0, enroute_distance_nm=100.0,
            reports=WeatherCollection([make_metar("LFPG"), make_taf("LFPG")]),
        )
        result = RouteWeatherResult(
            route_icaos=["EGLL", "LFPG"],
            corridor_nm=25,
            airports=[apt1, apt2],
        )
        assert len(result.collection) == 3


class TestRouteWeatherService:
    """Test RouteWeatherService orchestration."""

    def test_basic_route(self):
        nearby = [
            {"airport": make_airport("EGLL", "Heathrow"),
             "segment_distance_nm": 0.0, "enroute_distance_nm": 0.0},
            {"airport": make_airport("EGLF", "Farnborough"),
             "segment_distance_nm": 15.0, "enroute_distance_nm": 30.0},
            {"airport": make_airport("LFPG", "CDG"),
             "segment_distance_nm": 0.0, "enroute_distance_nm": 190.0},
        ]
        model = make_model(nearby)
        reports = [make_metar("EGLL"), make_metar("LFPG"), make_taf("EGLL")]
        source = make_source(reports)

        service = RouteWeatherService(source=source)
        result = service.fetch_route_weather(
            ["EGLL", "LFPG"], corridor_nm=25, model=model,
        )

        assert len(result.airports) == 3
        assert result.route_icaos == ["EGLL", "LFPG"]
        assert result.corridor_nm == 25

    def test_sorted_by_enroute_distance(self):
        nearby = [
            {"airport": make_airport("LFPG"), "segment_distance_nm": 0.0,
             "enroute_distance_nm": 190.0},
            {"airport": make_airport("EGLF"), "segment_distance_nm": 15.0,
             "enroute_distance_nm": 30.0},
            {"airport": make_airport("EGLL"), "segment_distance_nm": 0.0,
             "enroute_distance_nm": 0.0},
        ]
        model = make_model(nearby)
        source = make_source([])

        service = RouteWeatherService(source=source)
        result = service.fetch_route_weather(
            ["EGLL", "LFPG"], corridor_nm=25, model=model,
        )

        distances = [a.enroute_distance_nm for a in result.airports]
        assert distances == sorted(distances)

    def test_route_airports_always_included(self):
        """Route endpoints should appear even if not in model results."""
        nearby = [
            {"airport": make_airport("EGLF"), "segment_distance_nm": 15.0,
             "enroute_distance_nm": 30.0},
        ]
        model = make_model(nearby)
        source = make_source([make_metar("EGLL")])

        service = RouteWeatherService(source=source)
        result = service.fetch_route_weather(
            ["EGLL", "LFPG"], corridor_nm=25, model=model,
        )

        icaos = {a.icao for a in result.airports}
        assert "EGLL" in icaos
        assert "LFPG" in icaos

    def test_reports_distributed_by_icao(self):
        nearby = [
            {"airport": make_airport("EGLL"), "segment_distance_nm": 0.0,
             "enroute_distance_nm": 0.0},
            {"airport": make_airport("LFPG"), "segment_distance_nm": 0.0,
             "enroute_distance_nm": 190.0},
        ]
        model = make_model(nearby)
        reports = [
            make_metar("EGLL"),
            make_metar("LFPG"),
            make_taf("EGLL"),
        ]
        source = make_source(reports)

        service = RouteWeatherService(source=source)
        result = service.fetch_route_weather(
            ["EGLL", "LFPG"], corridor_nm=25, model=model,
        )

        egll = next(a for a in result.airports if a.icao == "EGLL")
        lfpg = next(a for a in result.airports if a.icao == "LFPG")

        assert len(egll.reports) == 2  # 1 METAR + 1 TAF
        assert len(lfpg.reports) == 1  # 1 METAR

    def test_airports_without_weather_in_result(self):
        """Airports with no weather still appear but has_weather is False."""
        nearby = [
            {"airport": make_airport("EGLL"), "segment_distance_nm": 0.0,
             "enroute_distance_nm": 0.0},
            {"airport": make_airport("EGLF"), "segment_distance_nm": 15.0,
             "enroute_distance_nm": 30.0},
        ]
        model = make_model(nearby)
        source = make_source([make_metar("EGLL")])

        service = RouteWeatherService(source=source)
        result = service.fetch_route_weather(
            ["EGLL", "LFPG"], corridor_nm=25, model=model,
        )

        eglf = next(a for a in result.airports if a.icao == "EGLF")
        assert not eglf.has_weather


class TestFetchAirportsWeather:
    """Test simple multi-airport fetch (no spatial query)."""

    def test_returns_collection(self):
        reports = [make_metar("EGLL"), make_metar("LFPG")]
        source = make_source(reports)

        service = RouteWeatherService(source=source)
        collection = service.fetch_airports_weather(["EGLL", "LFPG"])

        assert len(collection) == 2

    def test_lazy_source_creation(self):
        """Source is created lazily if not provided."""
        service = RouteWeatherService()
        # Access the source getter without actually calling the API
        with patch("euro_aip.briefing.sources.avwx.AvWxSource") as mock_cls:
            mock_instance = MagicMock()
            mock_instance.fetch_weather.return_value = []
            mock_cls.return_value = mock_instance

            service.fetch_airports_weather(["EGLL"])
            mock_cls.assert_called_once()
