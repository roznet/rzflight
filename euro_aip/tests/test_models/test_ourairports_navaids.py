"""Tests for OurAirports NAVAID source."""

import pytest
from unittest.mock import patch, MagicMock

from euro_aip.sources.ourairports_navaids import OurAirportsNavaidSource, _TYPE_MAP
from euro_aip.models.waypoint import Waypoint
from euro_aip.models.euro_aip_model import EuroAipModel

SAMPLE_CSV = """id,filename,ident,name,type,frequency_khz,latitude_deg,longitude_deg,elevation_ft,iso_country,dme_frequency_khz,dme_channel,dme_latitude_deg,dme_longitude_deg,dme_elevation_ft,slaved_variation_deg,magnetic_variation_deg,usageType,power,associated_airport
85100,REM,REM,Reims VOR-DME,VOR-DME,114100,49.310001,3.160000,312,FR,,,,,,,,BOTH,HIGH,
85101,LYD,LYD,Lydd VOR-DME,VOR-DME,114050,50.950001,0.930000,15,GB,,,,,,,,BOTH,HIGH,
85102,ABB,ABB,Abbeville NDB,NDB,353,50.120000,1.850000,220,FR,,,,,,,,BOTH,MEDIUM,
85103,,,Unnamed,UNKNOWN,0,0.0,0.0,0,XX,,,,,,,,BOTH,LOW,
85104,FOO,FOO,Foo TACAN,TACAN,109000,48.0,2.0,0,US,,,,,,,,BOTH,LOW,
"""


class TestParseCSV:
    """Tests for CSV parsing."""

    def _make_source(self):
        return OurAirportsNavaidSource(cache_dir="/tmp/test_cache")

    def test_parse_csv_basic(self):
        source = self._make_source()
        waypoints = source._parse_csv(SAMPLE_CSV)
        names = {wp.name for wp in waypoints}
        assert "REM" in names
        assert "LYD" in names
        assert "ABB" in names

    def test_type_mapping(self):
        source = self._make_source()
        waypoints = source._parse_csv(SAMPLE_CSV)
        by_name = {wp.name: wp for wp in waypoints}
        assert by_name["REM"].point_type == "VORDME"
        assert by_name["ABB"].point_type == "NDB"
        assert by_name["FOO"].point_type == "TACAN"

    def test_coordinates(self):
        source = self._make_source()
        waypoints = source._parse_csv(SAMPLE_CSV)
        by_name = {wp.name: wp for wp in waypoints}
        assert abs(by_name["REM"].latitude_deg - 49.31) < 0.01
        assert abs(by_name["REM"].longitude_deg - 3.16) < 0.01

    def test_source_field(self):
        source = self._make_source()
        waypoints = source._parse_csv(SAMPLE_CSV)
        assert all(wp.source == "ourairports" for wp in waypoints)

    def test_unknown_type_skipped(self):
        """Rows with unrecognized type should be skipped."""
        source = self._make_source()
        waypoints = source._parse_csv(SAMPLE_CSV)
        names = {wp.name for wp in waypoints}
        # Row with type "UNKNOWN" and no ident should be skipped
        assert "" not in names

    def test_empty_ident_skipped(self):
        source = self._make_source()
        waypoints = source._parse_csv(SAMPLE_CSV)
        assert all(wp.name != "" for wp in waypoints)

    def test_deduplication(self):
        """Duplicate idents should keep first occurrence."""
        csv_with_dup = SAMPLE_CSV + "85105,REM2,REM,Reims VOR,VOR,114100,49.31,3.16,312,FR,,,,,,,,BOTH,HIGH,\n"
        source = self._make_source()
        waypoints = source._parse_csv(csv_with_dup)
        rem_count = sum(1 for wp in waypoints if wp.name == "REM")
        assert rem_count == 1


class TestCountryFilter:
    """Tests for country filtering."""

    def test_filter_by_country(self):
        source = OurAirportsNavaidSource(cache_dir="/tmp/test_cache", countries=["FR"])
        waypoints = source._parse_csv(SAMPLE_CSV)
        countries_seen = {wp.name for wp in waypoints}
        assert "REM" in countries_seen   # FR
        assert "ABB" in countries_seen   # FR
        assert "LYD" not in countries_seen  # GB
        assert "FOO" not in countries_seen  # US

    def test_no_filter_includes_all(self):
        source = OurAirportsNavaidSource(cache_dir="/tmp/test_cache")
        waypoints = source._parse_csv(SAMPLE_CSV)
        names = {wp.name for wp in waypoints}
        assert "REM" in names
        assert "LYD" in names
        assert "FOO" in names


class TestUpdateModel:
    """Tests for update_model skip-existing behavior."""

    def test_skips_existing_waypoints(self):
        """Should not add waypoints that already exist in the model."""
        model = EuroAipModel()
        # Pre-add REM from Eurocontrol FRA
        existing = Waypoint(
            name="REM", latitude_deg=49.31, longitude_deg=3.16,
            point_type="VORDME", source="eurocontrol_fra",
        )
        model.add_waypoint(existing)

        source = OurAirportsNavaidSource(cache_dir="/tmp/test_cache")

        # Mock _get_navaids to return our sample data
        waypoints = source._parse_csv(SAMPLE_CSV)
        with patch.object(source, '_get_navaids', return_value=waypoints):
            source.update_model(model)

        # REM should still be from eurocontrol_fra, not overwritten
        rem = model.get_waypoint("REM")
        assert rem.source == "eurocontrol_fra"

        # LYD should be added from ourairports
        lyd = model.get_waypoint("LYD")
        assert lyd is not None
        assert lyd.source == "ourairports"

    def test_adds_when_model_empty(self):
        """All waypoints should be added to an empty model."""
        model = EuroAipModel()
        source = OurAirportsNavaidSource(cache_dir="/tmp/test_cache")

        waypoints = source._parse_csv(SAMPLE_CSV)
        with patch.object(source, '_get_navaids', return_value=waypoints):
            source.update_model(model)

        assert model.get_waypoint("REM") is not None
        assert model.get_waypoint("LYD") is not None
        assert model.get_waypoint("ABB") is not None


class TestTypeMap:
    """Tests for type mapping completeness."""

    def test_all_expected_types(self):
        expected = {"VOR", "VOR-DME", "VORTAC", "DME", "NDB", "NDB-DME", "TACAN"}
        assert set(_TYPE_MAP.keys()) == expected

    def test_mapped_values_match_waypoint_conventions(self):
        """Mapped values should match the point_type conventions used by FRA source."""
        assert _TYPE_MAP["VOR-DME"] == "VORDME"
        assert _TYPE_MAP["NDB-DME"] == "NDBDME"
        assert _TYPE_MAP["VOR"] == "VOR"
