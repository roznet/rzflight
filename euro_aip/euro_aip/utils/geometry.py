"""Spatial helpers for euro_aip — hand-rolled, no shapely/geopandas dependency.

Coordinates are decimal degrees in `(lon, lat)` order to match GeoJSON. Earth
radius matches `NavPoint.EARTH_RADIUS_NM` for consistency with the rest of the
library. Geometry primitives:

- ring:        list of (lon, lat) — outer or hole
- polygon:     list of rings (rings[0] is outer, rings[1:] are holes)
- multipolygon: list of polygons
- bbox:        (min_lon, min_lat, max_lon, max_lat)
"""

import math
from typing import List, Sequence, Tuple

EARTH_RADIUS_NM = 3440.065
NM_PER_DEGREE_LAT = math.pi * EARTH_RADIUS_NM / 180.0  # ~60.04 nm per degree


def nm_to_degrees_lat(nm: float) -> float:
    """Convert nautical miles to degrees of latitude (constant)."""
    return nm / NM_PER_DEGREE_LAT


def nm_to_degrees_lon(nm: float, at_latitude_deg: float) -> float:
    """Convert nautical miles to degrees of longitude at a given latitude."""
    cos_lat = math.cos(math.radians(at_latitude_deg))
    if cos_lat < 1e-9:
        return 360.0  # near a pole — anything wraps
    return nm / (NM_PER_DEGREE_LAT * cos_lat)


