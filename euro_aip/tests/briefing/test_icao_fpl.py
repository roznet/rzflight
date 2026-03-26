"""Tests for ICAO Flight Plan parser."""

import pytest
from datetime import date, time, timezone, datetime

from euro_aip.briefing.models.icao_fpl import (
    parse_icao_fpl,
    ICAOFlightPlan,
    _parse_altitude,
)
from euro_aip.utils.dms_parser import parse_icao_coordinate, is_icao_coordinate


# ========================================================================
# Sample FPL strings
# ========================================================================

SAMPLE_FPL = """(FPL-N122DR-VG
-S22T/L-SBDGORVY/LB2
-LFAT0930
-N0166VFR DCT LYD DCT VESAN 4830N00210E DCT
-EGTF0033 EGLL
-PBN/B2C2D2 DOF/260318 RMK/FIKI EQUIPPED)"""

SAMPLE_FPL_IFR = """(FPL-GZIPM-IS
-C172/L-S/C
-EGTF1030
-N0110F065 HAZEL UL9 ORTAC L28 DINARD
-LFAT0130
-DOF/260326 PBN/D2)"""

SAMPLE_FPL_MINIMAL = """(FPL-GABCD-VG
-PA28/L
-EGLL0800
-N0120VFR DCT
-EGSS0025
-0)"""

SAMPLE_FPL_METRIC_SPEED = """(FPL-HBXYZ-VG
-P28A/L-S/C
-LSGG0900
-K0200A055 DCT GVA DCT
-LSZH0045
-DOF/260401)"""


# ========================================================================
# ICAO Coordinate Parser Tests
# ========================================================================

class TestICAOCoordinate:
    """Tests for parse_icao_coordinate and is_icao_coordinate."""

    def test_degrees_minutes(self):
        """4830N00210E → 48.5, 2.1667"""
        lat, lon = parse_icao_coordinate("4830N00210E")
        assert abs(lat - 48.5) < 0.001
        assert abs(lon - 2.1667) < 0.001

    def test_degrees_minutes_south_west(self):
        """3345S05830W → -33.75, -58.5"""
        lat, lon = parse_icao_coordinate("3345S05830W")
        assert lat < 0
        assert lon < 0
        assert abs(lat - (-33.75)) < 0.001
        assert abs(lon - (-58.5)) < 0.001

    def test_degrees_minutes_seconds(self):
        """483012N0021034E → (48.5033, 2.1761)"""
        lat, lon = parse_icao_coordinate("483012N0021034E")
        assert abs(lat - 48.5033) < 0.001
        assert abs(lon - 2.1761) < 0.001

    def test_is_icao_coordinate(self):
        assert is_icao_coordinate("4830N00210E")
        assert is_icao_coordinate("483012N0021034E")
        assert not is_icao_coordinate("VESAN")
        assert not is_icao_coordinate("DCT")
        assert not is_icao_coordinate("L613")
        assert not is_icao_coordinate("N0166")

    def test_invalid_raises(self):
        with pytest.raises(ValueError):
            parse_icao_coordinate("INVALID")

    def test_zero_coords(self):
        lat, lon = parse_icao_coordinate("0000N00000E")
        assert lat == 0.0
        assert lon == 0.0


# ========================================================================
# Field Parsing Tests
# ========================================================================

class TestFPLParsing:
    """Tests for full FPL parsing."""

    def test_returns_none_for_no_fpl(self):
        assert parse_icao_fpl("no flight plan here") is None

    def test_returns_none_for_empty(self):
        assert parse_icao_fpl("") is None

    def test_basic_parse(self):
        """Test full FPL parse with all fields."""
        fpl = parse_icao_fpl(SAMPLE_FPL)
        assert fpl is not None
        assert fpl.aircraft_registration == "N122DR"
        assert fpl.aircraft_type == "S22T"
        assert fpl.flight_rules == "V"
        assert fpl.flight_type == "G"

    def test_departure(self):
        fpl = parse_icao_fpl(SAMPLE_FPL)
        assert fpl.route.departure == "LFAT"

    def test_departure_time(self):
        fpl = parse_icao_fpl(SAMPLE_FPL)
        assert fpl.departure_time_utc == time(9, 30)

    def test_destination(self):
        fpl = parse_icao_fpl(SAMPLE_FPL)
        assert fpl.route.destination == "EGTF"

    def test_eet(self):
        fpl = parse_icao_fpl(SAMPLE_FPL)
        assert fpl.eet_minutes == 33

    def test_alternates(self):
        fpl = parse_icao_fpl(SAMPLE_FPL)
        assert fpl.route.alternates == ["EGLL"]

    def test_speed(self):
        fpl = parse_icao_fpl(SAMPLE_FPL)
        assert fpl.speed == "N0166"
        assert fpl.speed_knots == 166

    def test_vfr_level(self):
        fpl = parse_icao_fpl(SAMPLE_FPL)
        assert fpl.level == "VFR"
        assert fpl.altitude_feet is None

    def test_equipment(self):
        fpl = parse_icao_fpl(SAMPLE_FPL)
        assert fpl.equipment == "SBDGORVY"
        assert fpl.surveillance == "LB2"

    def test_date_of_flight(self):
        # DOF/260318 = YYMMDD = 2026-03-18
        fpl = parse_icao_fpl(SAMPLE_FPL)
        assert fpl.date_of_flight == date(2026, 3, 18)

    def test_remarks(self):
        fpl = parse_icao_fpl(SAMPLE_FPL)
        assert fpl.remarks is not None
        assert "FIKI" in fpl.remarks

    def test_pbn_codes(self):
        fpl = parse_icao_fpl(SAMPLE_FPL)
        assert fpl.pbn_codes is not None
        assert "B2C2D2" in fpl.pbn_codes


