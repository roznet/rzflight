"""End-to-end parse + resolve tests using real filed routes.

Fixture is a frozen snapshot of airports/waypoints extracted from nav.db for
the identifiers mentioned in a handful of real ICAO Field-15 routes. We
keep the data and the routes together so the observed parser + resolver
behavior can be pinned — including edge cases worth preserving:

- SID/STAR names (PERUS1N, SOKDU1V, KATHY1V, …) classified as UNKNOWN and
  filtered out of the waypoint list.
- POINT/QUALIFIER splits (BILGO/N0178F120) captured in ``qualifier``.
- Inline DMS coordinates tokenised as UNKNOWN with the lon half in
  ``qualifier`` (parser keeps going, resolver skips them).
- Multi-candidate disambiguation via ``resolve_point_near`` — ABB has a
  US VORTAC and a French VORDME; SFD has a UK VORDME and a Venezuelan one;
  the proximity-aware selection must pick the European candidate on these
  European routes.
- AIRWAY→WAYPOINT demotion on Y8: Y8 is both a real airway identifier and a
  waypoint name in nav.db (a Canadian NDB). The demotion pass promotes it,
  then the detour gate correctly rejects it. Both halves of that behavior
  must hold.

If nav.db upstream changes (points renamed, coords shifted), these tests
stay green because the fixture is a frozen copy — we're testing the
parser/resolver, not the live database.
"""

from __future__ import annotations

import pytest

from euro_aip.models import EuroAipModel, Airport, Waypoint
from euro_aip.models.field15 import TokenKind, parse_field15
from euro_aip.models.route_resolver import RouteResolver


# Extracted 2026-04-22 from flyfun-apps/data/nav.db.
AIRPORTS = [
    ("EGLC", 51.505299, 0.055278),
    ("EGMD", 50.956246, 0.939074),
    ("EGSU", 52.090801, 0.131944),
    ("EGTF", 51.348099, -0.558889),
    ("LFAT", 50.518284, 1.621656),
    ("LFMD", 43.547998, 6.955176),
    ("LFQA", 49.208698, 4.15658),
    ("LFRD", 48.5877, -2.07996),
    ("LSGS", 46.219166, 7.326944),
]

# (name, lat, lon, point_type, source_id) — all candidates preserved so the
# multi-candidate selection path in resolve_point_near is exercised.
WAYPOINTS = [
    ("ABB", 38.58879852294922, -85.63600158691406, "VORTAC", "src_0"),
    ("ABB", 50.135101318359375, 1.8546899557113647, "VORDME", "src_1"),
    ("BENAR", 48.253055555555555, 0.7444444444444444, "5LNC", "src_0"),
    ("BENAR", 48.253055555555555, 0.7444444444444444, "5LNC", "src_1"),
    ("BILGO", 49.901944444444446, 3.4472222222222224, "5LNC", "src_0"),
    ("CMB", 50.22805555555556, 3.151388888888889, "VORDME", "src_0"),
    ("CMB", 50.22809982299805, 3.1514999866485596, "VORTAC", "src_1"),
    ("DIKOL", 49.1375, 4.049166666666666, "5LNC", "src_0"),
    ("DIKOL", 49.1375, 4.049166666666666, "5LNC", "src_1"),
    ("DJL", 47.270833333333336, 5.097222222222222, "VORDME", "src_0"),
    ("DJL", 47.27080154418945, 5.097330093383789, "VORDME", "src_1"),
    ("DOMOD", 47.86277777777778, 1.2858333333333332, "5LNC", "src_0"),
    ("DRAKE", 50.20944444444445, -0.07611111111111112, "5LNC", "src_0"),
    ("GWC", 50.85530090332031, -0.7566670179367065, "VORDME", "src_0"),
    ("LGL", 48.79055555555556, 0.5302777777777778, "VORDME", "src_0"),
    ("LGL", 48.79059982299805, 0.5302780270576477, "VOR", "src_1"),
    ("MINQI", 49.03333333333333, -2.0569444444444445, "5LNC", "src_0"),
    ("MINQI", 49.03333333333333, -2.0569444444444445, "5LNC", "src_1"),
    ("MINQI", 49.03333333333333, -2.0569444444444445, "5LNC", "src_2"),
    ("NEDUL", 50.66611111111111, -1.5477777777777777, "5LNC", "src_0"),
    ("OCK", 51.30500030517578, -0.4472219944000244, "VORDME", "src_0"),
    ("ORTAC", 49.99916666666667, -2.005, "5LNC", "src_0"),
    ("ORTAC", 49.99916666666667, -2.005, "5LNC", "src_1"),
    ("PERON", 49.9125, 2.8400000000000003, "5LNC", "src_0"),
    ("PERON", 49.9125, 2.8400000000000003, "5LNC", "src_1"),
    ("PERUS", 44.15333333333333, 6.103333333333333, "5LNC", "src_0"),
    ("REM", 49.31159973144531, 4.045360088348389, "VORTAC", "src_0"),
    ("RESPO", 47.83277777777778, 5.608055555555556, "5LNC", "src_0"),
    ("RESPO", 47.83280555555556, 5.608, "5LNC", "src_1"),
    ("RINTI", 51.032777777777774, 1.6155555555555556, "5LNC", "src_0"),
    ("RINTI", 51.032777777777774, 1.6155555555555556, "5LNC", "src_1"),
    ("RLP", 47.906388888888884, 5.2491666666666665, "DME", "src_0"),
    ("RLP", 47.90629959106445, 5.249169826507568, "VORDME", "src_1"),
    ("SFD", 50.76060104370117, 0.12194400280714035, "VORDME", "src_0"),
    ("SFD", 7.885560035705566, -67.43730163574219, "VORDME", "src_1"),
    ("SITET", 50.1, 0.0, "5LNC", "src_0"),
    ("SITET", 50.1, 0.0, "5LNC", "src_1"),
    ("SITET", 50.1, 0.0, "5LNC", "src_2"),
    ("SOMDA", 48.33777777777778, 4.2444444444444445, "5LNC", "src_0"),
    ("TRACA", 50.85166666666667, 1.9683333333333335, "5LNC", "src_0"),
    ("VATRI", 48.79333333333333, 4.058333333333334, "5LNC", "src_0"),
    ("VERMA", 50.0, 3.243333333333333, "5LNC", "src_0"),
    ("VUCTU", 48.22805555555556, 4.822222222222222, "5LNC", "src_0"),
    ("WAFFU", 50.5825, 0.3497222222222222, "5LNC", "src_0"),
    ("XORBI", 49.91777777777777, 2.4511111111111115, "5LNC", "src_0"),
    ("Y8", 45.84749984741211, -72.3989028930664, "NDB", "src_0"),
]


