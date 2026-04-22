"""Tests for Waypoint model, WaypointCollection, and RouteResolver."""

import pytest
import tempfile
import os
from datetime import datetime

from euro_aip.models.waypoint import Waypoint
from euro_aip.models.waypoint_collection import WaypointCollection
from euro_aip.models.navpoint import NavPoint
from euro_aip.models.euro_aip_model import EuroAipModel
from euro_aip.models.airport import Airport
from euro_aip.models.route_resolver import RouteResolver
from euro_aip.briefing.models.route import Route
from euro_aip.storage.database_storage import DatabaseStorage
from euro_aip.utils.dms_parser import (
    parse_fra_latitude,
    parse_fra_longitude,
    parse_fra_coordinates,
    parse_dms,
    parse_dms_coordinates,
)
from euro_aip.sources.opennav import OpenNavSource, _ROW_PATTERN


# ========================================================================
# DMS Parser Tests
# ========================================================================

class TestDMSParser:

    def test_latitude_north(self):
        assert abs(parse_fra_latitude("N404519") - 40.755278) < 0.001

    def test_latitude_south(self):
        lat = parse_fra_latitude("S451230")
        assert lat < 0
        assert abs(lat - (-45.208333)) < 0.001

    def test_longitude_east(self):
        assert abs(parse_fra_longitude("E0183830") - 18.641667) < 0.001

    def test_longitude_west(self):
        lon = parse_fra_longitude("W0010000")
        assert lon < 0
        assert abs(lon - (-1.0)) < 0.001

    def test_coordinates(self):
        lat, lon = parse_fra_coordinates("N404519", "E0183830")
        assert abs(lat - 40.755278) < 0.001
        assert abs(lon - 18.641667) < 0.001

    def test_invalid_latitude_length(self):
        with pytest.raises(ValueError):
            parse_fra_latitude("N4045")

    def test_invalid_longitude_length(self):
        with pytest.raises(ValueError):
            parse_fra_longitude("E01838")

    def test_invalid_hemisphere(self):
        with pytest.raises(ValueError):
            parse_fra_latitude("X404519")


# ========================================================================
# OpenNav DMS Parser Tests
# ========================================================================

class TestOpenNavDMSParser:

    def test_north_latitude(self):
        lat = parse_dms('49° 54\' 7.00" N')
        assert abs(lat - 49.901944) < 0.001

    def test_south_latitude(self):
        lat = parse_dms('45° 20\' 52.00" S')
        assert lat < 0
        assert abs(lat - (-45.347778)) < 0.001

    def test_east_longitude(self):
        lon = parse_dms('3° 26\' 50.00" E')
        assert abs(lon - 3.447222) < 0.001

    def test_west_longitude(self):
        lon = parse_dms('007° 11\' 29.00" W')
        assert lon < 0
        assert abs(lon - (-7.191389)) < 0.001

    def test_coordinates(self):
        lat, lon = parse_dms_coordinates('49° 54\' 7.00" N', '3° 26\' 50.00" E')
        assert abs(lat - 49.901944) < 0.001
        assert abs(lon - 3.447222) < 0.001

    def test_invalid_string(self):
        with pytest.raises(ValueError):
            parse_dms("not a coordinate")


# ========================================================================
# OpenNav Source Tests
# ========================================================================

