"""
Tests for the modern queryable collections API.

These tests demonstrate the new fluent, composable query interface and verify
that it works correctly with the Euro AIP model.
"""

import pytest
from euro_aip.models.euro_aip_model import EuroAipModel
from euro_aip.models.airport import Airport
from euro_aip.models.procedure import Procedure
from euro_aip.models.runway import Runway
from euro_aip.models.airport_collection import AirportCollection
from euro_aip.models.procedure_collection import ProcedureCollection


class TestQueryableCollection:
    """Test base QueryableCollection functionality."""

    def test_filter_with_predicate(self):
        """Test filtering with a custom predicate."""
        airports = [
            Airport(ident="EGLL", name="Heathrow", iso_country="GB"),
            Airport(ident="LFPG", name="Charles de Gaulle", iso_country="FR"),
            Airport(ident="EDDF", name="Frankfurt", iso_country="DE"),
        ]

        collection = AirportCollection(airports)
        french = collection.filter(lambda a: a.iso_country == "FR").all()

        assert len(french) == 1
        assert french[0].ident == "LFPG"

    def test_where_attribute_matching(self):
        """Test filtering with attribute matching."""
        airports = [
            Airport(ident="EGLL", name="Heathrow", iso_country="GB"),
            Airport(ident="LFPG", name="Charles de Gaulle", iso_country="FR"),
        ]

        collection = AirportCollection(airports)
        result = collection.where(ident="EGLL").first()

        assert result is not None
        assert result.ident == "EGLL"
        assert result.name == "Heathrow"

    def test_first(self):
        """Test getting first item."""
        airports = [
            Airport(ident="EGLL", name="Heathrow", iso_country="GB"),
            Airport(ident="LFPG", name="Charles de Gaulle", iso_country="FR"),
        ]

        collection = AirportCollection(airports)

        # First from filtered collection
        first = collection.where(iso_country="FR").first()
        assert first is not None
        assert first.ident == "LFPG"

        # First from empty collection
        empty = collection.where(iso_country="XX").first()
        assert empty is None

    def test_count(self):
        """Test counting items."""
        airports = [
            Airport(ident=f"TEST{i}", iso_country="GB")
            for i in range(5)
        ]

        collection = AirportCollection(airports)
        assert collection.count() == 5
        assert collection.where(ident="TEST0").count() == 1
        assert collection.where(ident="NONE").count() == 0

    def test_exists(self):
        """Test existence checking."""
        airports = [Airport(ident="EGLL", iso_country="GB")]

        collection = AirportCollection(airports)
        assert collection.exists()
        assert collection.where(iso_country="GB").exists()
        assert not collection.where(iso_country="FR").exists()

    def test_group_by(self):
        """Test grouping by key function."""
        airports = [
            Airport(ident="EGLL", iso_country="GB"),
            Airport(ident="EGKK", iso_country="GB"),
            Airport(ident="LFPG", iso_country="FR"),
        ]

        collection = AirportCollection(airports)
        by_country = collection.group_by(lambda a: a.iso_country)

        assert len(by_country) == 2
        assert len(by_country["GB"]) == 2
        assert len(by_country["FR"]) == 1

    def test_order_by(self):
        """Test sorting."""
        airports = [
            Airport(ident="C", name="Charlie"),
            Airport(ident="A", name="Alpha"),
            Airport(ident="B", name="Bravo"),
        ]

        collection = AirportCollection(airports)
        sorted_airports = collection.order_by(lambda a: a.name or '').all()

        assert sorted_airports[0].name == "Alpha"
        assert sorted_airports[1].name == "Bravo"
        assert sorted_airports[2].name == "Charlie"

    def test_take_and_skip(self):
        """Test pagination with take and skip."""
        airports = [Airport(ident=f"TEST{i}") for i in range(10)]

        collection = AirportCollection(airports)

        # Take first 3
        first_three = collection.take(3).all()
        assert len(first_three) == 3
        assert first_three[0].ident == "TEST0"

        # Skip 5, take 3
        page_two = collection.skip(5).take(3).all()
        assert len(page_two) == 3
        assert page_two[0].ident == "TEST5"

    def test_iteration(self):
        """Test that collections are iterable."""
        airports = [Airport(ident=f"TEST{i}") for i in range(3)]
        collection = AirportCollection(airports)

        idents = [a.ident for a in collection]
        assert idents == ["TEST0", "TEST1", "TEST2"]

    def test_indexing(self):
        """Test indexing and slicing."""
        airports = [Airport(ident=f"TEST{i}") for i in range(5)]
        collection = AirportCollection(airports)

        # Index access
        assert collection[0].ident == "TEST0"
        assert collection[-1].ident == "TEST4"

        # Slice access
        subset = collection[1:3]
        assert len(subset) == 2
        assert subset[0].ident == "TEST1"


