"""An airport stored under its current ICAO code stays findable by its previous one."""

import sqlite3

import pytest

from euro_aip.models.airport import Airport
from euro_aip.models.border_crossing_entry import BorderCrossingEntry
from euro_aip.models.euro_aip_model import EuroAipModel
from euro_aip.models.route_resolver import RouteResolver
from euro_aip.storage.database_storage import DatabaseStorage


def _airport(ident, lat, lon, name=None, alt_ident=None, country=None):
    airport = Airport(
        ident=ident,
        alt_ident=alt_ident,
        name=name or f"{ident} Field",
        latitude_deg=lat,
        longitude_deg=lon,
        iso_country=country,
    )
    airport.add_source("test_source")
    return airport


@pytest.fixture
def model():
    model = EuroAipModel()
    for airport in [
        _airport("LEMD", 40.4719, -3.5626, country="ES"),
        _airport("LERJ", 42.4610, -2.3222, name="Logroño-Agoncillo Airport",
                 alt_ident="LELO", country="ES"),
        _airport("LFBO", 43.6291, 1.3638, country="FR"),
    ]:
        model.add_airport(airport)
    model.sources_used.add("test_source")
    return model


class TestFindAirportByCode:
    def test_current_and_previous_code(self, model):
        assert model.find_airport_by_code("LERJ").name == "Logroño-Agoncillo Airport"
        assert model.find_airport_by_code("lelo").ident == "LERJ"

    def test_unknown_code(self, model):
        assert model.find_airport_by_code("EGTN") is None
        assert model.find_airport_by_code("LEL") is None
        assert model.find_airport_by_code("") is None

    def test_exact_ident_wins_over_alias(self):
        model = EuroAipModel()
        model.add_airport(_airport("EKBH", 55.96, 8.81, name="Bolhede Glider Field"))
        model.add_airport(_airport("EKAB", 56.00, 9.00, name="Arnborg", alt_ident="EKBH"))

        assert model.find_airport_by_code("EKBH").name == "Bolhede Glider Field"

    def test_collection_lookup(self, model):
        assert model.airports.find_by_code("LELO").ident == "LERJ"
        # Dict-style access stays exact
        assert model.airports.get("LELO") is None

    def test_near_route_accepts_previous_code(self, model):
        nearby = model.find_airports_near_route(["LELO"], distance_nm=5)

        assert [entry["airport"].ident for entry in nearby] == ["LERJ"]


class TestRouteResolver:
    def test_endpoint_by_previous_code(self, model):
        route = RouteResolver(model).resolve("LELO LFBO")

        assert route.departure == "LERJ"
        assert route.departure_coords == (42.4610, -2.3222)

    def test_middle_point_by_previous_code(self, model):
        route = RouteResolver(model).resolve("LEMD LELO LFBO")

        assert route.waypoints == ["LERJ"]
        assert route.rejected_waypoints == []


class TestBorderCrossing:
    def test_entry_under_previous_code_is_filed_under_current(self, model):
        model.add_border_crossing_entry(BorderCrossingEntry(
            airport_name="Logroño-Agoncillo", country_iso="ES", icao_code="LELO",
            is_airport=True, source="test",
        ))
        model.update_all_derived_fields()

        assert model.get_border_crossing_entry("ES", "LERJ") is not None
        assert model.airports["LERJ"].point_of_entry is True


class TestStorage:
    def test_alt_ident_round_trip(self, tmp_path, model):
        path = str(tmp_path / "nav.db")
        DatabaseStorage(path).save_model(model)
        loaded = DatabaseStorage(path).load_model()

        assert loaded.airports["LERJ"].alt_ident == "LELO"
        assert loaded.airports["LEMD"].alt_ident is None
        assert loaded.find_airport_by_code("LELO").ident == "LERJ"

    def test_alt_ident_column_added_by_migration(self, tmp_path, model):
        path = str(tmp_path / "nav.db")
        DatabaseStorage(path).save_model(model)
        with sqlite3.connect(path) as conn:
            conn.execute("ALTER TABLE airports DROP COLUMN alt_ident")
            conn.execute("UPDATE model_metadata SET value = '3' WHERE key = 'schema_version'")

        migrated = DatabaseStorage(path)

        with sqlite3.connect(path) as conn:
            cols = {r[1] for r in conn.execute("PRAGMA table_info(airports)")}
            version = conn.execute(
                "SELECT value FROM model_metadata WHERE key = 'schema_version'"
            ).fetchone()[0]
        assert "alt_ident" in cols
        assert version == "4"
        assert migrated.load_model().airports["LERJ"].alt_ident is None