class TestOpenNavSource:

    SAMPLE_HTML = '''
    <table>
    <tr><td><b>IDENT</b></td><td class="layout_col50">&nbsp;</td><td><b>LATITUDE</b></td><td class="layout_col50">&nbsp;</td><td><b>LONGITUDE</b></td></tr>
    <tr><td colspan="5">&nbsp;</td></tr>
    <tr><td><a href="/waypoint/CH/ABESI">ABESI</a></td><td class="layout_col50">&nbsp;</td><td>46° 9' 34.61" N</td><td class="layout_col50">&nbsp;</td><td>9° 2' 34.09" E</td></tr>
    <tr><td><a href="/waypoint/CH/ABREG">ABREG</a></td><td class="layout_col50">&nbsp;</td><td>46° 18' 25.00" N</td><td class="layout_col50">&nbsp;</td><td>009° 33' 05.00" E</td></tr>
    </table>
    '''

    def test_parse_html(self):
        import tempfile
        source = OpenNavSource(cache_dir=tempfile.mkdtemp())
        waypoints = source._parse_html(self.SAMPLE_HTML, "CH")
        assert len(waypoints) == 2
        assert waypoints[0].name == "ABESI"
        assert abs(waypoints[0].latitude_deg - 46.159614) < 0.001
        assert waypoints[0].source == "opennav"

    def test_parse_html_empty(self):
        import tempfile
        source = OpenNavSource(cache_dir=tempfile.mkdtemp())
        waypoints = source._parse_html("<table></table>", "XX")
        assert len(waypoints) == 0

    def test_point_type_classification(self):
        import tempfile
        source = OpenNavSource(cache_dir=tempfile.mkdtemp())
        waypoints = source._parse_html(self.SAMPLE_HTML, "CH")
        assert waypoints[0].point_type == "5LNC"  # 5-letter alpha name

    def test_row_regex_matches_real_format(self):
        row = '<tr><td><a href="/waypoint/FR/BILGO">BILGO</a></td><td class="layout_col50">&nbsp;</td><td>49° 54\' 7.00" N</td><td class="layout_col50">&nbsp;</td><td>3° 26\' 50.00" E</td></tr>'
        match = _ROW_PATTERN.search(row)
        assert match is not None
        assert match.group(1) == "BILGO"


# ========================================================================
# Waypoint Model Tests
# ========================================================================

class TestWaypoint:

    def test_basic_creation(self):
        wp = Waypoint(name="BILGO", latitude_deg=48.5, longitude_deg=2.3)
        assert wp.name == "BILGO"
        assert wp.latitude_deg == 48.5
        assert wp.longitude_deg == 2.3
        assert wp.source == "eurocontrol_fra"

    def test_navpoint_property(self):
        wp = Waypoint(name="BILGO", latitude_deg=48.5, longitude_deg=2.3)
        np = wp.navpoint
        assert isinstance(np, NavPoint)
        assert np.latitude == 48.5
        assert np.longitude == 2.3
        assert np.name == "BILGO"

    def test_is_navaid(self):
        wp_5lnc = Waypoint(name="BILGO", latitude_deg=0, longitude_deg=0, point_type="5LNC")
        assert not wp_5lnc.is_navaid

        wp_vor = Waypoint(name="REM", latitude_deg=0, longitude_deg=0, point_type="VOR")
        assert wp_vor.is_navaid

        wp_none = Waypoint(name="TEST", latitude_deg=0, longitude_deg=0)
        assert not wp_none.is_navaid

    def test_fir_list(self):
        wp = Waypoint(name="TEST", latitude_deg=0, longitude_deg=0, fir_codes="LFFF,LFBB")
        assert wp.fir_list == ["LFFF", "LFBB"]

        wp_none = Waypoint(name="TEST", latitude_deg=0, longitude_deg=0)
        assert wp_none.fir_list == []

    def test_to_dict_from_dict_roundtrip(self):
        wp = Waypoint(
            name="BILGO", latitude_deg=48.5, longitude_deg=2.3,
            point_type="5LNC", fir_codes="LFFF", level_availability="FL195 / FL660",
        )
        d = wp.to_dict()
        wp2 = Waypoint.from_dict(d)
        assert wp2.name == wp.name
        assert wp2.latitude_deg == wp.latitude_deg
        assert wp2.longitude_deg == wp.longitude_deg
        assert wp2.point_type == wp.point_type
        assert wp2.fir_codes == wp.fir_codes

    def test_repr(self):
        wp = Waypoint(name="REM", latitude_deg=49.3, longitude_deg=3.1, point_type="VOR")
        assert "REM" in repr(wp)
        assert "VOR" in repr(wp)


# ========================================================================
# WaypointCollection Tests
# ========================================================================

