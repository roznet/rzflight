"""Tests for spatial geometry helpers."""

import math

from euro_aip.utils.geometry import (
    NM_PER_DEGREE_LAT,
    haversine_nm,
    min_distance_point_to_multipolygon_nm,
    point_to_segment_nm,
)


class TestPointToSegmentNm:
    def test_endpoint_distance(self):
        # Point coincident with segment start → 0.
        assert point_to_segment_nm(0.0, 50.0, 0.0, 50.0, 1.0, 50.0) == 0.0

    def test_perpendicular_to_midpoint(self):
        # Segment along the 50N parallel from lon 0 to lon 2; point one degree
        # of latitude north of the midpoint → ~1 degree of latitude away.
        d = point_to_segment_nm(1.0, 51.0, 0.0, 50.0, 2.0, 50.0)
        assert math.isclose(d, NM_PER_DEGREE_LAT, rel_tol=0.02)

    def test_beyond_segment_end_clamps(self):
        # Point past the B end projects onto B, not the infinite line.
        d = point_to_segment_nm(3.0, 50.0, 0.0, 50.0, 2.0, 50.0)
        expected = haversine_nm(50.0, 3.0, 50.0, 2.0)
        assert math.isclose(d, expected, rel_tol=0.02)

    def test_degenerate_segment(self):
        d = point_to_segment_nm(0.0, 51.0, 0.0, 50.0, 0.0, 50.0)
        assert math.isclose(d, NM_PER_DEGREE_LAT, rel_tol=0.02)


class TestMinDistancePointToMultipolygon:
    def _square(self):
        # 1°-square ring around lon[0,1], lat[50,51], as a multipolygon.
        ring = [(0.0, 50.0), (1.0, 50.0), (1.0, 51.0), (0.0, 51.0), (0.0, 50.0)]
        return [[ring]]

    def test_distance_to_nearest_edge(self):
        polys = self._square()
        # Point one degree of latitude below the bottom edge.
        d = min_distance_point_to_multipolygon_nm(0.5, 49.0, polys)
        assert math.isclose(d, NM_PER_DEGREE_LAT, rel_tol=0.02)

    def test_point_on_boundary_is_zero(self):
        polys = self._square()
        d = min_distance_point_to_multipolygon_nm(0.5, 50.0, polys)
        assert d < 0.5

    def test_interior_point_returns_boundary_distance(self):
        # Interior point: still returns distance to the nearest *edge* (positive).
        polys = self._square()
        d = min_distance_point_to_multipolygon_nm(0.5, 50.5, polys)
        assert d > 0.0

    def test_empty_geometry_is_inf(self):
        assert min_distance_point_to_multipolygon_nm(0.0, 0.0, []) == math.inf
