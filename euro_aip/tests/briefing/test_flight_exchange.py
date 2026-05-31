"""Tests for the FlightExchange cross-app interchange model.

Covers the round-trip invariant ``from_dict(to_dict(x)) == x`` and parity with
the shared wire-format fixtures that the Swift side also decodes
(``Tests/fixtures/flight_exchange/``). See ``designs/flight_exchange_design.md``.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from euro_aip.briefing.models import FlightExchange, Route, RoutePoint
from euro_aip.briefing.models.flight_exchange import SCHEMA_VERSION

# Shared cross-platform parity fixtures live at the repo root so both the
# Python and Swift test suites read the exact same JSON.
FIXTURES_DIR = Path(__file__).resolve().parents[3] / "Tests" / "fixtures" / "flight_exchange"


def load_fixture(name: str) -> dict:
    with open(FIXTURES_DIR / name) as f:
        return json.load(f)


@pytest.fixture
def full_exchange() -> FlightExchange:
    """A fully populated FlightExchange matching full.json."""
    route = Route(
        departure="EGTK",
        destination="LSGS",
        alternates=["LSGG"],
        waypoints=["BILGO", "XIDIL"],
        departure_coords=(51.83, -1.32),
        destination_coords=(46.22, 7.33),
        alternate_coords={"LSGG": (46.24, 6.11)},
        waypoint_coords=[
            RoutePoint(name="BILGO", latitude=48.50, longitude=2.17, point_type="waypoint"),
            RoutePoint(name="XIDIL", latitude=47.10, longitude=5.40, point_type="waypoint"),
        ],
        aircraft_type="P28A",
        departure_time=datetime(2026, 6, 1, 9, 0, 0, tzinfo=timezone.utc),
        arrival_time=datetime(2026, 6, 1, 11, 15, 0, tzinfo=timezone.utc),
        cruise_altitude_ft=8000,
    )
    return FlightExchange(
        route=route,
        name="Oxford -> Sion",
        aircraft_registration="HB-ABC",
        source_app="weather",
        source_flight_id="egtk_lsgs-2026-06-01-a1b2",
        source_share_code="Ab3xY9k2",
    )


class TestRoundTrip:
    """The core invariant: from_dict(to_dict(x)) == x."""

    def test_full_round_trip(self, full_exchange):
        restored = FlightExchange.from_dict(full_exchange.to_dict())
        assert restored == full_exchange

    def test_minimal_round_trip(self):
        fx = FlightExchange(route=Route(departure="EGTF", destination="EGLL"))
        restored = FlightExchange.from_dict(fx.to_dict())
        assert restored == fx

    def test_dict_round_trip_is_stable(self, full_exchange):
        """to_dict -> from_dict -> to_dict yields identical wire output."""
        once = full_exchange.to_dict()
        twice = FlightExchange.from_dict(once).to_dict()
        assert once == twice


class TestWireFormat:
    """Shape of the emitted dictionary."""

    def test_minimal_omits_envelope_keys(self):
        d = FlightExchange(route=Route(departure="EGTF", destination="EGLL")).to_dict()
        assert d["schema_version"] == SCHEMA_VERSION
        assert "route" in d
        # Optional envelope fields are omitted, not emitted as null.
        assert "name" not in d
        assert "source" not in d
        assert "aircraft" not in d

    def test_route_embedded_verbatim(self, full_exchange):
        d = full_exchange.to_dict()
        assert d["route"] == full_exchange.route.to_dict()

    def test_aircraft_type_mirrors_route(self, full_exchange):
        d = full_exchange.to_dict()
        assert d["aircraft"]["type"] == full_exchange.route.aircraft_type

    def test_aircraft_block_from_type_only(self):
        """A route with an aircraft_type but no registration still emits type."""
        fx = FlightExchange(route=Route(departure="EGTF", destination="EGLL", aircraft_type="C172"))
        d = fx.to_dict()
        assert d["aircraft"] == {"type": "C172"}

    def test_source_partial(self):
        fx = FlightExchange(route=Route(departure="EGTF", destination="EGLL"), source_app="brief")
        d = fx.to_dict()
        assert d["source"] == {"app": "brief"}

    def test_schema_version_default(self):
        fx = FlightExchange(route=Route(departure="EGTF", destination="EGLL"))
        assert fx.schema_version == SCHEMA_VERSION


class TestFromDict:
    """Decoding behaviour and tolerance."""

    def test_aircraft_type_not_stored_separately(self, full_exchange):
        """aircraft.type is a mirror — route.aircraft_type is the source of truth."""
        d = full_exchange.to_dict()
        d["aircraft"]["type"] = "WRONG"  # mismatched mirror should be ignored
        fx = FlightExchange.from_dict(d)
        assert fx.route.aircraft_type == "P28A"

    def test_missing_schema_version_defaults(self):
        d = {"route": Route(departure="EGTF", destination="EGLL").to_dict()}
        fx = FlightExchange.from_dict(d)
        assert fx.schema_version == SCHEMA_VERSION

    def test_rejects_newer_schema_version(self):
        """A newer (unknown) schema version is rejected, not silently decoded."""
        d = {
            "schema_version": SCHEMA_VERSION + 1,
            "route": Route(departure="EGTF", destination="EGLL").to_dict(),
        }
        with pytest.raises(ValueError):
            FlightExchange.from_dict(d)

    def test_null_source_and_aircraft(self):
        d = {
            "schema_version": 1,
            "route": Route(departure="EGTF", destination="EGLL").to_dict(),
            "source": None,
            "aircraft": None,
        }
        fx = FlightExchange.from_dict(d)
        assert fx.source_app is None
        assert fx.aircraft_registration is None


class TestParityFixtures:
    """The committed fixtures are the exact Python wire format (shared with Swift)."""

    def test_full_fixture_matches_emit(self, full_exchange):
        assert full_exchange.to_dict() == load_fixture("full.json")

    def test_minimal_fixture_matches_emit(self):
        fx = FlightExchange(route=Route(departure="EGTF", destination="EGLL"))
        assert fx.to_dict() == load_fixture("minimal.json")

    def test_full_fixture_decodes_and_round_trips(self):
        data = load_fixture("full.json")
        fx = FlightExchange.from_dict(data)
        assert fx.route.departure == "EGTK"
        assert fx.route.destination == "LSGS"
        assert fx.name == "Oxford -> Sion"
        assert fx.aircraft_registration == "HB-ABC"
        assert fx.source_app == "weather"
        assert fx.source_share_code == "Ab3xY9k2"
        assert fx.route.departure_time == datetime(2026, 6, 1, 9, 0, 0, tzinfo=timezone.utc)
        assert fx.to_dict() == data

    def test_minimal_fixture_decodes(self):
        fx = FlightExchange.from_dict(load_fixture("minimal.json"))
        assert fx.route.departure == "EGTF"
        assert fx.route.destination == "EGLL"
        assert fx.name is None
        assert fx.aircraft_registration is None
        assert fx.source_app is None

    def test_decodes_swift_style_z_timestamps(self):
        """Swift's JSONEncoder.iso8601 emits a 'Z' suffix; Python emits +00:00.

        Guards the Swift -> Python import direction: a payload exported by a
        Swift app must decode here. Relies on datetime.fromisoformat accepting
        'Z' (Python >= 3.11; package requires >= 3.12).
        """
        data = load_fixture("full.json")
        data["route"]["departure_time"] = "2026-06-01T09:00:00Z"
        data["route"]["arrival_time"] = "2026-06-01T11:15:00Z"
        fx = FlightExchange.from_dict(data)
        assert fx.route.departure_time == datetime(2026, 6, 1, 9, 0, 0, tzinfo=timezone.utc)
        assert fx.route.arrival_time == datetime(2026, 6, 1, 11, 15, 0, tzinfo=timezone.utc)