class TestWaypointCollection:

    @pytest.fixture
    def waypoints(self):
        return [
            Waypoint(name="BILGO", latitude_deg=48.5, longitude_deg=2.3, point_type="5LNC", fir_codes="LFFF"),
            Waypoint(name="REM", latitude_deg=49.3, longitude_deg=3.1, point_type="VOR", fir_codes="LFFF,LFBB"),
            Waypoint(name="ERTIP", latitude_deg=47.8, longitude_deg=6.5, point_type="5LNC", fir_codes="LSAS"),
            Waypoint(name="ALG", latitude_deg=40.6, longitude_deg=8.2, point_type="VORTAC", fir_codes="LIRR"),
        ]

    def test_by_type(self, waypoints):
        col = WaypointCollection(waypoints)
        vors = col.by_type("VOR")
        assert vors.count() == 1
        assert vors.first().name == "REM"

    def test_by_fir(self, waypoints):
        col = WaypointCollection(waypoints)
        lfff = col.by_fir("LFFF")
        assert lfff.count() == 2

    def test_navaids(self, waypoints):
        col = WaypointCollection(waypoints)
        navaids = col.navaids()
        assert navaids.count() == 2  # REM (VOR) and ALG (VORTAC)

    def test_five_letter_codes(self, waypoints):
        col = WaypointCollection(waypoints)
        codes = col.five_letter_codes()
        assert codes.count() == 2  # BILGO and ERTIP

    def test_getitem_by_name(self, waypoints):
        col = WaypointCollection(waypoints)
        assert col["BILGO"].name == "BILGO"
        with pytest.raises(KeyError):
            col["NONEXISTENT"]

    def test_contains_by_name(self, waypoints):
        col = WaypointCollection(waypoints)
        assert "BILGO" in col
        assert "NONEXISTENT" not in col

    def test_get_by_name(self, waypoints):
        col = WaypointCollection(waypoints)
        assert col.get("BILGO") is not None
        assert col.get("NONEXISTENT") is None

    def test_nearest(self, waypoints):
        col = WaypointCollection(waypoints)
        point = NavPoint(latitude=48.0, longitude=3.0, name="REF")
        nearest = col.nearest(point, count=2)
        assert nearest.count() == 2
        # BILGO (48.5, 2.3) should be closer to (48.0, 3.0) than ALG (40.6, 8.2)
        names = [w.name for w in nearest.all()]
        assert names[0] in ("BILGO", "REM")

    def test_empty_collection(self):
        col = WaypointCollection([])
        assert col.count() == 0
        assert col.by_type("VOR").count() == 0
        assert col.by_fir("LFFF").count() == 0

    def test_chaining(self, waypoints):
        col = WaypointCollection(waypoints)
        result = col.by_fir("LFFF").five_letter_codes()
        assert result.count() == 1
        assert result.first().name == "BILGO"


# ========================================================================
# EuroAipModel Waypoint Integration Tests
# ========================================================================

class TestEuroAipModelWaypoints:

    def test_add_waypoint(self):
        model = EuroAipModel()
        wp = Waypoint(name="BILGO", latitude_deg=48.5, longitude_deg=2.3)
        model.add_waypoint(wp)
        assert model.get_waypoint("BILGO") is not None
        assert "BILGO" in model.waypoints

    def test_add_waypoint_merge_fir(self):
        model = EuroAipModel()
        wp1 = Waypoint(name="BILGO", latitude_deg=48.5, longitude_deg=2.3, fir_codes="LFFF")
        wp2 = Waypoint(name="BILGO", latitude_deg=48.5, longitude_deg=2.3, fir_codes="LFBB")
        model.add_waypoint(wp1)
        model.add_waypoint(wp2)
        merged = model.get_waypoint("BILGO")
        assert "LFFF" in merged.fir_list
        assert "LFBB" in merged.fir_list

    def test_bulk_add_waypoints(self):
        model = EuroAipModel()
        wps = [
            Waypoint(name="A", latitude_deg=0, longitude_deg=0),
            Waypoint(name="B", latitude_deg=1, longitude_deg=1),
        ]
        result = model.bulk_add_waypoints(wps)
        assert result["added"] == 2
        assert result["updated"] == 0
        assert model.waypoints.count() == 2

    def test_waypoints_in_statistics(self):
        model = EuroAipModel()
        model.add_waypoint(Waypoint(name="A", latitude_deg=0, longitude_deg=0))
        stats = model.get_statistics()
        assert stats["total_waypoints"] == 1

    def test_waypoints_in_to_dict(self):
        model = EuroAipModel()
        model.add_waypoint(Waypoint(name="A", latitude_deg=0, longitude_deg=0))
        d = model.to_dict()
        assert "waypoints" in d
        assert "A" in d["waypoints"]


