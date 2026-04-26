"""Unit tests for the pure Field-15 tokenizer."""

import pytest

from euro_aip.models.field15 import (
    TokenKind,
    RouteToken,
    parse_field15,
    waypoints_of,
    annotations_of,
)


# ---------------------------------------------------------------------------
# Per-kind isolation
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("text, kind", [
    ("DCT", TokenKind.DIRECT),
    ("->", TokenKind.DIRECT),
    ("TO", TokenKind.DIRECT),
    ("IFR", TokenKind.FLIGHT_RULE),
    ("VFR", TokenKind.FLIGHT_RULE),
    ("N0180F080", TokenKind.SPEED_LEVEL),
    ("M082F350", TokenKind.SPEED_LEVEL),
    ("K0860S1500", TokenKind.SPEED_LEVEL),
    ("UL612", TokenKind.AIRWAY),
    ("N850", TokenKind.AIRWAY),
    ("UN858A", TokenKind.AIRWAY),
    ("EGTF", TokenKind.WAYPOINT),    # 4-letter ICAO airport
    ("BILGO", TokenKind.WAYPOINT),   # 5-letter named fix
    ("DVR", TokenKind.WAYPOINT),     # 3-letter VOR
    ("MID", TokenKind.WAYPOINT),     # ambiguous but a valid point name
    # Inline ICAO coordinates (FPL field 15)
    ("4830N00210E", TokenKind.COORDINATE),       # DM, 11 chars
    ("4629N01541E", TokenKind.COORDINATE),       # DM, 11 chars
    ("483012N0021034E", TokenKind.COORDINATE),   # DMS, 15 chars
    ("4830s00210w", TokenKind.COORDINATE),       # lowercase still classifies (uppercased before _classify)
    ("23NM", TokenKind.UNKNOWN),     # US-style fix, out of scope
    ("FOO1BAR", TokenKind.UNKNOWN),
    ("4830N0021Z", TokenKind.UNKNOWN),  # bad hemisphere letter — not a coord
    ("4830N0021", TokenKind.UNKNOWN),   # too short — not a coord
])
def test_classify_each_kind(text, kind):
    tokens = parse_field15(text)
    assert len(tokens) == 1
    assert tokens[0].kind is kind, f"{text!r} classified as {tokens[0].kind}, expected {kind}"


# ---------------------------------------------------------------------------
# The motivating example from the issue
# ---------------------------------------------------------------------------

def test_full_example_from_issue():
    route = "N0175F160 EGTF DCT BILGO/N0180F100 UL612 XIDIL VFR LSGS"
    tokens = parse_field15(route)
    kinds = [t.kind for t in tokens]
    assert kinds == [
        TokenKind.SPEED_LEVEL,
        TokenKind.WAYPOINT,
        TokenKind.DIRECT,
        TokenKind.WAYPOINT,    # BILGO (qualifier stripped)
        TokenKind.AIRWAY,
        TokenKind.WAYPOINT,
        TokenKind.FLIGHT_RULE,
        TokenKind.WAYPOINT,
    ]
    assert waypoints_of(tokens) == ["EGTF", "BILGO", "XIDIL", "LSGS"]
    # The BILGO qualifier is captured, not silently lost.
    bilgo = tokens[3]
    assert bilgo.value == "BILGO"
    assert bilgo.qualifier == "N0180F100"
    assert bilgo.raw == "BILGO/N0180F100"


# ---------------------------------------------------------------------------
# Order preservation
# ---------------------------------------------------------------------------

def test_order_preserved_across_mixed_input():
    tokens = parse_field15("EGTF DCT BILGO UL612 XIDIL LSGS")
    raws = [t.raw for t in tokens]
    assert raws == ["EGTF", "DCT", "BILGO", "UL612", "XIDIL", "LSGS"]


def test_annotations_of_preserves_order():
    tokens = parse_field15("EGTF DCT BILGO IFR XIDIL LSGS")
    anns = annotations_of(tokens)
    assert [t.value for t in anns] == ["DCT", "IFR"]


