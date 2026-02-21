"""Tests for weather collection filtering."""

import pytest
from datetime import datetime

from euro_aip.briefing.weather.models import (
    WeatherReport,
    WeatherType,
    FlightCategory,
)
from euro_aip.briefing.weather.collection import WeatherCollection


def _make_reports():
    """Create test reports."""
    return [
        WeatherReport(
            icao="LFPG",
            report_type=WeatherType.METAR,
            observation_time=datetime(2024, 3, 21, 12, 30),
            wind_direction=240,
            wind_speed=15,
            visibility_sm=10.0,
            flight_category=FlightCategory.VFR,
        ),
        WeatherReport(
            icao="LFPG",
            report_type=WeatherType.TAF,
            observation_time=datetime(2024, 3, 21, 11, 0),
            wind_direction=240,
            wind_speed=12,
            visibility_sm=10.0,
            flight_category=FlightCategory.VFR,
        ),
        WeatherReport(
            icao="EGLL",
            report_type=WeatherType.METAR,
            observation_time=datetime(2024, 3, 21, 12, 50),
            wind_direction=270,
            wind_speed=20,
            visibility_sm=2.0,
            ceiling_ft=800,
            flight_category=FlightCategory.IFR,
        ),
        WeatherReport(
            icao="EGLL",
            report_type=WeatherType.SPECI,
            observation_time=datetime(2024, 3, 21, 13, 0),
            wind_direction=280,
            wind_speed=25,
            wind_gust=35,
            visibility_sm=0.5,
            ceiling_ft=200,
            flight_category=FlightCategory.LIFR,
        ),
        WeatherReport(
            icao="LFBO",
            report_type=WeatherType.METAR,
            observation_time=datetime(2024, 3, 21, 12, 30),
            wind_direction=180,
            wind_speed=8,
            visibility_sm=4.0,
            ceiling_ft=2500,
            flight_category=FlightCategory.MVFR,
        ),
    ]


class TestTypeFilters:
    def test_metars_includes_speci(self):
        coll = WeatherCollection(_make_reports())
        metars = coll.metars()
        assert metars.count() == 4  # 3 METARs + 1 SPECI
        for r in metars:
            assert r.report_type in (WeatherType.METAR, WeatherType.SPECI)

    def test_tafs(self):
        coll = WeatherCollection(_make_reports())
        tafs = coll.tafs()
        assert tafs.count() == 1
        assert tafs.first().report_type == WeatherType.TAF


class TestLocationFilters:
    def test_for_airport(self):
        coll = WeatherCollection(_make_reports())
        lfpg = coll.for_airport("LFPG")
        assert lfpg.count() == 2
        for r in lfpg:
            assert r.icao == "LFPG"

    def test_for_airport_case_insensitive(self):
        coll = WeatherCollection(_make_reports())
        assert coll.for_airport("lfpg").count() == 2

    def test_for_airports(self):
        coll = WeatherCollection(_make_reports())
        result = coll.for_airports(["LFPG", "EGLL"])
        assert result.count() == 4

    def test_group_by_airport(self):
        coll = WeatherCollection(_make_reports())
        groups = coll.group_by_airport()
        assert "LFPG" in groups
        assert "EGLL" in groups
        assert "LFBO" in groups
        assert groups["LFPG"].count() == 2


class TestCategoryFilters:
    def test_by_category(self):
        coll = WeatherCollection(_make_reports())
        vfr = coll.by_category(FlightCategory.VFR)
        assert vfr.count() == 2

    def test_worse_than(self):
        coll = WeatherCollection(_make_reports())
        worse = coll.worse_than(FlightCategory.MVFR)
        assert worse.count() == 2  # IFR + LIFR
        for r in worse:
            assert r.flight_category < FlightCategory.MVFR

    def test_at_or_worse_than(self):
        coll = WeatherCollection(_make_reports())
        result = coll.at_or_worse_than(FlightCategory.MVFR)
        assert result.count() == 3  # MVFR + IFR + LIFR
        for r in result:
            assert r.flight_category <= FlightCategory.MVFR


class TestTimeFilters:
    def test_latest(self):
        coll = WeatherCollection(_make_reports())
        latest = coll.latest()
        assert latest is not None
        assert latest.icao == "EGLL"
        assert latest.report_type == WeatherType.SPECI

    def test_latest_for_airport(self):
        coll = WeatherCollection(_make_reports())
        latest = coll.metars().for_airport("LFPG").latest()
        assert latest is not None
        assert latest.icao == "LFPG"

    def test_before(self):
        coll = WeatherCollection(_make_reports())
        before = coll.before(datetime(2024, 3, 21, 12, 0))
        assert before.count() == 1  # TAF at 11:00

    def test_after(self):
        coll = WeatherCollection(_make_reports())
        after = coll.after(datetime(2024, 3, 21, 12, 45))
        assert after.count() == 2  # EGLL METAR at 12:50, SPECI at 13:00

    def test_between(self):
        coll = WeatherCollection(_make_reports())
        result = coll.between(
            datetime(2024, 3, 21, 12, 0),
            datetime(2024, 3, 21, 12, 40),
        )
        assert result.count() == 2  # LFPG METAR + LFBO METAR at 12:30

    def test_chronological(self):
        coll = WeatherCollection(_make_reports())
        chrono = coll.chronological()
        times = [r.observation_time for r in chrono if r.observation_time]
        for i in range(1, len(times)):
            assert times[i] >= times[i - 1]


class TestWindFilters:
    def test_crosswind_exceeds(self):
        coll = WeatherCollection(_make_reports())
        # EGLL SPECI has 25G35KT from 280 on a 270 runway heading
        # That's nearly all headwind, minimal crosswind
        # Test with runway 360 where 280° wind gives significant crosswind
        exceeds = coll.crosswind_exceeds(360, 5)
        assert exceeds.count() > 0


class TestSetOperations:
    def test_union(self):
        coll = WeatherCollection(_make_reports())
        lfpg = coll.for_airport("LFPG")
        egll = coll.for_airport("EGLL")
        combined = lfpg | egll
        assert combined.count() == 4

    def test_intersection(self):
        coll = WeatherCollection(_make_reports())
        metars = coll.metars()
        lfpg = coll.for_airport("LFPG")
        result = metars & lfpg
        assert result.count() == 1  # Only LFPG METAR (not TAF)

    def test_difference(self):
        coll = WeatherCollection(_make_reports())
        all_metars = coll.metars()
        lfpg = coll.for_airport("LFPG")
        result = all_metars - lfpg
        assert result.count() == 3  # All metars/speci except LFPG


class TestChaining:
    def test_fluent_chain(self):
        coll = WeatherCollection(_make_reports())
        result = (
            coll
            .metars()
            .for_airport("EGLL")
            .at_or_worse_than(FlightCategory.IFR)
            .all()
        )
        assert len(result) == 2  # EGLL METAR (IFR) + SPECI (LIFR)

    def test_empty_collection(self):
        coll = WeatherCollection([])
        assert coll.metars().count() == 0
        assert coll.latest() is None
        assert coll.for_airport("LFPG").count() == 0