# ========================================================================
# Database Storage Round-Trip Tests
# ========================================================================

class TestDatabaseStorageWaypoints:

    def test_save_and_load(self):
        model = EuroAipModel()
        model.add_waypoint(Waypoint(
            name="BILGO", latitude_deg=48.5, longitude_deg=2.3,
            point_type="5LNC", fir_codes="LFFF,LFBB",
        ))
        model.add_waypoint(Waypoint(
            name="REM", latitude_deg=49.3, longitude_deg=3.1,
            point_type="VOR",
        ))

        db_path = tempfile.mktemp(suffix=".db")
        try:
            storage = DatabaseStorage(db_path)
            storage.save_model(model)

            loaded = storage.load_model()
            assert len(loaded._waypoints) == 2
            assert loaded.get_waypoint("BILGO").fir_codes == "LFFF,LFBB"
            assert loaded.get_waypoint("REM").point_type == "VOR"
        finally:
            os.unlink(db_path)

    def test_change_tracking(self):
        model = EuroAipModel()
        model.add_waypoint(Waypoint(name="A", latitude_deg=48.5, longitude_deg=2.3))

        db_path = tempfile.mktemp(suffix=".db")
        try:
            storage = DatabaseStorage(db_path)
            storage.save_model(model)

            # Update and re-save
            model._waypoints["A"][0].latitude_deg = 48.6
            model._waypoints["A"][0]._navpoint = None
            storage2 = DatabaseStorage(db_path)
            storage2.save_model(model)

            # Check changes table
            import sqlite3
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            changes = conn.execute("SELECT * FROM waypoints_changes").fetchall()
            assert len(changes) == 1
            assert changes[0]["field_name"] == "latitude_deg"
            conn.close()
        finally:
            os.unlink(db_path)

    def test_migration_adds_waypoints_table(self):
        """Test that opening an old DB without waypoints table adds it."""
        db_path = tempfile.mktemp(suffix=".db")
        try:
            # Create a DB without waypoints table
            import sqlite3
            conn = sqlite3.connect(db_path)
            conn.execute("CREATE TABLE airports (icao_code TEXT PRIMARY KEY, name TEXT)")
            conn.execute("CREATE TABLE model_metadata (key TEXT PRIMARY KEY, value TEXT, updated_at TEXT)")
            conn.execute("INSERT INTO model_metadata VALUES ('schema_version', '1', '2024-01-01')")
            conn.commit()
            conn.close()

            # Opening should trigger migration
            storage = DatabaseStorage(db_path)
            # Verify waypoints table exists
            conn = sqlite3.connect(db_path)
            cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='waypoints'")
            assert cursor.fetchone() is not None
            conn.close()
        finally:
            os.unlink(db_path)


# ========================================================================
# Route Resolver Tests
# ========================================================================

