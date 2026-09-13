"""METAR/TAF issued under an airport's previous code are filed under its current one."""

from types import SimpleNamespace
from unittest.mock import MagicMock

from euro_aip.briefing.weather.models import FlightCategory, WeatherReport, WeatherType
from euro_aip.briefing.weather.route_weather import RouteWeatherService


def _metar(icao):
    return WeatherReport(
        icao=icao,
        report_type=WeatherType.METAR,
        raw_text=f"METAR {icao} 211230Z 24010KT 9999 FEW040 18/09 Q1015",
        flight_category=FlightCategory.VFR,
        source="avwx",
    )


def _fetch(route_icaos, nearby_airports, reports):
    model = MagicMock()
    model.find_airports_near_route.return_value = [
        {"airport": airport, "segment_distance_nm": 0.0, "enroute_distance_nm": 0.0}
        for airport in nearby_airports
    ]
    source = MagicMock()
    source.fetch_weather.return_value = reports
    result = RouteWeatherService(source=source).fetch_route_weather(
        route_icaos, corridor_nm=1, model=model,
    )
    return result, source.fetch_weather.call_args[0][0]


LOGRONO = SimpleNamespace(ident="LERJ", alt_ident="LELO", name="Logroño-Agoncillo Airport")


def test_metar_under_previous_code_is_filed_under_current_code():
    result, requested = _fetch(["LERJ"], [LOGRONO], [_metar("LELO")])

    assert set(requested) == {"LERJ", "LELO"}
    [airport] = result.airports
    assert airport.icao == "LERJ"
    assert airport.latest_metar.raw_text.startswith("METAR LELO")


def test_route_given_by_previous_code_is_not_duplicated():
    result, requested = _fetch(["LELO"], [LOGRONO], [])

    assert [a.icao for a in result.airports] == ["LERJ"]
    assert sorted(requested) == ["LELO", "LERJ"]


def test_airport_without_alias_requests_only_its_code():
    oxford = SimpleNamespace(ident="EGTK", alt_ident=None, name="Oxford")

    _, requested = _fetch(["EGTK"], [oxford], [])

    assert requested == ["EGTK"]
