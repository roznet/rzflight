"""Tests for weather models: serialization, FlightCategory ordering."""

import pytest
from datetime import datetime

from euro_aip.briefing.weather.models import (
    FlightCategory,
    WeatherType,
    WindComponents,
    WeatherReport,
)


class TestFlightCategory:
    """Test FlightCategory enum ordering."""

    def test_ordering_lifr_worst(self):
        assert FlightCategory.LIFR < FlightCategory.IFR
        assert FlightCategory.LIFR < FlightCategory.MVFR
        assert FlightCategory.LIFR < FlightCategory.VFR

    def test_ordering_vfr_best(self):
        assert FlightCategory.VFR > FlightCategory.MVFR
        assert FlightCategory.VFR > FlightCategory.IFR
        assert FlightCategory.VFR > FlightCategory.LIFR

    def test_ordering_equality(self):
        assert FlightCategory.IFR <= FlightCategory.IFR
        assert FlightCategory.IFR >= FlightCategory.IFR
        assert not (FlightCategory.IFR < FlightCategory.IFR)
        assert not (FlightCategory.IFR > FlightCategory.IFR)

    def test_ordering_adjacent(self):
        assert FlightCategory.LIFR < FlightCategory.IFR
        assert FlightCategory.IFR < FlightCategory.MVFR
        assert FlightCategory.MVFR < FlightCategory.VFR

    def test_order_property(self):
        assert FlightCategory.LIFR.order == 0
        assert FlightCategory.IFR.order == 1
        assert FlightCategory.MVFR.order == 2
        assert FlightCategory.VFR.order == 3

    def test_min_returns_worst(self):
        assert min(FlightCategory.VFR, FlightCategory.IFR) == FlightCategory.IFR
        assert min(FlightCategory.MVFR, FlightCategory.LIFR) == FlightCategory.LIFR

    def test_sorting(self):
        cats = [FlightCategory.VFR, FlightCategory.LIFR, FlightCategory.MVFR, FlightCategory.IFR]
        sorted_cats = sorted(cats)
        assert sorted_cats == [
            FlightCategory.LIFR,
            FlightCategory.IFR,
            FlightCategory.MVFR,
            FlightCategory.VFR,
        ]


class TestWindComponents:
    """Test WindComponents dataclass."""

    def test_within_limits_ok(self):
        wc = WindComponents(
            runway_ident="27",
            runway_heading=270,
            headwind=15.0,
            crosswind=10.0,
            crosswind_direction="right",
        )
        assert wc.within_limits(max_crosswind_kt=20, max_tailwind_kt=10)

    def test_within_limits_crosswind_exceeded(self):
        wc = WindComponents(
            runway_ident="27",
            runway_heading=270,
            headwind=5.0,
            crosswind=25.0,
            crosswind_direction="right",
        )
        assert not wc.within_limits(max_crosswind_kt=20)

    def test_within_limits_tailwind(self):
        wc = WindComponents(
            runway_ident="27",
            runway_heading=270,
            headwind=-15.0,  # tailwind
            crosswind=5.0,
            crosswind_direction="left",
        )
        assert not wc.within_limits(max_tailwind_kt=10)

    def test_within_limits_gust_crosswind(self):
        wc = WindComponents(
            runway_ident="27",
            runway_heading=270,
            headwind=10.0,
            crosswind=15.0,
            crosswind_direction="right",
            gust_crosswind=25.0,
        )
        assert not wc.within_limits(max_crosswind_kt=20)

    def test_serialization_roundtrip(self):
        wc = WindComponents(
            runway_ident="09L",
            runway_heading=90,
            headwind=12.0,
            crosswind=-8.0,
            crosswind_direction="left",
            gust_headwind=18.0,
            gust_crosswind=-12.0,
            max_crosswind=12.0,
        )
        d = wc.to_dict()
        wc2 = WindComponents.from_dict(d)
        assert wc2.runway_ident == "09L"
        assert wc2.headwind == 12.0
        assert wc2.gust_headwind == 18.0
        assert wc2.max_crosswind == 12.0


class TestWeatherReport:
    """Test WeatherReport serialization."""

    def test_serialization_roundtrip(self):
        report = WeatherReport(
            icao="LFPG",
            report_type=WeatherType.METAR,
            raw_text="METAR LFPG 211230Z 24015G25KT 9999 FEW040 18/09 Q1015",
            observation_time=datetime(2024, 3, 21, 12, 30),
            wind_direction=240,
            wind_speed=15,
            wind_gust=25,
            wind_unit="KT",
            visibility_meters=9999,
            visibility_sm=6.21,
            ceiling_ft=None,
            cavok=False,
            clouds=[{'quantity': 'FEW', 'height': 4000, 'type': None}],
            weather_conditions=[],
            temperature=18,
            dewpoint=9,
            altimeter=1015.0,
            flight_category=FlightCategory.VFR,
            source="test",
        )

        d = report.to_dict()
        assert d['icao'] == "LFPG"
        assert d['report_type'] == "METAR"
        assert d['flight_category'] == "VFR"
        assert d['wind_gust'] == 25
        assert d['observation_time'] == "2024-03-21T12:30:00"

        report2 = WeatherReport.from_dict(d)
        assert report2.icao == "LFPG"
        assert report2.report_type == WeatherType.METAR
        assert report2.flight_category == FlightCategory.VFR
        assert report2.wind_gust == 25
        assert report2.observation_time == datetime(2024, 3, 21, 12, 30)
        assert report2.clouds == [{'quantity': 'FEW', 'height': 4000, 'type': None}]

    def test_serialization_with_trends(self):
        trend = WeatherReport(
            icao="LFPG",
            report_type=WeatherType.TAF,
            trend_type="TEMPO",
            visibility_meters=3000,
            visibility_sm=1.86,
            flight_category=FlightCategory.IFR,
        )
        taf = WeatherReport(
            icao="LFPG",
            report_type=WeatherType.TAF,
            raw_text="TAF ...",
            trends=[trend],
            flight_category=FlightCategory.VFR,
        )

        d = taf.to_dict()
        assert len(d['trends']) == 1
        assert d['trends'][0]['trend_type'] == "TEMPO"
        assert d['trends'][0]['flight_category'] == "IFR"

        taf2 = WeatherReport.from_dict(d)
        assert len(taf2.trends) == 1
        assert taf2.trends[0].trend_type == "TEMPO"
        assert taf2.trends[0].flight_category == FlightCategory.IFR

    def test_from_dict_missing_fields(self):
        """from_dict handles missing fields gracefully."""
        report = WeatherReport.from_dict({'icao': 'EGLL'})
        assert report.icao == "EGLL"
        assert report.report_type == WeatherType.METAR
        assert report.flight_category is None
        assert report.trends == []
        assert report.clouds == []

    def test_repr(self):
        report = WeatherReport(
            icao="LFPG",
            report_type=WeatherType.METAR,
            flight_category=FlightCategory.VFR,
        )
        assert "METAR" in repr(report)
        assert "LFPG" in repr(report)
        assert "VFR" in repr(report)