class TestRouteResolver:

    @pytest.fixture
    def model(self):
        m = EuroAipModel()
        m.add_airport(Airport(ident="EGTF", name="Fairoaks", latitude_deg=51.348, longitude_deg=-0.559))
        m.add_airport(Airport(ident="LSGS", name="Sion", latitude_deg=46.219, longitude_deg=7.327))
        m.add_airport(Airport(ident="LFQA", name="Reims", latitude_deg=49.310, longitude_deg=3.621))
        m.add_waypoint(Waypoint(name="VESAN", latitude_deg=50.372, longitude_deg=2.026, point_type="5LNC"))
        m.add_waypoint(Waypoint(name="POGOL", latitude_deg=48.399, longitude_deg=6.693, point_type="5LNC"))
        m.add_waypoint(Waypoint(name="REM", latitude_deg=49.3, longitude_deg=3.1, point_type="VOR"))
        return m

    def test_resolve_point_airport(self, model):
        resolver = RouteResolver(model)
        point = resolver.resolve_point("EGTF")
        assert point is not None
        assert point.point_type == "airport"
        assert abs(point.latitude - 51.348) < 0.001

    def test_resolve_point_waypoint(self, model):
        resolver = RouteResolver(model)
        point = resolver.resolve_point("VESAN")
        assert point is not None
        assert point.point_type == "5LNC"

    def test_resolve_point_not_found(self, model):
        resolver = RouteResolver(model)
        assert resolver.resolve_point("XYZZY") is None

    def test_resolve_airport_first(self, model):
        """Airport should win over waypoint if same name."""
        # Add a waypoint with same name as airport
        model.add_waypoint(Waypoint(name="EGTF", latitude_deg=0, longitude_deg=0))
        resolver = RouteResolver(model)
        point = resolver.resolve_point("EGTF")
        assert point.point_type == "airport"
        assert abs(point.latitude - 51.348) < 0.001

    def test_resolve_simple_route(self, model):
        resolver = RouteResolver(model)
        route = resolver.resolve("EGTF LSGS")
        assert route.departure == "EGTF"
        assert route.destination == "LSGS"
        assert route.departure_coords is not None
        assert route.destination_coords is not None
        assert len(route.waypoints) == 0

    def test_resolve_mixed_route(self, model):
        resolver = RouteResolver(model)
        route = resolver.resolve("EGTF VESAN POGOL LSGS")
        assert route.departure == "EGTF"
        assert route.destination == "LSGS"
        assert route.waypoints == ["VESAN", "POGOL"]
        assert len(route.waypoint_coords) == 2
        assert route.waypoint_coords[0].name == "VESAN"
        assert route.waypoint_coords[1].name == "POGOL"

    def test_resolve_airport_as_waypoint(self, model):
        """An airport in the middle of a route is treated as a waypoint."""
        resolver = RouteResolver(model)
        route = resolver.resolve("EGTF LFQA LSGS")
        assert route.waypoints == ["LFQA"]
        # It should be point_type="waypoint" not "airport"
        assert route.waypoint_coords[0].point_type == "waypoint"

    def test_resolve_with_unresolved(self, model):
        resolver = RouteResolver(model)
        route = resolver.resolve("EGTF XYZZY LSGS")
        assert route.waypoints == []
        assert len(route.waypoint_coords) == 0

    def test_resolve_filters_dct(self, model):
        resolver = RouteResolver(model)
        route = resolver.resolve("EGTF DCT VESAN DCT LSGS")
        assert route.waypoints == ["VESAN"]

    def test_resolve_too_few_tokens(self, model):
        resolver = RouteResolver(model)
        with pytest.raises(ValueError):
            resolver.resolve("EGTF")

    def test_route_navpoints(self, model):
        resolver = RouteResolver(model)
        route = resolver.resolve("EGTF VESAN POGOL LSGS")
        navpoints = route.get_route_navpoints()
        assert len(navpoints) == 4
        assert navpoints[0].name == "EGTF"
        assert navpoints[1].name == "VESAN"
        assert navpoints[2].name == "POGOL"
        assert navpoints[3].name == "LSGS"

    def test_from_route_string(self, model):
        resolver = RouteResolver(model)
        route = Route.from_route_string("EGTF VESAN LSGS", resolver)
        assert route.departure == "EGTF"
        assert route.destination == "LSGS"
        assert route.waypoints == ["VESAN"]


# ========================================================================
# Detour Filter Tests
# ========================================================================