class TestFPLDerived:
    """Tests for derived convenience properties."""

    def test_is_vfr(self):
        fpl = parse_icao_fpl(SAMPLE_FPL)
        assert fpl.is_vfr is True
        assert fpl.is_ifr is False

    def test_is_ifr(self):
        fpl = parse_icao_fpl(SAMPLE_FPL_IFR)
        assert fpl.is_ifr is True
        assert fpl.is_vfr is False

    def test_has_gnss(self):
        fpl = parse_icao_fpl(SAMPLE_FPL)
        assert fpl.has_gnss is True  # G in SBDGORVY

    def test_has_adsb(self):
        fpl = parse_icao_fpl(SAMPLE_FPL)
        assert fpl.has_adsb is True  # B in LB2

    def test_has_rvsm(self):
        fpl = parse_icao_fpl(SAMPLE_FPL)
        assert fpl.has_rvsm is False  # no W in SBDGORVY

    def test_has_rnav(self):
        fpl = parse_icao_fpl(SAMPLE_FPL)
        assert fpl.has_rnav is True  # R in SBDGORVY


class TestFPLIFR:
    """Tests for IFR flight plan parsing."""

    def test_ifr_fields(self):
        fpl = parse_icao_fpl(SAMPLE_FPL_IFR)
        assert fpl.aircraft_registration == "GZIPM"
        assert fpl.aircraft_type == "C172"
        assert fpl.flight_rules == "I"
        assert fpl.flight_type == "S"

    def test_ifr_speed_and_level(self):
        fpl = parse_icao_fpl(SAMPLE_FPL_IFR)
        assert fpl.speed == "N0110"
        assert fpl.speed_knots == 110
        assert fpl.level == "F065"
        assert fpl.altitude_feet == 6500

    def test_ifr_route_has_airways_filtered(self):
        """Airways (UL9, L28) should be skipped, waypoints kept."""
        fpl = parse_icao_fpl(SAMPLE_FPL_IFR)
        assert "HAZEL" in fpl.route.waypoints
        assert "ORTAC" in fpl.route.waypoints
        assert "DINARD" in fpl.route.waypoints
        # Airways should not appear in waypoints
        for wp in fpl.route.waypoints:
            assert not _is_airway(wp), f"Airway {wp} should be filtered"

    def test_ifr_departure_time(self):
        fpl = parse_icao_fpl(SAMPLE_FPL_IFR)
        assert fpl.departure_time_utc == time(10, 30)

    def test_ifr_eet(self):
        fpl = parse_icao_fpl(SAMPLE_FPL_IFR)
        assert fpl.eet_minutes == 90


class TestFPLMinimal:
    """Tests for minimal FPL with few fields."""

    def test_minimal_parse(self):
        fpl = parse_icao_fpl(SAMPLE_FPL_MINIMAL)
        assert fpl is not None
        assert fpl.aircraft_registration == "GABCD"
        assert fpl.route.departure == "EGLL"
        assert fpl.route.destination == "EGSS"

    def test_minimal_no_equipment(self):
        fpl = parse_icao_fpl(SAMPLE_FPL_MINIMAL)
        # No equipment field split
        assert fpl.equipment is None

    def test_minimal_field18_zero(self):
        """Field 18 of '0' means no other info."""
        fpl = parse_icao_fpl(SAMPLE_FPL_MINIMAL)
        assert fpl.date_of_flight is None


class TestFPLMetricSpeed:
    """Tests for km/h speed conversion."""

    def test_metric_speed_conversion(self):
        fpl = parse_icao_fpl(SAMPLE_FPL_METRIC_SPEED)
        assert fpl.speed == "K0200"
        assert fpl.speed_knots == round(200 / 1.852)  # 108 knots

    def test_altitude_hundreds_of_feet(self):
        fpl = parse_icao_fpl(SAMPLE_FPL_METRIC_SPEED)
        assert fpl.level == "A055"
        assert fpl.altitude_feet == 5500