@pytest.fixture(scope="module")
def model():
    m = EuroAipModel()
    for ident, lat, lon in AIRPORTS:
        m.add_airport(Airport(ident=ident, latitude_deg=lat, longitude_deg=lon))
    for name, lat, lon, pt, sid in WAYPOINTS:
        m.add_waypoint(
            Waypoint(
                name=name,
                latitude_deg=lat,
                longitude_deg=lon,
                point_type=pt,
                source_id=sid,
            )
        )
    return m


@pytest.fixture(scope="module")
def resolver(model):
    return RouteResolver(model)


# ---------------------------------------------------------------------------
# Per-route end-to-end tests
# ---------------------------------------------------------------------------

def test_route1_sid_star_names_dropped(resolver):
    """SID/STAR names (M25J7, M25J5, KBMD2, KBMD3) must tokenise as UNKNOWN
    and be filtered out of the waypoint list."""
    route = "EGTF OCK M25J7 M25J5 KBMD2 KBMD3 EGMD LFAT"

    tokens = parse_field15(route)
    kinds = [t.kind for t in tokens]
    assert kinds == [
        TokenKind.WAYPOINT,   # EGTF
        TokenKind.WAYPOINT,   # OCK
        TokenKind.UNKNOWN,    # M25J7
        TokenKind.UNKNOWN,    # M25J5
        TokenKind.UNKNOWN,    # KBMD2
        TokenKind.UNKNOWN,    # KBMD3
        TokenKind.WAYPOINT,   # EGMD
        TokenKind.WAYPOINT,   # LFAT
    ]

    r = resolver.resolve(route)
    assert r.departure == "EGTF"
    assert r.destination == "LFAT"
    assert r.waypoints == ["OCK", "EGMD"]
    assert r.rejected_waypoints == []


