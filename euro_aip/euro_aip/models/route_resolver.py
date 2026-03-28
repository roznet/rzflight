"""
Route resolver for resolving route strings to Route objects with coordinates.

Resolves mixed airport/waypoint route strings like "EGTF POGOL REM VESAN LSGS"
by looking up each token in the airport and waypoint databases.

When multiple waypoint candidates share the same name (e.g. MID in UK vs Mexico),
the resolver picks the candidate closest to the route context (departure/destination
midpoint, or the previously resolved point for progressive resolution).
"""

import logging
from typing import Optional, List, TYPE_CHECKING

from euro_aip.briefing.models.route import Route, RoutePoint
from euro_aip.models.navpoint import NavPoint

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

    def __init__(self, model: 'EuroAipModel'):
        self.model = model

    def resolve_point(self, name: str) -> Optional[RoutePoint]:
        """Resolve a single name to a RoutePoint (first candidate, no proximity).

        Tries airport first, then waypoint. For proximity-aware resolution,
        use resolve_point_near() instead.

        Args:
            name: ICAO code or waypoint name

        Returns:
            RoutePoint with coordinates, or None if not found
        """
        name_upper = name.upper().strip()

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

    def resolve_point_near(self, name: str, reference: NavPoint) -> Optional[RoutePoint]:
        """Resolve a name to a RoutePoint, picking the candidate closest to reference.

        Args:
            name: ICAO code or waypoint name
            reference: NavPoint to use for proximity disambiguation

        Returns:
            RoutePoint with coordinates, or None if not found
        """
        name_upper = name.upper().strip()

        # Try airport first (airports are unique by ICAO)
        airport = self.model.airports.where(ident=name_upper).first()
        if airport and airport.latitude_deg is not None and airport.longitude_deg is not None:
            return RoutePoint(
                name=name_upper,
                latitude=airport.latitude_deg,
                longitude=airport.longitude_deg,
                point_type="airport",
            )

        # Try waypoint — pick closest candidate to reference
        candidates = self.model.get_waypoint_candidates(name_upper)
        if not candidates:
            return None

        if len(candidates) == 1:
            wp = candidates[0]
        else:
            wp = min(
                candidates,
                key=lambda c: reference.haversine_distance(c.navpoint)[1],
            )
            if len(candidates) > 1:
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
        tokens = route_string.upper().split()
        # Filter out common route notation tokens
        tokens = [t for t in tokens if t not in ("DCT", "->", "TO")]

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

        # Build reference point for proximity disambiguation
        # Start with midpoint of dep/dest, then progressively use last resolved point
        reference = self._make_reference(dep_point, dest_point)

        # Resolve middle waypoints with proximity context
        waypoint_names = []
        waypoint_coords = []
        unresolved = []
        for token in middle_tokens:
            if reference is not None:
                point = self.resolve_point_near(token, reference)
            else:
                point = self.resolve_point(token)

            if point:
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
                # Update reference to last resolved point for progressive resolution
                reference = NavPoint(
                    latitude=point.latitude,
                    longitude=point.longitude,
                    name=point.name,
                )
            else:
                unresolved.append(token)
                logger.warning("Could not resolve waypoint: %s", token)

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
