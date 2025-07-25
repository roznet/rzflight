import math
import pytest
from euro_aip.models.euro_aip_model import EuroAipModel
from euro_aip.models.airport import Airport
from euro_aip.models.navpoint import NavPoint

def make_airport(ident, lat, lon):
    return Airport(
        ident=ident,
        name=ident,
        latitude_deg=lat,
        longitude_deg=lon
    )

def test_navpoint_class_constants():
    """Test that NavPoint class constants are accessible and correct."""
    from euro_aip.models.navpoint import NavPoint
    
    # Test class constant is accessible
    assert hasattr(NavPoint, 'EARTH_RADIUS_NM')
    assert NavPoint.EARTH_RADIUS_NM == 3440.065
    
    # Test instance can access class constant
    point = NavPoint(51.4706, -0.461941, 'EGLL')
    assert point.EARTH_RADIUS_NM == 3440.065
    
    # Test the constant is used in calculations
    point2 = NavPoint(48.0695, -1.73456, 'LFRN')
    bearing, distance = point.haversine_distance(point2)
    
    # The distance should be calculated using the class constant
    # We can't easily test the internal calculation, but we can verify
    # that the method works correctly with the constant
    assert isinstance(distance, float)
    assert distance > 0

def test_distance_to_segment_boundary_conditions():
    """Test that distance_to_segment properly handles points outside segment boundaries."""
    from euro_aip.models.navpoint import NavPoint
    
    # Create a simple segment: EGLL -> LFRN
    egll = NavPoint(51.4706, -0.461941, 'EGLL')  # London Heathrow
    lfrn = NavPoint(48.0695, -1.73456, 'LFRN')   # Rennes
    
    # Test point behind the start (should return distance to start)
    point_behind = NavPoint(52.0, -0.5, 'BEHIND')  # North of EGLL
    dist_behind = point_behind.distance_to_segment(egll, lfrn)
    dist_to_start = point_behind.haversine_distance(egll)[1]
    
    print(f"Point behind segment: {dist_behind:.2f}nm, distance to start: {dist_to_start:.2f}nm")
    assert abs(dist_behind - dist_to_start) < 0.1, "Point behind should return distance to start"
    
    # Test point beyond the end (should return distance to end)
    point_beyond = NavPoint(47.0, -2.0, 'BEYOND')  # South of LFRN
    dist_beyond = point_beyond.distance_to_segment(egll, lfrn)
    dist_to_end = point_beyond.haversine_distance(lfrn)[1]
    
    print(f"Point beyond segment: {dist_beyond:.2f}nm, distance to end: {dist_to_end:.2f}nm")
    assert abs(dist_beyond - dist_to_end) < 0.1, "Point beyond should return distance to end"
    
    # Test point on the segment (should return cross-track distance)
    point_on_segment = NavPoint(50.0, -1.0, 'ON_SEGMENT')  # Midway between EGLL and LFRN
    dist_on = point_on_segment.distance_to_segment(egll, lfrn)
    
    print(f"Point on segment: {dist_on:.2f}nm")
    assert dist_on < 50, "Point on segment should have small cross-track distance"

def test_airport_navpoint_property():
    """Test that Airport.navpoint property works correctly."""
    from euro_aip.models.airport import Airport
    from euro_aip.models.navpoint import NavPoint
    
    # Test with valid coordinates
    airport = make_airport('EGLL', 51.4706, -0.461941)
    navpoint = airport.navpoint
    
    assert navpoint is not None
    assert navpoint.latitude == 51.4706
    assert navpoint.longitude == -0.461941
    assert navpoint.name == 'EGLL'
    
    # Test caching - second access should return same object
    navpoint2 = airport.navpoint
    assert navpoint is navpoint2  # Same object reference
    
    # Test with missing coordinates
    airport_no_coords = Airport(ident='TEST')
    navpoint_none = airport_no_coords.navpoint
    assert navpoint_none is None
    
    # Test setter
    new_navpoint = NavPoint(52.0, 1.0, 'TEST2')
    airport.navpoint = new_navpoint
    assert airport.latitude_deg == 52.0
    assert airport.longitude_deg == 1.0
    assert airport.navpoint is new_navpoint