class TestDetourFilter:
    """Filters waypoints resolved to coordinates far from the route."""

    @pytest.fixture
    def model(self):
        m = EuroAipModel()
        # EGKK (Gatwick) → EDDF (Frankfurt), ~340 nm leg
        m.add_airport(Airport(ident="EGKK", name="Gatwick", latitude_deg=51.148, longitude_deg=-0.190))
        m.add_airport(Airport(ident="EDDF", name="Frankfurt", latitude_deg=50.033, longitude_deg=8.543))
        # Small regional pair for short-leg floor test
        m.add_airport(Airport(ident="EGKA", name="Shoreham", latitude_deg=50.835, longitude_deg=-0.297))
        m.add_airport(Airport(ident="EGKB", name="Biggin Hill", latitude_deg=51.331, longitude_deg=0.033))
        # On-route European fixes
        m.add_waypoint(Waypoint(name="NEARR", latitude_deg=50.6, longitude_deg=4.2, point_type="5LNC"))
        m.add_waypoint(Waypoint(name="TERMN", latitude_deg=51.20, longitude_deg=-0.10, point_type="5LNC"))
        # Single far-off candidate (simulates a misresolution)
        m.add_waypoint(Waypoint(name="FAROFF", latitude_deg=40.5, longitude_deg=-3.5, point_type="5LNC"))
        # Ambiguous name — one candidate near route, one far off
        m.add_waypoint(
            Waypoint(name="AMBIG", latitude_deg=50.5, longitude_deg=4.0, point_type="VOR",
                     source_id="near", source="test")
        )
        m.add_waypoint(
            Waypoint(name="AMBIG", latitude_deg=35.0, longitude_deg=-100.0, point_type="VOR",
                     source_id="far", source="test")
        )
        return m

    def test_threshold_formula(self, model):
        r = RouteResolver(model, detour_floor_nm=30, detour_coef=0.5, detour_cap_nm=300)
        # Short leg → floor
        assert r._detour_threshold_nm(10.0) == 30
        # Medium leg → coef × leg
        assert r._detour_threshold_nm(200.0) == 100.0
        # Long leg → cap
        assert r._detour_threshold_nm(2000.0) == 300.0

    def test_two_point_route_has_no_rejects(self, model):
        r = RouteResolver(model)
        route = r.resolve("EGKK EDDF")
        assert route.rejected_waypoints == []

    def test_near_route_waypoint_passes(self, model):
        r = RouteResolver(model)
        route = r.resolve("EGKK NEARR EDDF")
        assert route.waypoints == ["NEARR"]
        assert route.rejected_waypoints == []

    def test_far_off_waypoint_rejected(self, model):
        r = RouteResolver(model)
        route = r.resolve("EGKK FAROFF EDDF")
        assert route.waypoints == []
        assert len(route.rejected_waypoints) == 1
        entry = route.rejected_waypoints[0]
        assert entry["name"] == "FAROFF"
        assert entry["reason"] == "detour_exceeds_threshold"
        assert entry["detour_nm"] > entry["threshold_nm"]

    def test_short_leg_floor_accepts_terminal_fix(self, model):
        """Short legs use the floor, tolerating near-route terminal fixes."""
        # EGKA→EGKB is ~24 nm; TERMN is ~12 nm off course → should pass.
        r = RouteResolver(model)
        route = r.resolve("EGKA TERMN EGKB")
        assert route.waypoints == ["TERMN"]
        assert route.rejected_waypoints == []

    def test_long_leg_cap_rejects_very_far_off(self, model):
        """Cap bounds permissiveness even on long legs."""
        # Manually tighten cap so FAROFF is clearly out of bounds
        r = RouteResolver(model, detour_cap_nm=200)
        route = r.resolve("EGKK FAROFF EDDF")
        assert route.rejected_waypoints
        assert route.rejected_waypoints[0]["threshold_nm"] <= 200

    def test_candidate_selection_picks_min_detour(self, model):
        """When multiple candidates exist, the on-route one is chosen."""
        r = RouteResolver(model)
        route = r.resolve("EGKK AMBIG EDDF")
        # Should pick the near candidate (lat ~50.5) not the far one (lat 35)
        assert route.waypoints == ["AMBIG"]
        assert len(route.waypoint_coords) == 1
        assert abs(route.waypoint_coords[0].latitude - 50.5) < 0.1
        assert route.rejected_waypoints == []

    def test_bad_point_does_not_pollute_subsequent_anchor(self, model):
        """A rejected point must not move the reference — next fix still
        scored against the last good anchor."""
        r = RouteResolver(model)
        # FAROFF (in Spain) between two on-route fixes. If rejection moved
        # the anchor to Spain, NEARR would then fail too. It must still pass.
        route = r.resolve("EGKK FAROFF NEARR EDDF")
        assert "NEARR" in route.waypoints
        assert any(rej["name"] == "FAROFF" for rej in route.rejected_waypoints)

    def test_rejected_waypoints_roundtrip(self, model):
        r = RouteResolver(model)
        route = r.resolve("EGKK FAROFF EDDF")
        d = route.to_dict()
        assert d["rejected_waypoints"]
        route2 = Route.from_dict(d)
        assert route2.rejected_waypoints == route.rejected_waypoints