class TestAirportCollection:
    """Test AirportCollection domain-specific filters."""

    def test_by_country(self):
        """Test country filtering."""
        airports = [
            Airport(ident="EGLL", iso_country="GB"),
            Airport(ident="LFPG", iso_country="FR"),
            Airport(ident="EDDF", iso_country="DE"),
        ]

        collection = AirportCollection(airports)
        french = collection.by_country("FR").all()

        assert len(french) == 1
        assert french[0].ident == "LFPG"

    def test_by_countries(self):
        """Test multiple country filtering."""
        airports = [
            Airport(ident="EGLL", iso_country="GB"),
            Airport(ident="LFPG", iso_country="FR"),
            Airport(ident="EDDF", iso_country="DE"),
            Airport(ident="LEMD", iso_country="ES"),
        ]

        collection = AirportCollection(airports)
        result = collection.by_countries(["FR", "DE"]).all()

        assert len(result) == 2
        idents = {a.ident for a in result}
        assert idents == {"LFPG", "EDDF"}

    def test_with_runways(self):
        """Test runway filtering."""
        airport_with = Airport(ident="WITH", runways=[Runway(airport_ident="WITH")])
        airport_without = Airport(ident="WITHOUT", runways=[])

        collection = AirportCollection([airport_with, airport_without])
        with_runways = collection.with_runways().all()

        assert len(with_runways) == 1
        assert with_runways[0].ident == "WITH"

    def test_with_min_runway_length(self):
        """Test minimum runway length filtering."""
        airports = [
            Airport(ident="LONG", longest_runway_length_ft=8000),
            Airport(ident="SHORT", longest_runway_length_ft=2000),
            Airport(ident="NONE", longest_runway_length_ft=None),
        ]

        collection = AirportCollection(airports)
        long_enough = collection.with_min_runway_length(3000).all()

        assert len(long_enough) == 1
        assert long_enough[0].ident == "LONG"

    def test_chaining_filters(self):
        """Test chaining multiple filters."""
        airports = [
            Airport(ident="PERFECT", iso_country="FR",
                   has_hard_runway=True, longest_runway_length_ft=5000),
            Airport(ident="NO_HARD", iso_country="FR",
                   has_hard_runway=False, longest_runway_length_ft=5000),
            Airport(ident="TOO_SHORT", iso_country="FR",
                   has_hard_runway=True, longest_runway_length_ft=2000),
            Airport(ident="WRONG_COUNTRY", iso_country="GB",
                   has_hard_runway=True, longest_runway_length_ft=5000),
        ]

        collection = AirportCollection(airports)
        result = collection.by_country("FR") \
                          .with_hard_runway() \
                          .with_min_runway_length(3000) \
                          .all()

        assert len(result) == 1
        assert result[0].ident == "PERFECT"

    def test_dict_style_getitem(self):
        """Test dict-style access by ICAO code."""
        airports = [
            Airport(ident="EGLL", name="Heathrow", iso_country="GB"),
            Airport(ident="LFPG", name="Charles de Gaulle", iso_country="FR"),
            Airport(ident="EDDF", name="Frankfurt", iso_country="DE"),
        ]

        collection = AirportCollection(airports)

        # Dict-style lookup by ICAO
        heathrow = collection['EGLL']
        assert heathrow.ident == "EGLL"
        assert heathrow.name == "Heathrow"

        # List-style indexing still works
        first = collection[0]
        assert first.ident == "EGLL"

        # Slicing still works
        first_two = collection[0:2]
        assert len(first_two) == 2

    def test_dict_style_getitem_not_found(self):
        """Test dict-style access raises KeyError for missing airport."""
        airports = [
            Airport(ident="EGLL", name="Heathrow", iso_country="GB"),
        ]

        collection = AirportCollection(airports)

        with pytest.raises(KeyError, match="ZZZZ"):
            _ = collection['ZZZZ']

    def test_dict_style_contains(self):
        """Test 'in' operator for ICAO code containment check."""
        airports = [
            Airport(ident="EGLL", name="Heathrow", iso_country="GB"),
            Airport(ident="LFPG", name="Charles de Gaulle", iso_country="FR"),
        ]

        collection = AirportCollection(airports)

        # Check ICAO codes
        assert 'EGLL' in collection
        assert 'LFPG' in collection
        assert 'ZZZZ' not in collection

    def test_dict_style_get(self):
        """Test get() method with default value."""
        airports = [
            Airport(ident="EGLL", name="Heathrow", iso_country="GB"),
        ]

        collection = AirportCollection(airports)

        # Get existing airport
        heathrow = collection.get('EGLL')
        assert heathrow is not None
        assert heathrow.ident == "EGLL"

        # Get missing airport with default None
        missing = collection.get('ZZZZ')
        assert missing is None

        # Get missing airport with custom default
        default = Airport(ident="DEFAULT")
        result = collection.get('ZZZZ', default=default)
        assert result is default

    def test_dict_style_with_filtering(self):
        """Test dict-style access works on filtered collections."""
        airports = [
            Airport(ident="EGLL", name="Heathrow", iso_country="GB"),
            Airport(ident="LFPG", name="Charles de Gaulle", iso_country="FR"),
            Airport(ident="EDDF", name="Frankfurt", iso_country="DE"),
        ]

        collection = AirportCollection(airports)

        # Filter then lookup
        french = collection.by_country("FR")
        assert 'LFPG' in french
        assert 'EGLL' not in french

        cdg = french['LFPG']
        assert cdg.name == "Charles de Gaulle"

        # KeyError on filtered collection
        with pytest.raises(KeyError):
            _ = french['EGLL']  # UK airport not in French filter