def haversine_nm(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance between two (lat, lon) points in nautical miles."""
    rlat1 = math.radians(lat1)
    rlat2 = math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(rlat1) * math.cos(rlat2) * math.sin(dlon / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return EARTH_RADIUS_NM * c


def point_in_ring(lon: float, lat: float, ring: Sequence[Tuple[float, float]]) -> bool:
    """Ray-cast point-in-polygon for a single ring of (lon, lat) vertices.

    Crossing-number test; works whether or not the ring is explicitly closed.
    """
    n = len(ring)
    if n < 3:
        return False
    inside = False
    j = n - 1
    for i in range(n):
        xi, yi = ring[i]
        xj, yj = ring[j]
        if (yi > lat) != (yj > lat):
            x_intersect = (xj - xi) * (lat - yi) / ((yj - yi) or 1e-15) + xi
            if lon < x_intersect:
                inside = not inside
        j = i
    return inside


def point_in_polygon(lon: float, lat: float,
                     rings: Sequence[Sequence[Tuple[float, float]]]) -> bool:
    """Point-in-polygon honouring the outer ring (rings[0]) and holes (rings[1:])."""
    if not rings:
        return False
    if not point_in_ring(lon, lat, rings[0]):
        return False
    for hole in rings[1:]:
        if point_in_ring(lon, lat, hole):
            return False
    return True


def point_in_multipolygon(lon: float, lat: float,
                          polygons: Sequence[Sequence[Sequence[Tuple[float, float]]]]) -> bool:
    """OR over multiple polygons."""
    for poly in polygons:
        if point_in_polygon(lon, lat, poly):
            return True
    return False


def bbox_of_ring(ring: Sequence[Tuple[float, float]]) -> Tuple[float, float, float, float]:
    """Bounding box (min_lon, min_lat, max_lon, max_lat) of a ring."""
    lons = [p[0] for p in ring]
    lats = [p[1] for p in ring]
    return (min(lons), min(lats), max(lons), max(lats))


def bbox_union(boxes: Sequence[Tuple[float, float, float, float]]) -> Tuple[float, float, float, float]:
    """Union of bounding boxes."""
    return (
        min(b[0] for b in boxes),
        min(b[1] for b in boxes),
        max(b[2] for b in boxes),
        max(b[3] for b in boxes),
    )


def bbox_intersects(a: Tuple[float, float, float, float],
                    b: Tuple[float, float, float, float]) -> bool:
    """True if two axis-aligned bboxes overlap (inclusive intervals)."""
    return not (a[2] < b[0] or b[2] < a[0] or a[3] < b[1] or b[3] < a[1])


def bbox_contains_point(box: Tuple[float, float, float, float],
                        lon: float, lat: float) -> bool:
    return box[0] <= lon <= box[2] and box[1] <= lat <= box[3]


def bbox_pad(box: Tuple[float, float, float, float], nm: float) -> Tuple[float, float, float, float]:
    """Pad a bbox by `nm` nautical miles. Uses the bbox center latitude for the
    longitude scale, which is accurate enough for typical FIR-sized boxes."""
    if nm <= 0:
        return box
    min_lon, min_lat, max_lon, max_lat = box
    pad_lat = nm_to_degrees_lat(nm)
    center_lat = (min_lat + max_lat) / 2.0
    pad_lon = nm_to_degrees_lon(nm, center_lat)
    return (min_lon - pad_lon, min_lat - pad_lat, max_lon + pad_lon, max_lat + pad_lat)


def point_to_segment_nm(plon: float, plat: float,
                        alon: float, alat: float,
                        blon: float, blat: float) -> float:
    """Shortest distance (nm) from a point to a segment A→B.

    Uses a local equirectangular projection centred on the point's latitude,
    which is accurate at corridor scales (tens of nm) and avoids the cost of a
    full geodesic cross-track calculation.
    """
    ky = NM_PER_DEGREE_LAT
    kx = NM_PER_DEGREE_LAT * math.cos(math.radians(plat))
    ax, ay = (alon - plon) * kx, (alat - plat) * ky
    bx, by = (blon - plon) * kx, (blat - plat) * ky
    dx, dy = bx - ax, by - ay
    seg_len2 = dx * dx + dy * dy
    if seg_len2 <= 1e-12:
        return math.hypot(ax, ay)
    t = -(ax * dx + ay * dy) / seg_len2
    t = max(0.0, min(1.0, t))
    cx, cy = ax + t * dx, ay + t * dy
    return math.hypot(cx, cy)


def min_distance_point_to_multipolygon_nm(
    lon: float, lat: float,
    polygons: Sequence[Sequence[Sequence[Tuple[float, float]]]],
) -> float:
    """Minimum distance (nm) from a point to the boundary of a multipolygon.

    Considers every ring (outer and holes) of every polygon. Returns ``inf`` if
    there is no usable geometry. Note this is the distance to the *boundary*: a
    point strictly inside a polygon still returns a positive value, so callers
    that care about containment should test :func:`point_in_multipolygon` first.
    """
    best = math.inf
    for poly in polygons:
        for ring in poly:
            n = len(ring)
            if n == 0:
                continue
            if n == 1:
                best = min(best, haversine_nm(lat, lon, ring[0][1], ring[0][0]))
                continue
            for i in range(n):
                alon, alat = ring[i]
                blon, blat = ring[(i + 1) % n]
                d = point_to_segment_nm(lon, lat, alon, alat, blon, blat)
                if d < best:
                    best = d
    return best


def sample_polyline(points: Sequence[Tuple[float, float]], step_nm: float) -> List[Tuple[float, float]]:
    """Sample a polyline at fixed nm intervals along its great-circle distance.

    Returns each input vertex plus linearly-interpolated samples between them
    spaced by approximately `step_nm`. Linear interpolation in lon/lat is fine
    for FIR-resolution sampling at typical latitudes — switching to true
    great-circle interpolation isn't worth the complexity here.
    """
    if step_nm <= 0:
        return list(points)
    if len(points) < 2:
        return list(points)
    samples: List[Tuple[float, float]] = []
    for (lon1, lat1), (lon2, lat2) in zip(points, points[1:]):
        samples.append((lon1, lat1))
        seg_len = haversine_nm(lat1, lon1, lat2, lon2)
        if seg_len <= step_nm:
            continue
        n_extra = int(seg_len / step_nm)
        for k in range(1, n_extra + 1):
            t = k * step_nm / seg_len
            samples.append((lon1 + t * (lon2 - lon1), lat1 + t * (lat2 - lat1)))
    samples.append(points[-1])
    return samples
