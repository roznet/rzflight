"""Choosing the code an OurAirports row is stored under."""

import logging

import pandas as pd
import pytest

from euro_aip.utils.airport_codes import (
    assign_airport_codes,
    is_icao_code,
    select_airport_code,
)


def _values(series):
    return [None if pd.isna(v) else v for v in series]


def _frame(rows):
    return pd.DataFrame(rows, columns=["ident", "icao_code", "gps_code", "name"])


class TestIsIcaoCode:
    @pytest.mark.parametrize("code", ["EGTN", "lerj", " EGSY "])
    def test_valid(self, code):
        assert is_icao_code(code)

    @pytest.mark.parametrize(
        "code", ["GB-0007", "BI42", "EGT", "XRRT", "", None, float("nan")]
    )
    def test_invalid(self, code):
        assert not is_icao_code(code)


class TestSelectAirportCode:
    def test_placeholder_ident_takes_icao_code(self):
        # Enstone: OurAirports ident is a placeholder
        assert select_airport_code("GB-0007", "EGTN", "EGTN") == ("EGTN", None)

    def test_placeholder_ident_takes_gps_code_without_icao_code(self):
        assert select_airport_code("BA-0006", float("nan"), "LQKR") == ("LQKR", None)

    def test_superseded_ident_kept_as_alias(self):
        # Logroño: METAR still issued as LELO, AIP publishes LERJ
        assert select_airport_code("LELO", "LERJ", "LERJ") == ("LERJ", "LELO")

    def test_gps_code_supersedes_ident_without_icao_code(self):
        assert select_airport_code("EGDW", None, "EGDI") == ("EGDI", "EGDW")

    def test_icao_code_preferred_over_gps_code(self):
        assert select_airport_code("AB-0001", "EGAA", "EGBB") == ("EGAA", None)

    def test_x_prefixed_alternate_ignored(self):
        # Russian internal indicator, not an ICAO code
        assert select_airport_code("URRT", None, "XRRT") == ("URRT", None)

    def test_matching_codes_have_no_alias(self):
        assert select_airport_code("EGTK", "EGTK", "EGTK") == ("EGTK", None)

    def test_four_character_ident_kept_when_nothing_better(self):
        # Canadian aerodrome codes contain digits and were always stored
        assert select_airport_code("CAA2", None, "CAA2") == ("CAA2", None)

    def test_no_usable_code(self):
        assert select_airport_code("GB-0023", None, None) == (None, None)


class TestAssignAirportCodes:
    def test_codes_and_aliases(self):
        df = assign_airport_codes(_frame([
            ("GB-0007", "EGTN", "EGTN", "Enstone"),
            ("LELO", "LERJ", "LERJ", "Logroño"),
            ("EGTK", "EGTK", "EGTK", "Oxford"),
            ("GB-0023", None, None, "Shenstone Hall Farm"),
        ]))

        assert list(df["code"]) == ["EGTN", "LERJ", "EGTK"]
        assert _values(df["alt_ident"]) == [None, "LELO", None]
        # Runways join on the source ident, so it is left alone
        assert list(df["ident"]) == ["GB-0007", "LELO", "EGTK"]

    def test_existing_holder_keeps_contested_code(self, caplog):
        with caplog.at_level(logging.WARNING, logger="euro_aip.utils.airport_codes"):
            df = assign_airport_codes(_frame([
                ("IS-0016", "BISA", None, "Sauðárflugvöllur"),
                ("BISA", None, "BI42", "Sandá"),
            ]))

        assert list(df["name"]) == ["Sandá"]
        assert "IS-0016" in caplog.text

    def test_alias_that_is_another_airports_code_is_dropped(self):
        df = assign_airport_codes(_frame([
            ("DK-0009", "EKBH", None, "Bolhede"),
            ("EKBH", "EKAB", "EKAB", "Arnborg"),
        ]))

        assert dict(zip(df["name"], df["code"])) == {"Bolhede": "EKBH", "Arnborg": "EKAB"}
        assert _values(df["alt_ident"]) == [None, None]

    def test_without_icao_code_column(self):
        # Older OurAirports extracts have no icao_code column
        df = assign_airport_codes(pd.DataFrame({"ident": ["EGDW"], "gps_code": ["EGDI"]}))

        assert list(df["code"]) == ["EGDI"]
        assert _values(df["alt_ident"]) == ["EGDW"]
