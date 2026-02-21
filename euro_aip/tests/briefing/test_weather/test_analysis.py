"""Tests for weather analysis: flight categories, wind components."""

import pytest
from datetime import datetime

from euro_aip.briefing.weather.models import (
    WeatherReport,
    WeatherType,
    FlightCategory,
)
from euro_aip.briefing.weather.analysis import WeatherAnalyzer


class TestFlightCategory:
    """Test flight category determination."""

    def test_vfr_good_visibility_no_ceiling(self):
        report = WeatherReport(visibility_sm=10.0, ceiling_ft=None)
        assert WeatherAnalyzer.flight_category(report) == FlightCategory.VFR

    def test_vfr_good_conditions(self):
        report = WeatherReport(visibility_sm=10.0, ceiling_ft=5000)
        assert WeatherAnalyzer.flight_category(report) == FlightCategory.VFR

    def test_mvfr_visibility(self):
        """3-5 SM visibility = MVFR"""
        report = WeatherReport(visibility_sm=4.0, ceiling_ft=5000)
        assert WeatherAnalyzer.flight_category(report) == FlightCategory.MVFR

    def test_mvfr_ceiling(self):
        """1000-3000 ft ceiling = MVFR"""
        report = WeatherReport(visibility_sm=10.0, ceiling_ft=2000)
        assert WeatherAnalyzer.flight_category(report) == FlightCategory.MVFR

    def test_ifr_visibility(self):
        """1-3 SM visibility = IFR"""
        report = WeatherReport(visibility_sm=2.0, ceiling_ft=5000)
        assert WeatherAnalyzer.flight_category(report) == FlightCategory.IFR

    def test_ifr_ceiling(self):
        """500-1000 ft ceiling = IFR"""
        report = WeatherReport(visibility_sm=10.0, ceiling_ft=800)
        assert WeatherAnalyzer.flight_category(report) == FlightCategory.IFR

    def test_lifr_visibility(self):
        """< 1 SM visibility = LIFR"""
        report = WeatherReport(visibility_sm=0.5, ceiling_ft=5000)
        assert WeatherAnalyzer.flight_category(report) == FlightCategory.LIFR

    def test_lifr_ceiling(self):
        """< 500 ft ceiling = LIFR"""
        report = WeatherReport(visibility_sm=10.0, ceiling_ft=200)
        assert WeatherAnalyzer.flight_category(report) == FlightCategory.LIFR

    def test_worst_condition_wins(self):
        """When visibility says VFR but ceiling says IFR, result is IFR."""
        report = WeatherReport(visibility_sm=10.0, ceiling_ft=800)
        assert WeatherAnalyzer.flight_category(report) == FlightCategory.IFR

    def test_worst_condition_wins_reverse(self):
        """When ceiling says VFR but visibility says IFR, result is IFR."""
        report = WeatherReport(visibility_sm=2.0, ceiling_ft=5000)
        assert WeatherAnalyzer.flight_category(report) == FlightCategory.IFR

    def test_cavok_is_vfr(self):
        report = WeatherReport(cavok=True)
        assert WeatherAnalyzer.flight_category(report) == FlightCategory.VFR

    def test_no_data_returns_none(self):
        report = WeatherReport()
        assert WeatherAnalyzer.flight_category(report) is None

    def test_visibility_only(self):
        report = WeatherReport(visibility_sm=2.5)
        assert WeatherAnalyzer.flight_category(report) == FlightCategory.IFR

    def test_ceiling_only(self):
        report = WeatherReport(ceiling_ft=1500)
        assert WeatherAnalyzer.flight_category(report) == FlightCategory.MVFR

    def test_boundary_mvfr_vfr_visibility(self):
        """5 SM = MVFR (inclusive), > 5 SM = VFR"""
        assert WeatherAnalyzer.flight_category(
            WeatherReport(visibility_sm=5.0)
        ) == FlightCategory.MVFR
        assert WeatherAnalyzer.flight_category(
            WeatherReport(visibility_sm=5.1)
        ) == FlightCategory.VFR

    def test_boundary_mvfr_vfr_ceiling(self):
        """3000 ft = MVFR (inclusive), > 3000 ft = VFR"""
        assert WeatherAnalyzer.flight_category(
            WeatherReport(ceiling_ft=3000)
        ) == FlightCategory.MVFR
        assert WeatherAnalyzer.flight_category(
            WeatherReport(ceiling_ft=3100)
        ) == FlightCategory.VFR

    def test_boundary_ifr_mvfr_visibility(self):
        """3 SM = MVFR, < 3 SM = IFR"""
        assert WeatherAnalyzer.flight_category(
            WeatherReport(visibility_sm=3.0)
        ) == FlightCategory.MVFR
        assert WeatherAnalyzer.flight_category(
            WeatherReport(visibility_sm=2.9)
        ) == FlightCategory.IFR

    def test_boundary_lifr_ifr_visibility(self):
        """1 SM = IFR, < 1 SM = LIFR"""
        assert WeatherAnalyzer.flight_category(
            WeatherReport(visibility_sm=1.0)
        ) == FlightCategory.IFR
        assert WeatherAnalyzer.flight_category(
            WeatherReport(visibility_sm=0.9)
        ) == FlightCategory.LIFR