# ---------------------------------------------------------------------------
# Slash qualifier
# ---------------------------------------------------------------------------

def test_waypoint_with_qualifier_is_one_token():
    tokens = parse_field15("BILGO/N0180F100")
    assert len(tokens) == 1
    t = tokens[0]
    assert t.kind is TokenKind.WAYPOINT
    assert t.value == "BILGO"
    assert t.qualifier == "N0180F100"


def test_qualifier_absent_when_no_slash():
    tokens = parse_field15("BILGO")
    assert tokens[0].qualifier is None


# ---------------------------------------------------------------------------
# Degenerate input
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("text", ["", "   ", "\t\n"])
def test_blank_input_returns_empty_list(text):
    assert parse_field15(text) == []


def test_multiple_spaces_are_treated_as_single_separator():
    tokens = parse_field15("EGTF    DCT\t\tBILGO  LSGS")
    assert [t.value for t in tokens] == ["EGTF", "DCT", "BILGO", "LSGS"]


# ---------------------------------------------------------------------------
# Case handling
# ---------------------------------------------------------------------------

def test_lowercase_input_is_classified_after_upper():
    tokens = parse_field15("egtf dct bilgo lsgs")
    assert [t.kind for t in tokens] == [
        TokenKind.WAYPOINT,
        TokenKind.DIRECT,
        TokenKind.WAYPOINT,
        TokenKind.WAYPOINT,
    ]
    # value normalized to upper, raw preserved.
    assert tokens[0].value == "EGTF"
    assert tokens[0].raw == "egtf"


def test_mixed_case_qualifier_is_uppercased_in_value():
    tokens = parse_field15("bilgo/n0180f100")
    t = tokens[0]
    assert t.value == "BILGO"
    assert t.qualifier == "N0180F100"
    assert t.raw == "bilgo/n0180f100"


# ---------------------------------------------------------------------------
# Position / round-trip
# ---------------------------------------------------------------------------

def test_position_is_char_offset_in_original_string():
    route = "EGTF DCT BILGO LSGS"
    tokens = parse_field15(route)
    assert tokens[0].position == 0
    assert tokens[1].position == route.index("DCT")
    assert tokens[2].position == route.index("BILGO")
    assert tokens[3].position == route.index("LSGS")


def test_round_trip_up_to_whitespace_normalization():
    route = "N0175F160 EGTF DCT BILGO/N0180F100 UL612 XIDIL VFR LSGS"
    tokens = parse_field15(route)
    assert " ".join(t.raw for t in tokens) == route


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def test_waypoints_of_excludes_all_non_waypoints():
    tokens = parse_field15("N0175F160 EGTF DCT UL612 IFR BILGO LSGS")
    assert waypoints_of(tokens) == ["EGTF", "BILGO", "LSGS"]


def test_waypoints_of_includes_inline_coordinates():
    """Inline coords are real route points and must flow through ``waypoints_of``
    so they're handled like any other middle waypoint by the resolver."""
    tokens = parse_field15("EDFE DCT LUGEM DCT 4629N01541E DCT LJSK")
    assert waypoints_of(tokens) == ["EDFE", "LUGEM", "4629N01541E", "LJSK"]


def test_annotations_of_returns_route_tokens_not_strings():
    tokens = parse_field15("EGTF DCT BILGO LSGS")
    anns = annotations_of(tokens)
    assert all(isinstance(t, RouteToken) for t in anns)
    assert [t.kind for t in anns] == [TokenKind.DIRECT]


# ---------------------------------------------------------------------------
# Airway vs waypoint disambiguation (pure-regex level — the RouteResolver
# adds a DB-based demotion pass on top of this)
# ---------------------------------------------------------------------------

def test_airway_requires_a_digit():
    # 5 letters, no digit → WAYPOINT, never AIRWAY
    assert parse_field15("ABCDE")[0].kind is TokenKind.WAYPOINT


def test_speed_level_not_confused_with_airway():
    # N0180F080 matches speed/level (letter+digits+letter+digits), not airway.
    assert parse_field15("N0180F080")[0].kind is TokenKind.SPEED_LEVEL