def test_route2_sids_and_airways_filtered(resolver):
    """SIDs (PERUS1N, SOKDU1V) → UNKNOWN; airways (A3, H20, A34, L151) →
    AIRWAY; POINT/QUALIFIER split on BENAR. NOTGI and EVATA are not in the
    fixture — they stay unresolved."""
    route = (
        "LFMD PERUS1N PERUS A3 DOMOD H20 BENAR/N0178F120 H20 LGL A34 "
        "SITET L151 DRAKE NOTGI EVATA SOKDU1V EGTF"
    )

    tokens = parse_field15(route)
    # Locate BENAR and verify qualifier captured
    benar = next(t for t in tokens if t.value == "BENAR")
    assert benar.qualifier == "N0178F120"

    # Every SID/STAR must be UNKNOWN; every airway must be AIRWAY.
    by_val = {t.value: t.kind for t in tokens}
    assert by_val["PERUS1N"] is TokenKind.UNKNOWN
    assert by_val["SOKDU1V"] is TokenKind.UNKNOWN
    assert by_val["A3"] is TokenKind.AIRWAY
    assert by_val["A34"] is TokenKind.AIRWAY
    assert by_val["H20"] is TokenKind.AIRWAY
    assert by_val["L151"] is TokenKind.AIRWAY

    r = resolver.resolve(route)
    assert r.departure == "LFMD"
    assert r.destination == "EGTF"
    assert r.waypoints == ["PERUS", "DOMOD", "BENAR", "LGL", "SITET", "DRAKE"]
    assert r.rejected_waypoints == []


def test_route3_speed_level_and_qualifiers(resolver):
    """The long EGTF→LSGS route with speed/level prefix, multiple
    POINT/QUALIFIER splits, B3/Y112 airways and a trailing VFR."""
    route = (
        "EGTF N0155F040 GWC DCT SFD/N0155F070 DCT RINTI/N0160F070 B3 TRACA "
        "B3 CMB/N0160F090 B3 VERMA B3 BILGO B3 REM B3 DIKOL/N0163F100 B3 "
        "VATRI B3 VUCTU B3 RLP/N0165F100 Y112 RESPO VFR LSGS"
    )

    tokens = parse_field15(route)
    # N0155F040 at position 1 is a speed/level, not a waypoint.
    assert tokens[1].value == "N0155F040"
    assert tokens[1].kind is TokenKind.SPEED_LEVEL
    # Trailing VFR is a flight-rule marker.
    assert tokens[-2].kind is TokenKind.FLIGHT_RULE
    # Both DCTs classify as DIRECT (and therefore drop out of waypoints).
    dct_kinds = [t.kind for t in tokens if t.value == "DCT"]
    assert dct_kinds == [TokenKind.DIRECT, TokenKind.DIRECT]
    # Spot-check a couple of qualifier splits.
    qualifiers = {t.value: t.qualifier for t in tokens if t.qualifier}
    assert qualifiers["SFD"] == "N0155F070"
    assert qualifiers["RINTI"] == "N0160F070"
    assert qualifiers["DIKOL"] == "N0163F100"

    r = resolver.resolve(route)
    assert r.departure == "EGTF"
    assert r.destination == "LSGS"
    # 13 waypoints, order preserved, speed/level + VFR + airways all dropped.
    assert r.waypoints == [
        "GWC", "SFD", "RINTI", "TRACA", "CMB", "VERMA", "BILGO",
        "REM", "DIKOL", "VATRI", "VUCTU", "RLP", "RESPO",
    ]
    assert r.rejected_waypoints == []


def test_route3_sfd_proximity_picks_uk_not_venezuela(resolver):
    """SFD has two candidates: UK (50.76, 0.12) and Venezuela (7.88, -67.44).
    On an EGTF→LSGS route the proximity-aware selection must pick UK."""
    route = "EGTF SFD LSGS"
    r = resolver.resolve(route)
    sfd = next(w for w in r.waypoint_coords if w.name == "SFD")
    assert sfd.latitude == pytest.approx(50.76, abs=0.01)
    assert sfd.longitude == pytest.approx(0.12, abs=0.01)


def test_route4_dms_tokens_tokenise_as_unknown(resolver):
    """Inline DMS coordinates are tokenised as UNKNOWN (with the lon half
    landing in ``qualifier`` because of the `/` split) and the resolver
    skips them. Only the actual ICAO points survive."""
    route = (
        'EGSU 52°07\'09"N/0°23\'49"E 52°04\'14"N/0°36\'46"E 51°58\'42"N/0°37\'35"E '
        '51°42\'56"N/0°13\'28"E 51°40\'19"N/0°06\'24"E 51°35\'58"N/0°01\'38"E EGLC '
        '51°23\'38"N/0°00\'16"E 51°19\'28"N/0°10\'13"W 51°18\'33"N/0°28\'38"W EGTF'
    )

    tokens = parse_field15(route)
    dms_tokens = [t for t in tokens if "°" in t.value]
    assert len(dms_tokens) == 9
    assert all(t.kind is TokenKind.UNKNOWN for t in dms_tokens)
    # Qualifier captures the part after the '/' (the longitude half).
    assert all(t.qualifier and ("E" in t.qualifier or "W" in t.qualifier) for t in dms_tokens)

    r = resolver.resolve(route)
    assert r.departure == "EGSU"
    assert r.destination == "EGTF"
    assert r.waypoints == ["EGLC"]


