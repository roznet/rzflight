"""
Route resolver for resolving route strings to Route objects with coordinates.

Resolves mixed airport/waypoint route strings like "EGTF POGOL REM VESAN LSGS"
by looking up each token in the airport and waypoint databases.

When multiple waypoint candidates share the same name (e.g. MID in UK vs Mexico),
the resolver picks the candidate closest to the route context (departure/destination
midpoint, or the previously resolved point for progressive resolution).
"""

import logging
from dataclasses import replace
from typing import Optional, List, TYPE_CHECKING

from euro_aip.briefing.models.route import Route, RoutePoint
from euro_aip.models.navpoint import NavPoint
from euro_aip.models.field15 import (
    TokenKind,
    parse_field15,
    waypoints_of,
)
from euro_aip.utils.dms_parser import is_icao_coordinate, parse_icao_coordinate

if TYPE_CHECKING:
    from euro_aip.models.euro_aip_model import EuroAipModel

logger = logging.getLogger(__name__)


class RouteResolver:
    """Resolves route strings to Route objects with coordinates.

    Resolution order for each token:
    1. Airport lookup (by ICAO code)
    2. Waypoint lookup (by name) — picks closest candidate to route context
    3. Unresolved (logged as warning, skipped)

    Usage:
        model = storage.load_model()
        resolver = RouteResolver(model)
        route = resolver.resolve("EGTF POGOL REM VESAN LSGS")
    """

    # Default detour-filter thresholds (nautical miles). The leg here is
    # `prev_resolved → destination`, so the filter tightens automatically as
    # resolution progresses.
    DEFAULT_DETOUR_FLOOR_NM = 30.0
    DEFAULT_DETOUR_COEF = 0.5
    DEFAULT_DETOUR_CAP_NM = 300.0

    def __init__(
        self,
        model: 'EuroAipModel',
        detour_floor_nm: float = DEFAULT_DETOUR_FLOOR_NM,
        detour_coef: float = DEFAULT_DETOUR_COEF,
        detour_cap_nm: float = DEFAULT_DETOUR_CAP_NM,
    ):
        """
        Args:
            model: EuroAipModel with airport and waypoint data.
            detour_floor_nm: Minimum detour tolerated on short legs (nm).
            detour_coef: Fraction of leg length allowed as detour.
            detour_cap_nm: Maximum detour tolerated on long legs (nm).

        Threshold per candidate = min(cap, max(floor, coef × leg_nm)).
        """
        self.model = model
        self.detour_floor_nm = detour_floor_nm
        self.detour_coef = detour_coef
        self.detour_cap_nm = detour_cap_nm

    def _detour_threshold_nm(self, leg_nm: float) -> float:
        return min(
            self.detour_cap_nm,
            max(self.detour_floor_nm, self.detour_coef * leg_nm),
        )

    def resolve_point(self, name: str) -> Optional[RoutePoint]:
        """Resolve a single name to a RoutePoint (first candidate, no proximity).

        Tries inline coord, then airport, then waypoint. For proximity-aware
        resolution, use resolve_point_near() instead.

        Args:
            name: ICAO code, waypoint name, or inline ICAO coordinate
                (``DDMM[NS]DDDMM[EW]`` / ``DDMMSS[NS]DDDMMSS[EW]``).

        Returns:
            RoutePoint with coordinates, or None if not found
        """
        name_upper = name.upper().strip()

        # Inline coordinate — geometry, no DB lookup
        coord_point = self._coord_point(name_upper)
        if coord_point is not None:
            return coord_point

        # Try airport first
        airport = self.model.airports.where(ident=name_upper).first()
        if airport and airport.latitude_deg is not None and airport.longitude_deg is not None:
            return RoutePoint(
                name=name_upper,
                latitude=airport.latitude_deg,
                longitude=airport.longitude_deg,
                point_type="airport",
            )

        # Try waypoint — return first candidate
        waypoint = self.model.get_waypoint(name_upper)
        if waypoint:
            return RoutePoint(
                name=name_upper,
                latitude=waypoint.latitude_deg,
                longitude=waypoint.longitude_deg,
                point_type=waypoint.point_type or "waypoint",
            )

        return None

    @staticmethod
    def _coord_point(name_upper: str) -> Optional[RoutePoint]:
        """If ``name_upper`` is an inline ICAO coordinate, return its RoutePoint.

        The token itself becomes the point name so it round-trips back into
        the route string verbatim. ``point_type="coordinate"`` lets callers
        distinguish geometric points from named ones (useful for icons,
        labels, and skipping nav-DB cross-references).
        """
        if not is_icao_coordinate(name_upper):
            return None
        lat, lon = parse_icao_coordinate(name_upper)
        return RoutePoint(
            name=name_upper,
            latitude=lat,
            longitude=lon,
            point_type="coordinate",
        )

    def resolve_point_near(
        self,
        name: str,
        reference: NavPoint,
        forward: Optional[NavPoint] = None,
    ) -> Optional[RoutePoint]:
        """Resolve a name to a RoutePoint, disambiguating among candidates.

        When ``forward`` is provided, candidates are scored by their detour
        cost relative to the leg ``reference → forward`` — i.e. how much
        they'd add if inserted there. This is more meaningful than raw
        distance to ``reference`` when the route is long and ``reference``
        is only one endpoint of the current leg.

        When ``forward`` is None, falls back to closest-to-reference
        (legacy behavior).

        Args:
            name: ICAO code or waypoint name.
            reference: Anchor NavPoint (typically last resolved point).
            forward: Optional second anchor (typically destination) used
                for detour-based selection.

        Returns:
            RoutePoint with coordinates, or None if not found.
        """
        name_upper = name.upper().strip()

        # Inline coordinate — geometry, no candidates to disambiguate
        coord_point = self._coord_point(name_upper)
        if coord_point is not None:
            return coord_point

        # Try airport first (airports are unique by ICAO)
        airport = self.model.airports.where(ident=name_upper).first()
        if airport and airport.latitude_deg is not None and airport.longitude_deg is not None:
            return RoutePoint(
                name=name_upper,
                latitude=airport.latitude_deg,
                longitude=airport.longitude_deg,
                point_type="airport",
            )

        # Try waypoint — pick best candidate
        candidates = self.model.get_waypoint_candidates(name_upper)
        if not candidates:
            return None

        if len(candidates) == 1:
            wp = candidates[0]
        elif forward is not None:
            # Minimise detour on the reference→forward leg
            wp = min(
                candidates,
                key=lambda c: NavPoint.detour_nm(reference, c.navpoint, forward),
            )
            logger.debug(
                "Waypoint %s: %d candidates, chose %s (detour %.0f nm)",
                name_upper,
                len(candidates),
                wp.source_id,
                NavPoint.detour_nm(reference, wp.navpoint, forward),
            )
        else:
            # No forward anchor — fall back to closest-to-reference
            wp = min(
                candidates,
                key=lambda c: reference.haversine_distance(c.navpoint)[1],
            )
            _, chosen_dist = reference.haversine_distance(wp.navpoint)
            logger.debug(
                "Waypoint %s: %d candidates, chose %s (%.0f nm from reference)",
                name_upper, len(candidates), wp.source_id, chosen_dist,
            )

        return RoutePoint(
            name=name_upper,
            latitude=wp.latitude_deg,
            longitude=wp.longitude_deg,
            point_type=wp.point_type or "waypoint",
        )

    def resolve(self, route_string: str) -> Route:
        """Resolve a space-separated route string into a Route with coordinates.

        The first token is treated as the departure airport, the last as the
        destination airport, and everything in between as waypoints. Tokens
        that match airports are still valid as intermediate points.

        For intermediate waypoints with multiple candidates, picks the one
        closest to the route context (midpoint of departure/destination, then
        progressively the last resolved point).

        Args:
            route_string: Space-separated route string, e.g. "EGTF POGOL REM LSGS"

        Returns:
            Route with resolved coordinates

        Raises:
            ValueError: If fewer than 2 tokens are provided
        """
        parsed = parse_field15(route_string)

        # Belt-and-braces: if a token classified as AIRWAY or UNKNOWN
        # actually resolves to a known point, treat it as a waypoint. The
        # parser stays strict to ICAO grammar; this demotion needs DB
        # access so it lives here. Covers two real cases: airway-like
        # identifiers that collide with a point name, and longer-than-ICAO
        # point names occasionally present in real nav databases.
        for i, t in enumerate(parsed):
            if t.kind in (TokenKind.AIRWAY, TokenKind.UNKNOWN) and self.resolve_point(t.value):
                parsed[i] = replace(t, kind=TokenKind.WAYPOINT)

        tokens = waypoints_of(parsed)

        if len(tokens) < 2:
            raise ValueError(f"Route string must have at least departure and destination, got: '{route_string}'")

        departure = tokens[0]
        destination = tokens[-1]
        middle_tokens = tokens[1:-1]

        # Resolve departure
        dep_point = self.resolve_point(departure)
        departure_coords = None
        if dep_point:
            departure_coords = (dep_point.latitude, dep_point.longitude)
        else:
            logger.warning("Could not resolve departure: %s", departure)

        # Resolve destination
        dest_point = self.resolve_point(destination)
        destination_coords = None
        if dest_point:
            destination_coords = (dest_point.latitude, dest_point.longitude)
        else:
            logger.warning("Could not resolve destination: %s", destination)

        # Anchors for progressive resolution:
        #   reference = last good resolved point (starts at dep, else dep/dest
        #               midpoint fallback, else dest)
        #   forward   = destination (stable; used for detour scoring + gate)
        reference = self._make_reference(dep_point, dest_point)
        forward = (
            NavPoint(
                latitude=dest_point.latitude,
                longitude=dest_point.longitude,
                name=dest_point.name,
            )
            if dest_point
            else None
        )
        # Prefer dep_point as starting reference when available, so the leg
        # used for the detour gate is a real leg (dep→dest) rather than the
        # midpoint→dest half-leg.
        if dep_point is not None:
            reference = NavPoint(
                latitude=dep_point.latitude,
                longitude=dep_point.longitude,
                name=dep_point.name,
            )

        waypoint_names: List[str] = []
        waypoint_coords: List[RoutePoint] = []
        unresolved: List[str] = []
        rejected: List[dict] = []
        for token in middle_tokens:
            if reference is not None:
                point = self.resolve_point_near(token, reference, forward=forward)
            else:
                point = self.resolve_point(token)

            if not point:
                unresolved.append(token)
                logger.warning("Could not resolve waypoint: %s", token)
                continue

            # Detour gate — only applies when we have both anchors AND a
            # real leg between them. For closed-loop routes (dep == dest)
            # leg_nm collapses to 0 and the detour metric reduces to
            # 2·d(ref, candidate), which would reject every middle point.
            if reference is not None and forward is not None:
                _, leg_nm = reference.haversine_distance(forward)
                if leg_nm >= 1.0:
                    candidate_np = NavPoint(
                        latitude=point.latitude,
                        longitude=point.longitude,
                        name=point.name,
                    )
                    detour = NavPoint.detour_nm(reference, candidate_np, forward)
                    threshold = self._detour_threshold_nm(leg_nm)
                    if detour > threshold:
                        rejected.append({
                            "name": token,
                            "reason": "detour_exceeds_threshold",
                            "detour_nm": round(detour, 1),
                            "leg_nm": round(leg_nm, 1),
                            "threshold_nm": round(threshold, 1),
                        })
                        logger.warning(
                            "Route '%s': rejecting %s — detour %.0f nm exceeds "
                            "threshold %.0f nm on %.0f nm leg (%s→%s)",
                            route_string, token, detour, threshold, leg_nm,
                            reference.name, forward.name,
                        )
                        # Do not advance reference — keep anchoring on last good point
                        continue

            waypoint_names.append(token)
            # Override point_type for intermediate points
            if point.point_type == "airport":
                point = RoutePoint(
                    name=point.name,
                    latitude=point.latitude,
                    longitude=point.longitude,
                    point_type="waypoint",
                )
            waypoint_coords.append(point)
            # Advance reference to last good resolved point
            reference = NavPoint(
                latitude=point.latitude,
                longitude=point.longitude,
                name=point.name,
            )

        if unresolved:
            logger.warning(
                "Route '%s': %d unresolved point(s): %s",
                route_string, len(unresolved), ", ".join(unresolved),
            )

        return Route(
            departure=departure,
            destination=destination,
            waypoints=waypoint_names,
            departure_coords=departure_coords,
            destination_coords=destination_coords,
            waypoint_coords=waypoint_coords,
            rejected_waypoints=rejected,
        )

    @staticmethod
    def _make_reference(dep: Optional[RoutePoint], dest: Optional[RoutePoint]) -> Optional[NavPoint]:
        """Build a reference NavPoint from departure and/or destination."""
        if dep and dest:
            return NavPoint(
                latitude=(dep.latitude + dest.latitude) / 2,
                longitude=(dep.longitude + dest.longitude) / 2,
                name="route_midpoint",
            )
        if dep:
            return NavPoint(latitude=dep.latitude, longitude=dep.longitude, name=dep.name)
        if dest:
            return NavPoint(latitude=dest.latitude, longitude=dest.longitude, name=dest.name)
        return None
