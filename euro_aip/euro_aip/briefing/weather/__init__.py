"""
Weather module for parsing and analyzing METAR/TAF reports.

Provides:
- WeatherReport: Parsed METAR or TAF data
- FlightCategory: VFR/MVFR/IFR/LIFR enum with ordering
- WindComponents: Headwind/crosswind calculations
- WeatherType: METAR/SPECI/TAF enum
- WeatherParser: Parse raw METAR/TAF text
- WeatherAnalyzer: Flight categories, wind components, TAF matching
- WeatherCollection: Queryable collection with aviation weather filters

Example:
    from euro_aip.briefing.weather import WeatherReport, FlightCategory

    report = WeatherReport.from_metar(
        "METAR LFPG 211230Z 24015G25KT 9999 FEW040 18/09 Q1015"
    )
    print(report.flight_category)  # FlightCategory.VFR
    print(report.wind_components(270, "27"))  # WindComponents(...)
"""

from euro_aip.briefing.weather.models import (
    WeatherReport,
    FlightCategory,
    WindComponents,
    WeatherType,
)
from euro_aip.briefing.weather.parser import WeatherParser
from euro_aip.briefing.weather.analysis import WeatherAnalyzer
from euro_aip.briefing.weather.collection import WeatherCollection
from euro_aip.briefing.weather.route_weather import (
    RouteWeatherService,
    RouteWeatherResult,
    RouteAirportWeather,
)

__all__ = [
    'WeatherReport',
    'FlightCategory',
    'WindComponents',
    'WeatherType',
    'WeatherParser',
    'WeatherAnalyzer',
    'WeatherCollection',
    'RouteWeatherService',
    'RouteWeatherResult',
    'RouteAirportWeather',
]