class TestWindComponents:
    """Test wind component calculations."""

    def test_direct_headwind(self):
        """Wind 270 on runway 27 = full headwind, zero crosswind."""
        report = WeatherReport(wind_direction=270, wind_speed=20)
        wc = WeatherAnalyzer.wind_components(report, 270, "27")

        assert wc is not None
        assert wc.headwind == pytest.approx(20.0, abs=1)
        assert abs(wc.crosswind) == pytest.approx(0.0, abs=1)

    def test_direct_tailwind(self):
        """Wind 090 on runway 27 = full tailwind (negative headwind)."""
        report = WeatherReport(wind_direction=90, wind_speed=20)
        wc = WeatherAnalyzer.wind_components(report, 270, "27")

        assert wc is not None
        assert wc.headwind == pytest.approx(-20.0, abs=1)
        assert abs(wc.crosswind) == pytest.approx(0.0, abs=1)

    def test_direct_crosswind_right(self):
        """Wind 360 on runway 27 = full crosswind from right."""
        report = WeatherReport(wind_direction=360, wind_speed=20)
        wc = WeatherAnalyzer.wind_components(report, 270, "27")

        assert wc is not None
        assert abs(wc.headwind) == pytest.approx(0.0, abs=1)
        assert abs(wc.crosswind) == pytest.approx(20.0, abs=1)

    def test_45_degree_wind(self):
        """Wind 315 on runway 27 = equal headwind and crosswind."""
        report = WeatherReport(wind_direction=315, wind_speed=20)
        wc = WeatherAnalyzer.wind_components(report, 270, "27")

        assert wc is not None
        # cos(45) = sin(45) ≈ 0.707
        assert wc.headwind == pytest.approx(14.1, abs=1)
        assert abs(wc.crosswind) == pytest.approx(14.1, abs=1)

    def test_calm_wind(self):
        report = WeatherReport(wind_direction=0, wind_speed=0)
        wc = WeatherAnalyzer.wind_components(report, 270, "27")

        assert wc is not None
        assert wc.headwind == 0.0
        assert wc.crosswind == 0.0

    def test_no_wind_data(self):
        report = WeatherReport()
        wc = WeatherAnalyzer.wind_components(report, 270, "27")
        assert wc is None

    def test_variable_wind_no_direction(self):
        """Variable wind with no direction → full speed as crosswind."""
        report = WeatherReport(wind_direction=None, wind_speed=10)
        wc = WeatherAnalyzer.wind_components(report, 270, "27")

        assert wc is not None
        assert wc.crosswind == 10.0
        assert wc.max_crosswind == 10.0

    def test_gust_components(self):
        report = WeatherReport(wind_direction=270, wind_speed=15, wind_gust=25)
        wc = WeatherAnalyzer.wind_components(report, 270, "27")

        assert wc is not None
        assert wc.headwind == pytest.approx(15.0, abs=1)
        assert wc.gust_headwind == pytest.approx(25.0, abs=1)

    def test_crosswind_with_variable_wind(self):
        """Variable wind should compute worst-case crosswind."""
        report = WeatherReport(
            wind_direction=270,
            wind_speed=15,
            wind_variable_from=240,
            wind_variable_to=300,
        )
        wc = WeatherAnalyzer.wind_components(report, 270, "27")

        assert wc is not None
        # Worst-case crosswind from variable range should be >= basic crosswind
        assert wc.max_crosswind is not None
        assert wc.max_crosswind >= abs(wc.crosswind)

    def test_within_limits_integration(self):
        """Wind components within_limits method works with calculated values."""
        report = WeatherReport(wind_direction=300, wind_speed=15)
        wc = WeatherAnalyzer.wind_components(report, 270, "27")

        assert wc is not None
        assert wc.within_limits(max_crosswind_kt=20, max_tailwind_kt=10)