class TestRouteTokens:
    """Tests for route token classification."""

    def test_gps_coordinate_in_route(self):
        """GPS coordinates should become waypoints with coordinates."""
        fpl = parse_icao_fpl(SAMPLE_FPL)
        gps_points = [wp for wp in fpl.route.waypoint_coords if wp.point_type == "gps"]
        assert len(gps_points) == 1
        assert gps_points[0].name == "4830N00210E"
        assert abs(gps_points[0].latitude - 48.5) < 0.001
        assert abs(gps_points[0].longitude - 2.1667) < 0.001

    def test_dct_filtered(self):
        """DCT tokens should not appear in waypoints."""
        fpl = parse_icao_fpl(SAMPLE_FPL)
        assert "DCT" not in fpl.route.waypoints

    def test_named_waypoints_in_route(self):
        fpl = parse_icao_fpl(SAMPLE_FPL)
        assert "LYD" in fpl.route.waypoints
        assert "VESAN" in fpl.route.waypoints

    def test_raw_route_preserved(self):
        fpl = parse_icao_fpl(SAMPLE_FPL)
        assert fpl.raw_route is not None
        assert "LYD" in fpl.raw_route
        assert "4830N00210E" in fpl.raw_route


class TestAltitudeParsing:
    """Tests for _parse_altitude helper."""

    def test_flight_level(self):
        assert _parse_altitude("F350") == 35000
        assert _parse_altitude("F065") == 6500

    def test_altitude(self):
        assert _parse_altitude("A055") == 5500
        assert _parse_altitude("A100") == 10000

    def test_vfr_ifr(self):
        assert _parse_altitude("VFR") is None
        assert _parse_altitude("IFR") is None

    def test_metric(self):
        # S0850 = 850 tens of meters = 8500m ≈ 27887 ft
        alt = _parse_altitude("S0850")
        assert alt is not None
        assert 27000 < alt < 28000

    def test_none(self):
        assert _parse_altitude(None) is None
        assert _parse_altitude("") is None


class TestComputedTimes:
    """Tests for computed departure/arrival datetimes on route."""

    def test_departure_datetime(self):
        fpl = parse_icao_fpl(SAMPLE_FPL)
        assert fpl.route.departure_time is not None
        assert fpl.route.departure_time.year == 2026
        assert fpl.route.departure_time.month == 3
        assert fpl.route.departure_time.day == 18
        assert fpl.route.departure_time.hour == 9
        assert fpl.route.departure_time.minute == 30

    def test_arrival_datetime(self):
        fpl = parse_icao_fpl(SAMPLE_FPL)
        assert fpl.route.arrival_time is not None
        # 09:30 + 33min = 10:03
        assert fpl.route.arrival_time.hour == 10
        assert fpl.route.arrival_time.minute == 3

    def test_no_date_no_datetime(self):
        """Without DOF, route departure_time should be None."""
        fpl = parse_icao_fpl(SAMPLE_FPL_MINIMAL)
        assert fpl.route.departure_time is None


class TestSerialization:
    """Tests for to_dict serialization."""

    def test_to_dict_roundtrip(self):
        fpl = parse_icao_fpl(SAMPLE_FPL)
        d = fpl.to_dict()
        assert d["aircraft_registration"] == "N122DR"
        assert d["flight_rules"] == "V"
        assert d["is_vfr"] is True
        assert d["speed_knots"] == 166
        assert d["route"]["departure"] == "LFAT"
        assert d["route"]["destination"] == "EGTF"

    def test_to_dict_has_all_keys(self):
        fpl = parse_icao_fpl(SAMPLE_FPL)
        d = fpl.to_dict()
        expected_keys = {
            "aircraft_registration", "aircraft_type", "flight_rules",
            "flight_type", "speed", "speed_knots", "level", "altitude_feet",
            "equipment", "surveillance", "date_of_flight", "departure_time_utc",
            "eet_minutes", "raw_route", "other_info", "raw_text", "route",
            "is_ifr", "is_vfr", "has_gnss", "has_rnav", "has_adsb", "has_rvsm",
        }
        assert expected_keys.issubset(set(d.keys()))


class TestRepr:
    def test_repr(self):
        fpl = parse_icao_fpl(SAMPLE_FPL)
        r = repr(fpl)
        assert "N122DR" in r
        assert "LFAT" in r


# Helper used in test assertions
def _is_airway(token: str) -> bool:
    import re
    return bool(re.match(r'^[A-Z]{1,2}\d{1,4}$', token))