def test_route5_clean_mixed_airways_and_qualifiers(resolver):
    route = "LFQA DIKOL B3 BILGO/N0177F130 H20 PERON/N0179F140 H20 XORBI H40 ABB LFAT"

    tokens = parse_field15(route)
    bilgo = next(t for t in tokens if t.value == "BILGO")
    peron = next(t for t in tokens if t.value == "PERON")
    assert bilgo.qualifier == "N0177F130"
    assert peron.qualifier == "N0179F140"

    r = resolver.resolve(route)
    assert r.departure == "LFQA"
    assert r.destination == "LFAT"
    assert r.waypoints == ["DIKOL", "BILGO", "PERON", "XORBI", "ABB"]


def test_route5_abb_proximity_picks_france_not_usa(resolver):
    """ABB has a US VORTAC at (38.6, -85.6) and a French VORDME at (50.1, 1.85).
    On an LFQA→LFAT route the resolver must pick the French candidate."""
    route = "LFQA ABB LFAT"
    r = resolver.resolve(route)
    abb = next(w for w in r.waypoint_coords if w.name == "ABB")
    assert abb.latitude == pytest.approx(50.14, abs=0.01)
    assert abb.longitude == pytest.approx(1.85, abs=0.01)


def test_route6_y8_airway_demoted_then_rejected(resolver):
    """Route 6 contains ``Y8`` — a real airway identifier that also exists as
    a waypoint (Canadian NDB) in nav.db. The resolver's demotion pass
    promotes AIRWAY→WAYPOINT when the token resolves to a point, and the
    detour gate then rejects the far-off Canadian NDB. Both halves of that
    behavior must hold.

    SAPRE and ELDAX are not in the fixture → stay unresolved.
    """
    route = (
        "LSGS SAPRE1D SAPRE/N0189F180 IFR L615 DJL A6 SOMDA T11 VATRI B3 "
        "BILGO H20 XORBI H40 ABB N20 ELDAX M8 WAFFU Y8 GWC EGTF"
    )

    tokens = parse_field15(route)
    # Y8 tokenises as AIRWAY per pure ICAO grammar (the demotion is DB-side).
    y8 = next(t for t in tokens if t.value == "Y8")
    assert y8.kind is TokenKind.AIRWAY
    # SAPRE1D is a STAR, not a real point.
    sapre1d = next(t for t in tokens if t.value == "SAPRE1D")
    assert sapre1d.kind is TokenKind.UNKNOWN
    # IFR must classify as FLIGHT_RULE and drop out of waypoints.
    ifr = next(t for t in tokens if t.value == "IFR")
    assert ifr.kind is TokenKind.FLIGHT_RULE

    r = resolver.resolve(route)
    assert r.departure == "LSGS"
    assert r.destination == "EGTF"
    assert r.waypoints == [
        "DJL", "SOMDA", "VATRI", "BILGO", "XORBI", "ABB", "WAFFU", "GWC",
    ]
    # Y8 must show up in rejected_waypoints with detour metadata.
    rejected_names = [rj["name"] for rj in r.rejected_waypoints]
    assert "Y8" in rejected_names, (
        "Y8 must be demoted to WAYPOINT and then rejected by the detour gate"
    )
    y8_rej = next(rj for rj in r.rejected_waypoints if rj["name"] == "Y8")
    assert y8_rej["reason"] == "detour_exceeds_threshold"


def test_route7_star_dropped_unresolved_point_tracked(resolver):
    """KATHY1V is a STAR (UNKNOWN). RUDMO is not in the fixture (unresolved).
    Q41 is an airway. Only real points survive."""
    route = "LFRD MINQI DCT ORTAC Q41 NEDUL DCT RUDMO KATHY1V EGTF"

    tokens = parse_field15(route)
    by_val = {t.value: t.kind for t in tokens}
    assert by_val["KATHY1V"] is TokenKind.UNKNOWN
    assert by_val["Q41"] is TokenKind.AIRWAY
    assert by_val["DCT"] is TokenKind.DIRECT

    r = resolver.resolve(route)
    assert r.departure == "LFRD"
    assert r.destination == "EGTF"
    assert r.waypoints == ["MINQI", "ORTAC", "NEDUL"]