class TestWindComponentsForRunways:
    """Test multi-runway wind component calculations."""

    def test_multiple_runways(self):
        report = WeatherReport(wind_direction=270, wind_speed=15)
        runways = {"27L": 270, "09R": 90}
        result = WeatherAnalyzer.wind_components_for_runways(report, runways)

        assert "27L" in result
        assert "09R" in result
        assert result["27L"].headwind == pytest.approx(15.0, abs=1)
        assert result["09R"].headwind == pytest.approx(-15.0, abs=1)


class TestCompareCategories:
    """Test category comparison."""

    def test_exact_match(self):
        assert WeatherAnalyzer.compare_categories(
            FlightCategory.VFR, FlightCategory.VFR
        ) == "exact"

    def test_actual_worse(self):
        assert WeatherAnalyzer.compare_categories(
            FlightCategory.IFR, FlightCategory.VFR
        ) == "worse"

    def test_actual_better(self):
        assert WeatherAnalyzer.compare_categories(
            FlightCategory.VFR, FlightCategory.IFR
        ) == "better"


class TestTafValidity:
    """Test TAF validity period matching."""

    def test_find_applicable_taf_base(self):
        """When no trends apply, returns base TAF."""
        taf = WeatherReport(
            report_type=WeatherType.TAF,
            validity_start=datetime(2024, 3, 21, 12, 0),
            validity_end=datetime(2024, 3, 22, 18, 0),
            trends=[],
        )
        result = WeatherAnalyzer.find_applicable_taf(taf, datetime(2024, 3, 21, 15, 0))
        assert result is taf

    def test_find_applicable_taf_with_tempo(self):
        """Returns applicable TEMPO trend."""
        tempo = WeatherReport(
            trend_type="TEMPO",
            validity_start=datetime(2024, 3, 21, 14, 0),
            validity_end=datetime(2024, 3, 21, 18, 0),
        )
        taf = WeatherReport(
            report_type=WeatherType.TAF,
            validity_start=datetime(2024, 3, 21, 12, 0),
            validity_end=datetime(2024, 3, 22, 18, 0),
            trends=[tempo],
        )

        # Within TEMPO validity
        result = WeatherAnalyzer.find_applicable_taf(taf, datetime(2024, 3, 21, 15, 0))
        assert result is tempo

        # Outside TEMPO validity
        result = WeatherAnalyzer.find_applicable_taf(taf, datetime(2024, 3, 21, 13, 0))
        assert result is taf

    def test_applicable_trends_multiple(self):
        """Returns all applicable trends."""
        tempo1 = WeatherReport(
            trend_type="TEMPO",
            validity_start=datetime(2024, 3, 21, 14, 0),
            validity_end=datetime(2024, 3, 21, 20, 0),
        )
        tempo2 = WeatherReport(
            trend_type="TEMPO",
            validity_start=datetime(2024, 3, 21, 16, 0),
            validity_end=datetime(2024, 3, 21, 18, 0),
        )
        taf = WeatherReport(
            report_type=WeatherType.TAF,
            trends=[tempo1, tempo2],
        )

        # Time within both trends
        result = WeatherAnalyzer.applicable_trends(taf, datetime(2024, 3, 21, 17, 0))
        assert len(result) == 2