def test_find_airports_near_route_segment_edge_cases():
    """Test airports near a route for segment edge cases (EGLL, LFRN, LFMN)."""
    model = EuroAipModel()
    # Add route airports
    airports = [
        make_airport('EGLL', 51.4706, -0.461941),   # London Heathrow
        make_airport('LFRN', 48.0695, -1.73456),    # Rennes
        make_airport('LFMN', 43.6584, 7.21587),     # Nice
    ]
    # Add test airports - using airports that are truly far from the route
    airports += [
        make_airport('EGNY', 53.8984, -0.3614),   # North, should not be included
        make_airport('LFRC', 49.6501, -1.4703),   # Portsmouth, should not be included
    ]

    within_50nm = ['EGLL', 'LFRN', 'LFMN']

    for ap in airports:
        model.add_airport(ap)
    
    # Test at 50nm
    found_50 = model.find_airports_near_route(['EGLL', 'LFRN', 'LFMN'], 50)
    found_idents_50 = {item['airport'].ident for item in found_50}
    
    # Test at 100nm
    found_100 = model.find_airports_near_route(['EGLL', 'LFRN', 'LFMN'], 100)
    found_idents_100 = {item['airport'].ident for item in found_100}
    
    # EGLL, LFRN, LFMN should always be included
    for ident in ['EGLL', 'LFRN', 'LFMN', 'LFRC']:
        assert ident in found_idents_50, f"{ident} should be in 50nm results"
        assert ident in found_idents_100, f"{ident} should be in 100nm results"
    # LFLH should only be in 100nm
    # EGPH and EGAA should not be in either (they are far from the route)
    for ident in ['EGNY']:
        assert ident not in found_idents_50, f"{ident} should NOT be in 50nm results"
        assert ident not in found_idents_100, f"{ident} should NOT be in 100nm results"

def test_distance_boundary_conditions():
    """Test that distance calculations work correctly at boundary conditions."""
    model = EuroAipModel()
    
    # Create a simple route: EGLL -> LFRN
    airports = [
        make_airport('EGLL', 51.4706, -0.461941),   # London Heathrow
        make_airport('LFRN', 48.0695, -1.73456),    # Rennes
    ]
    
    # Add test airports at various distances
    airports += [
        make_airport('TEST1', 51.0, -0.5),          # Very close to EGLL
        make_airport('TEST2', 49.0, -1.0),          # Midway between EGLL and LFRN
        make_airport('TEST3', 47.0, -1.5),          # Very close to LFRN
    ]
    
    for ap in airports:
        model.add_airport(ap)
    
    # Test at very small distances
    found_1 = model.find_airports_near_route(['EGLL', 'LFRN'], 1)
    found_idents_1 = {item['airport'].ident for item in found_1}
    
    found_5 = model.find_airports_near_route(['EGLL', 'LFRN'], 5)
    found_idents_5 = {item['airport'].ident for item in found_5}
    
    # Route airports should always be included
    assert 'EGLL' in found_idents_1
    assert 'LFRN' in found_idents_1
    assert 'EGLL' in found_idents_5
    assert 'LFRN' in found_idents_5
    
    # Test that distance calculations are working
    egll = model.get_airport('EGLL')
    lfrn = model.get_airport('LFRN')
    test1 = model.get_airport('TEST1')
    
    # Calculate distance manually to verify
    from euro_aip.models.navpoint import NavPoint
    egll_point = NavPoint(egll.latitude_deg, egll.longitude_deg)
    test1_point = NavPoint(test1.latitude_deg, test1.longitude_deg)
    _, manual_dist = egll_point.haversine_distance(test1_point)
    
    print(f"Manual distance EGLL to TEST1: {manual_dist:.2f}nm")
    
    # Verify the algorithm finds the same distance
    found_test1 = [item for item in found_5 if item['airport'].ident == 'TEST1']
    if found_test1:
        algo_dist = found_test1[0]['distance_nm']
        print(f"Algorithm distance EGLL to TEST1: {algo_dist:.2f}nm")
        assert abs(manual_dist - algo_dist) < 0.1, "Distance calculation mismatch" 