class TestProcedureCollection:
    """Test ProcedureCollection domain-specific filters."""

    def test_approaches(self):
        """Test approach filtering."""
        procedures = [
            Procedure(name="ILS 09L", procedure_type="approach"),
            Procedure(name="SID 27R", procedure_type="departure"),
            Procedure(name="STAR 09L", procedure_type="arrival"),
        ]

        collection = ProcedureCollection(procedures)
        approaches = collection.approaches().all()

        assert len(approaches) == 1
        assert approaches[0].name == "ILS 09L"

    def test_by_type(self):
        """Test approach type filtering."""
        procedures = [
            Procedure(name="ILS 09L", procedure_type="approach", approach_type="ILS"),
            Procedure(name="RNAV 09L", procedure_type="approach", approach_type="RNAV"),
            Procedure(name="VOR 27R", procedure_type="approach", approach_type="VOR"),
        ]

        collection = ProcedureCollection(procedures)
        ils = collection.by_type("ILS").all()

        assert len(ils) == 1
        assert ils[0].name == "ILS 09L"

    def test_by_runway(self):
        """Test runway filtering."""
        procedures = [
            Procedure(name="ILS 09L", procedure_type="approach", runway_ident="09L"),
            Procedure(name="RNAV 09L", procedure_type="approach", runway_ident="09L"),
            Procedure(name="ILS 27R", procedure_type="approach", runway_ident="27R"),
        ]

        collection = ProcedureCollection(procedures)
        rwy_09l = collection.by_runway("09L").all()

        assert len(rwy_09l) == 2

    def test_most_precise(self):
        """Test getting most precise approach."""
        procedures = [
            Procedure(name="VOR 09L", procedure_type="approach",
                     approach_type="VOR", runway_ident="09L"),
            Procedure(name="ILS 09L", procedure_type="approach",
                     approach_type="ILS", runway_ident="09L"),
            Procedure(name="RNAV 09L", procedure_type="approach",
                     approach_type="RNAV", runway_ident="09L"),
        ]

        collection = ProcedureCollection(procedures)
        best = collection.approaches().by_runway("09L").most_precise()

        assert best is not None
        assert best.approach_type == "ILS"

    def test_chaining_procedure_filters(self):
        """Test chaining procedure filters."""
        procedures = [
            Procedure(name="ILS 09L", procedure_type="approach",
                     approach_type="ILS", runway_ident="09L"),
            Procedure(name="ILS 27R", procedure_type="approach",
                     approach_type="ILS", runway_ident="27R"),
            Procedure(name="RNAV 09L", procedure_type="approach",
                     approach_type="RNAV", runway_ident="09L"),
            Procedure(name="SID 09L", procedure_type="departure",
                     runway_ident="09L"),
        ]

        collection = ProcedureCollection(procedures)
        result = collection.approaches() \
                          .by_type("ILS") \
                          .by_runway("09L") \
                          .all()

        assert len(result) == 1
        assert result[0].name == "ILS 09L"


