"""Signed along/cross-track positions from find_airports_near_route.

The westbound route EDLD → EHMZ → EGTF with Dortmund (EDLW) ~29 NM east of the
departure is the case that motivated the fields: ``enroute_distance_nm`` reads
it as ~29 NM *along* the route, which it is not.
"""

import pytest

from euro_aip.models.airport import Airport
from euro_aip.models.euro_aip_model import EuroAipModel
from euro_aip.models.navpoint import NavPoint


def _model(*airports):
    model = EuroAipModel()
    for ident, lat, lon in airports:
        model.add_airport(Airport(ident=ident, name=ident, latitude_deg=lat, longitude_deg=lon))
    return model


ROUTE = [("EDLD", 51.616, 6.865), ("EHMZ", 51.512, 3.731), ("EGTF", 51.348, -0.559)]


def _found(model, ident, distance_nm=60):
    hits = model.find_airports_near_route([r[0] for r in ROUTE], distance_nm)
    return next(h for h in hits if h["airport"].ident == ident)


def test_track_position_signs():
    a = NavPoint(50.0, 0.0)
    b = NavPoint(50.0, 2.0)  # eastbound
    along, cross = NavPoint(49.9, 1.0).track_position(a, b)  # south = right
    assert 30 < along < 45
    assert cross == pytest.approx(6.0, abs=0.3)
    along, cross = NavPoint(50.1, 1.0).track_position(a, b)  # north = left
    assert cross == pytest.approx(-6.0, abs=0.3)
    along, _ = NavPoint(50.0, -0.5).track_position(a, b)  # behind the start
    assert along == pytest.approx(-19.3, abs=0.3)
    along, _ = NavPoint(50.0, 2.5).track_position(a, b)  # past the end
    assert along == pytest.approx(96.4, abs=0.5)


def test_airport_behind_departure_is_negative():
    model = _model(*ROUTE, ("EDLW", 51.518, 7.612))
    hit = _found(model, "EDLW")
    # The legacy field is unchanged: still positive, as consumers expect.
    assert hit["enroute_distance_nm"] > 25
    assert hit["along_track_nm"] == pytest.approx(-29, abs=2)
    assert hit["route_end"] == "departure"
    assert -10 < hit["cross_track_nm"] < 0  # a little south: left of a westbound track


def test_airport_past_destination():
    model = _model(*ROUTE, ("EGUB", 51.616, -1.096))  # Benson, NW of Fairoaks
    hit = _found(model, "EGUB")
    route_total = sum(
        NavPoint(*ROUTE[i][1:]).haversine_distance(NavPoint(*ROUTE[i + 1][1:]))[1]
        for i in range(len(ROUTE) - 1)
    )
    assert hit["along_track_nm"] > route_total + 10
    assert hit["route_end"] == "destination"


def test_off_abeam_mid_route_is_projected_not_pushed_forward():
    # 20 NM north of the EDLD→EHMZ leg, abeam ~half way.
    model = _model(*ROUTE, ("ZZAB", 51.90, 5.30))
    hit = _found(model, "ZZAB")
    along, cross = hit["along_track_nm"], hit["cross_track_nm"]
    assert hit["route_end"] is None
    assert cross > 15  # flying west, north is on the right
    assert hit["segment_distance_nm"] == pytest.approx(abs(cross), abs=0.5)
    # The straight-line distance from EDLD overstates the along-track position.
    assert hit["enroute_distance_nm"] > along + 1
    leg = NavPoint(*ROUTE[0][1:]).haversine_distance(NavPoint(*ROUTE[1][1:]))[1]
    assert 0.35 * leg < along < 0.65 * leg


def test_beyond_inner_corner_clamps_to_waypoint():
    # South of EHMZ, beyond the end of leg 1 and before the start of leg 2.
    model = _model(*ROUTE, ("ZZCO", 51.30, 3.95))
    hit = _found(model, "ZZCO")
    leg1 = NavPoint(*ROUTE[0][1:]).haversine_distance(NavPoint(*ROUTE[1][1:]))[1]
    assert hit["route_end"] is None
    assert hit["along_track_nm"] == pytest.approx(leg1, abs=8)


def test_route_waypoints_sit_on_the_track():
    model = _model(*ROUTE)
    hits = {h["airport"].ident: h for h in model.find_airports_near_route([r[0] for r in ROUTE], 5)}
    assert hits["EDLD"]["along_track_nm"] == pytest.approx(0, abs=0.01)
    assert hits["EDLD"]["route_end"] is None
    assert hits["EGTF"]["route_end"] is None
    assert abs(hits["EHMZ"]["cross_track_nm"]) < 0.01


def test_single_point_route():
    model = _model(("EDLD", 51.616, 6.865), ("EDLW", 51.518, 7.612))
    hit = next(h for h in model.find_airports_near_route(["EDLD"], 50) if h["airport"].ident == "EDLW")
    assert hit["along_track_nm"] == 0.0
    assert hit["cross_track_nm"] is None
    assert hit["route_end"] is None