class TestBackwardCompatibility:
    """Test that legacy methods still work with deprecation warnings."""

    def test_legacy_methods_work(self):
        """Verify legacy methods still function."""
        model = EuroAipModel()

        # Add test airport
        airport = Airport(ident="EGLL", iso_country="GB")
        model.add_airport(airport)

        # Legacy method should still work (with warning)
        import warnings
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = model.get_airports_by_country("GB")

            # Should have one deprecation warning
            assert len(w) == 1
            assert issubclass(w[0].category, DeprecationWarning)
            assert "deprecated" in str(w[0].message).lower()

        # But should still return correct result
        assert len(result) == 1
        assert result[0].ident == "EGLL"


class TestIntegration:
    """Integration tests for common use cases."""

    def test_find_suitable_airports(self):
        """Test a realistic airport search scenario."""
        model = EuroAipModel()

        # Add test airports
        airports = [
            Airport(ident="PERFECT", iso_country="FR",
                   has_hard_runway=True, longest_runway_length_ft=5000,
                   avgas=True, jet_a=True),
            Airport(ident="NO_FUEL", iso_country="FR",
                   has_hard_runway=True, longest_runway_length_ft=5000,
                   avgas=False, jet_a=False),
            Airport(ident="TOO_SHORT", iso_country="FR",
                   has_hard_runway=True, longest_runway_length_ft=2000,
                   avgas=True, jet_a=True),
        ]

        for airport in airports:
            model.add_airport(airport)

        # Find suitable airports
        suitable = model.airports.by_country("FR") \
                                 .with_hard_runway() \
                                 .with_min_runway_length(3000) \
                                 .with_fuel(avgas=True, jet_a=True) \
                                 .all()

        assert len(suitable) == 1
        assert suitable[0].ident == "PERFECT"

    def test_airport_procedure_query(self):
        """Test querying procedures from an airport."""
        airport = Airport(ident="EGLL")

        # Add procedures
        procedures = [
            Procedure(name="ILS 09L", procedure_type="approach",
                     approach_type="ILS", runway_ident="09L"),
            Procedure(name="RNAV 09L", procedure_type="approach",
                     approach_type="RNAV", runway_ident="09L"),
            Procedure(name="SID 09L", procedure_type="departure",
                     runway_ident="09L"),
        ]

        for proc in procedures:
            airport.add_procedure(proc)

        # Query using the new API
        approaches = airport.procedures_query.approaches().all()
        assert len(approaches) == 2

        ils = airport.procedures_query.approaches().by_type("ILS").all()
        assert len(ils) == 1

        best = airport.procedures_query.approaches().by_runway("09L").most_precise()
        assert best.approach_type == "ILS"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
