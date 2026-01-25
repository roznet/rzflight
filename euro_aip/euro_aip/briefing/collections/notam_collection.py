"""Queryable collection for NOTAM filtering."""

from datetime import datetime
from typing import List, Dict, Optional, Tuple, Callable, Any, TYPE_CHECKING
import re

from euro_aip.models.queryable_collection import QueryableCollection
from euro_aip.models.navpoint import NavPoint
from euro_aip.briefing.models.notam import Notam, NotamCategory

if TYPE_CHECKING:
    from euro_aip.briefing.models.route import Route
    from euro_aip.models.euro_aip_model import EuroAipModel


class NotamCollection(QueryableCollection[Notam]):
    """
    Queryable collection for NOTAM filtering.

    Extends QueryableCollection with aviation-specific filters for:
    - Location (airport, FIR)
    - Time (active at, active during, permanent/temporary)
    - Category (runway, navigation, airspace, etc.)
    - Spatial (within radius, along route, near airports)
    - Altitude (below, above, in range)
    - Q-code (ICAO standard codes)
    - Content (text search, regex matching)

    Supports fluent chaining, set operations, and iteration.

    Example:
        # Chain multiple filters
        critical_notams = (
            collection
            .for_airport("LFPG")
            .active_now()
            .runway_related()
            .all()
        )

        # Set operations
        departure_or_arrival = (
            collection.for_airport("LFPG") |
            collection.for_airport("EGLL")
        )
    """

    def __init__(
        self,
        items: List[Notam],
        model: Optional['EuroAipModel'] = None
    ):
        """
        Initialize NotamCollection.

        Args:
            items: List of Notam objects
            model: Optional EuroAipModel for coordinate lookups
        """
        super().__init__(items)
        self._model = model

    def _new_collection(self, items: List[Notam]) -> 'NotamCollection':
        """Create new collection preserving model reference."""
        return NotamCollection(items, model=self._model)

    # Override filter to preserve model
    def filter(self, predicate: Callable[[Notam], bool]) -> 'NotamCollection':
        """Filter items using a predicate function."""
        return self._new_collection([item for item in self._items if predicate(item)])

    # --- Location filters ---

    def for_airport(self, icao: str) -> 'NotamCollection':
        """
        Filter NOTAMs affecting a specific airport.

        Args:
            icao: Airport ICAO code

        Returns:
            Collection with NOTAMs for the airport
        """
        icao_upper = icao.upper()
        return self._new_collection([
            n for n in self._items
            if n.location.upper() == icao_upper
            or icao_upper in [loc.upper() for loc in n.affected_locations]
        ])

    def for_airports(self, icaos: List[str]) -> 'NotamCollection':
        """
        Filter NOTAMs affecting any of the specified airports.

        Args:
            icaos: List of ICAO codes

        Returns:
            Collection with NOTAMs for any of the airports
        """
        icaos_upper = {i.upper() for i in icaos}
        return self._new_collection([
            n for n in self._items
            if n.location.upper() in icaos_upper
            or any(loc.upper() in icaos_upper for loc in n.affected_locations)
        ])

    def for_fir(self, fir: str) -> 'NotamCollection':
        """
        Filter NOTAMs for a specific FIR.

        Args:
            fir: FIR code

        Returns:
            Collection with NOTAMs for the FIR
        """
        fir_upper = fir.upper()
        return self._new_collection([
            n for n in self._items
            if n.fir and n.fir.upper() == fir_upper
        ])

    def for_route(self, route: 'Route') -> 'NotamCollection':
        """
        Filter NOTAMs affecting any airport in the route.

        Args:
            route: Route object

        Returns:
            Collection with NOTAMs for route airports
        """
        return self.for_airports(route.get_all_airports())

    # --- Category filters ---

    def by_category(self, category: NotamCategory) -> 'NotamCollection':
        """
        Filter by NOTAM category.

        Args:
            category: NotamCategory enum value

        Returns:
            Collection with NOTAMs of the category
        """
        return self._new_collection([
            n for n in self._items
            if n.category == category
        ])

    def runway_related(self) -> 'NotamCollection':
        """
        Filter NOTAMs related to runways.

        Includes runway closures, conditions, and lighting.
        """
        return self._new_collection([
            n for n in self._items
            if n.category in (NotamCategory.AGA_MOVEMENT, NotamCategory.AGA_LIGHTING)
            or (n.q_code and n.q_code.upper().startswith(('QMR', 'QLR')))
            or (n.primary_category and 'runway' in n.primary_category.lower())
        ])

    def navigation_related(self) -> 'NotamCollection':
        """Filter NOTAMs related to navigation aids."""
        return self._new_collection([
            n for n in self._items
            if n.category in (NotamCategory.NAVIGATION, NotamCategory.CNS_ILS, NotamCategory.CNS_GNSS)
            or (n.q_code and n.q_code.upper().startswith(('QN', 'QI', 'QG')))
        ])

    def airspace_related(self) -> 'NotamCollection':
        """Filter NOTAMs related to airspace restrictions."""
        return self._new_collection([
            n for n in self._items
            if n.category in (NotamCategory.ATM_AIRSPACE, NotamCategory.AIRSPACE_RESTRICTIONS)
            or (n.q_code and n.q_code.upper().startswith(('QA', 'QR', 'QW')))
        ])

    def procedure_related(self) -> 'NotamCollection':
        """Filter NOTAMs related to instrument procedures."""
        return self._new_collection([
            n for n in self._items
            if n.category == NotamCategory.ATM_PROCEDURES
            or (n.q_code and n.q_code.upper().startswith('QP'))
        ])

    def obstacle_related(self) -> 'NotamCollection':
        """Filter NOTAMs related to obstacles."""
        return self._new_collection([
            n for n in self._items
            if n.category == NotamCategory.OTHER_INFO
            or (n.q_code and n.q_code.upper().startswith('QO'))
        ])

    # --- Time filters ---

    def active_at(self, dt: datetime) -> 'NotamCollection':
        """
        Filter NOTAMs active at a specific time.

        Args:
            dt: Datetime to check

        Returns:
            Collection with NOTAMs active at that time
        """
        return self._new_collection([
            n for n in self._items
            if self._is_active_at(n, dt)
        ])

    def active_now(self) -> 'NotamCollection':
        """Filter NOTAMs currently active (assumes UTC)."""
        return self.active_at(datetime.utcnow())

    def active_during(self, start: datetime, end: datetime) -> 'NotamCollection':
        """
        Filter NOTAMs active during any part of a time window.

        Use this for flight planning - pass departure and arrival times
        to get all NOTAMs that could affect the flight.

        Args:
            start: Window start time (e.g., departure time)
            end: Window end time (e.g., arrival time + buffer)

        Returns:
            Collection with NOTAMs overlapping the window

        Example:
            dep_time = datetime.utcnow() + timedelta(hours=2)
            arr_time = dep_time + timedelta(hours=3)
            relevant = notams.active_during(dep_time, arr_time)
        """
        return self._new_collection([
            n for n in self._items
            if self._overlaps_window(n, start, end)
        ])

    def effective_after(self, dt: datetime) -> 'NotamCollection':
        """Filter NOTAMs that become effective after a given time."""
        return self._new_collection([
            n for n in self._items
            if n.effective_from and n.effective_from > dt
        ])

    def expiring_before(self, dt: datetime) -> 'NotamCollection':
        """Filter NOTAMs that expire before a given time."""
        return self._new_collection([
            n for n in self._items
            if n.effective_to and n.effective_to < dt and not n.is_permanent
        ])

    def permanent(self) -> 'NotamCollection':
        """Filter permanent NOTAMs."""
        return self._new_collection([
            n for n in self._items
            if n.is_permanent
        ])

    def temporary(self) -> 'NotamCollection':
        """Filter temporary NOTAMs."""
        return self._new_collection([
            n for n in self._items
            if not n.is_permanent
        ])

    @staticmethod
    def _is_active_at(notam: Notam, dt: datetime) -> bool:
        """Check if NOTAM is active at a specific time."""
        if notam.is_permanent:
            return notam.effective_from is None or notam.effective_from <= dt
        from_ok = notam.effective_from is None or notam.effective_from <= dt
        to_ok = notam.effective_to is None or notam.effective_to >= dt
        return from_ok and to_ok

    @staticmethod
    def _overlaps_window(notam: Notam, start: datetime, end: datetime) -> bool:
        """Check if NOTAM is active during any part of time window."""
        if notam.is_permanent:
            return notam.effective_from is None or notam.effective_from <= end

        n_start = notam.effective_from
        n_end = notam.effective_to

        if n_end and n_end < start:
            return False
        if n_start and n_start > end:
            return False
        return True

    # --- Spatial filters ---

    def within_radius(
        self,
        lat: float,
        lon: float,
        radius_nm: float
    ) -> 'NotamCollection':
        """
        Filter NOTAMs within a radius of a point.

        Args:
            lat: Latitude in degrees
            lon: Longitude in degrees
            radius_nm: Radius in nautical miles

        Returns:
            Collection with NOTAMs within the radius

        Example:
            nearby = notams.within_radius(48.8566, 2.3522, 50)
        """
        center = NavPoint(latitude=lat, longitude=lon)
        return self._new_collection([
            n for n in self._items
            if n.coordinates and self._distance_nm(center, n.coordinates) <= radius_nm
        ])

    def along_route(
        self,
        route: 'Route',
        corridor_nm: float = 25
    ) -> 'NotamCollection':
        """
        Filter NOTAMs along a route corridor.

        Checks if NOTAM coordinates fall within corridor_nm of any route segment.

        Args:
            route: Route object with waypoints
            corridor_nm: Corridor width in nautical miles (default 25nm each side)

        Returns:
            Collection with NOTAMs along the route

        Example:
            enroute = notams.along_route(briefing.route, corridor_nm=25)
        """
        route_points = route.get_route_navpoints()
        if len(route_points) < 2:
            return self._new_collection([])

        def is_along_route(notam: Notam) -> bool:
            if not notam.coordinates:
                return False
            point = NavPoint(
                latitude=notam.coordinates[0],
                longitude=notam.coordinates[1]
            )
            # Check distance to each route segment
            for i in range(len(route_points) - 1):
                dist = point.distance_to_segment(route_points[i], route_points[i + 1])
                if dist <= corridor_nm:
                    return True
            return False

        return self._new_collection([
            n for n in self._items
            if is_along_route(n)
        ])

    def near_airports(
        self,
        icaos: List[str],
        radius_nm: float,
        airport_coords: Optional[Dict[str, Tuple[float, float]]] = None
    ) -> 'NotamCollection':
        """
        Filter NOTAMs near specific airports by coordinates.

        Args:
            icaos: List of ICAO codes
            radius_nm: Radius around each airport
            airport_coords: Dict mapping ICAO to (lat, lon).
                           If None and model is set, looks up from model.

        Returns:
            Collection with NOTAMs near the airports

        Example:
            coords = {"LFPG": (49.0097, 2.5479), "EGLL": (51.4700, -0.4543)}
            nearby = notams.near_airports(["LFPG", "EGLL"], 30, coords)
        """
        # Resolve coordinates
        if airport_coords is None:
            airport_coords = self._resolve_airport_coords(icaos)

        relevant = []
        icaos_upper = {i.upper() for i in icaos}

        for n in self._items:
            # Include NOTAMs without coords if they match airport by location
            if not n.coordinates:
                if n.location.upper() in icaos_upper:
                    relevant.append(n)
                continue

            # Check distance to each airport
            for icao in icaos:
                if icao in airport_coords:
                    apt_lat, apt_lon = airport_coords[icao]
                    center = NavPoint(latitude=apt_lat, longitude=apt_lon)
                    if self._distance_nm(center, n.coordinates) <= radius_nm:
                        relevant.append(n)
                        break

        return self._new_collection(relevant)

    def _resolve_airport_coords(
        self,
        icaos: List[str]
    ) -> Dict[str, Tuple[float, float]]:
        """
        Resolve airport coordinates from model or return empty dict.

        Args:
            icaos: List of ICAO codes

        Returns:
            Dict mapping ICAO to (lat, lon)
        """
        if not self._model:
            return {}

        coords = {}
        for icao in icaos:
            airport = self._model.airports.where(ident=icao.upper()).first()
            if airport and airport.latitude_deg and airport.longitude_deg:
                coords[icao.upper()] = (airport.latitude_deg, airport.longitude_deg)
        return coords

    @staticmethod
    def _distance_nm(
        center: NavPoint,
        coords: Tuple[float, float]
    ) -> float:
        """Calculate distance in nautical miles."""
        point = NavPoint(latitude=coords[0], longitude=coords[1])
        _, distance = center.haversine_distance(point)
        return distance

    # --- Altitude filters ---

    def below_altitude(self, feet: int) -> 'NotamCollection':
        """Filter NOTAMs with upper limit below specified altitude."""
        return self._new_collection([
            n for n in self._items
            if n.upper_limit is not None and n.upper_limit <= feet
        ])

    def above_altitude(self, feet: int) -> 'NotamCollection':
        """Filter NOTAMs with lower limit above specified altitude."""
        return self._new_collection([
            n for n in self._items
            if n.lower_limit is not None and n.lower_limit >= feet
        ])

    def in_altitude_range(self, lower: int, upper: int) -> 'NotamCollection':
        """
        Filter NOTAMs affecting an altitude range.

        Args:
            lower: Lower altitude in feet
            upper: Upper altitude in feet

        Returns:
            Collection with NOTAMs that affect the altitude band
        """
        return self._new_collection([
            n for n in self._items
            if self._affects_altitude_range(n, lower, upper)
        ])

    @staticmethod
    def _affects_altitude_range(notam: Notam, lower: int, upper: int) -> bool:
        """Check if NOTAM affects an altitude range."""
        if notam.lower_limit is None and notam.upper_limit is None:
            return True  # Assume it affects all altitudes
        n_lower = notam.lower_limit or 0
        n_upper = notam.upper_limit or 99999
        return n_lower <= upper and n_upper >= lower

    # --- Q-code filters (ICAO standard) ---

    def by_q_code(self, q_code: str) -> 'NotamCollection':
        """
        Filter by exact Q-code match.

        Args:
            q_code: 5-letter Q-code (e.g., "QMRLC" for runway closed)
        """
        q_upper = q_code.upper()
        return self._new_collection([
            n for n in self._items
            if n.q_code and n.q_code.upper() == q_upper
        ])

    def by_q_code_prefix(self, prefix: str) -> 'NotamCollection':
        """
        Filter by Q-code prefix.

        Common prefixes:
        - QM: Movement area (runway, taxiway, apron)
        - QL: Lighting
        - QN: Navigation services
        - QO: Obstacles
        - QP: Instrument procedures
        - QA: Aerodrome

        Args:
            prefix: Q-code prefix (e.g., "QM" for movement area)
        """
        prefix_upper = prefix.upper()
        return self._new_collection([
            n for n in self._items
            if n.q_code and n.q_code.upper().startswith(prefix_upper)
        ])

    def by_traffic_type(self, traffic: str) -> 'NotamCollection':
        """
        Filter by traffic type from Q-line.

        Args:
            traffic: "I" (IFR), "V" (VFR), or "IV" (both)
        """
        traffic_upper = traffic.upper()
        return self._new_collection([
            n for n in self._items
            if n.traffic_type and traffic_upper in n.traffic_type.upper()
        ])

    def by_purpose(self, purpose: str) -> 'NotamCollection':
        """
        Filter by NOTAM purpose from Q-line.

        Args:
            purpose: N (immediate), B (briefing), O (operations), M (misc), K (checklist)
        """
        purpose_upper = purpose.upper()
        return self._new_collection([
            n for n in self._items
            if n.purpose and purpose_upper in n.purpose.upper()
        ])

    def by_scope(self, scope: str) -> 'NotamCollection':
        """
        Filter by scope from Q-line.

        Args:
            scope: A (aerodrome), E (enroute), W (nav warning), AE, AW, etc.
        """
        scope_upper = scope.upper()
        return self._new_collection([
            n for n in self._items
            if n.scope and scope_upper in n.scope.upper()
        ])

    # --- Custom category filters ---

    def by_custom_category(self, category: str) -> 'NotamCollection':
        """
        Filter by custom-assigned category.

        Custom categories are assigned by categorizers (rule-based or LLM).

        Args:
            category: Custom category name
        """
        category_lower = category.lower()
        return self._new_collection([
            n for n in self._items
            if category_lower in {c.lower() for c in n.custom_categories}
        ])

    def by_custom_tag(self, tag: str) -> 'NotamCollection':
        """
        Filter by custom tag.

        Tags are more granular than categories (e.g., "construction", "crane").
        """
        tag_lower = tag.lower()
        return self._new_collection([
            n for n in self._items
            if tag_lower in {t.lower() for t in n.custom_tags}
        ])

    def by_primary_category(self, category: str) -> 'NotamCollection':
        """
        Filter by primary category assigned by categorizer.

        Args:
            category: Primary category name
        """
        category_lower = category.lower()
        return self._new_collection([
            n for n in self._items
            if n.primary_category and n.primary_category.lower() == category_lower
        ])

    # --- Content filters ---

    def containing(self, text: str) -> 'NotamCollection':
        """
        Filter NOTAMs containing specific text (case-insensitive).

        Args:
            text: Text to search for
        """
        text_upper = text.upper()
        return self._new_collection([
            n for n in self._items
            if text_upper in n.raw_text.upper() or text_upper in n.message.upper()
        ])

    def matching(self, pattern: str) -> 'NotamCollection':
        """
        Filter NOTAMs matching a regex pattern.

        Args:
            pattern: Regular expression pattern
        """
        regex = re.compile(pattern, re.IGNORECASE)
        return self._new_collection([
            n for n in self._items
            if regex.search(n.raw_text) or regex.search(n.message)
        ])

    # --- Grouping ---

    def group_by_airport(self) -> Dict[str, 'NotamCollection']:
        """Group NOTAMs by primary airport."""
        groups = self.group_by(lambda n: n.location)
        return {k: self._new_collection(v) for k, v in groups.items()}

    def group_by_category(self) -> Dict[Optional[NotamCategory], 'NotamCollection']:
        """Group NOTAMs by category."""
        groups = self.group_by(lambda n: n.category)
        return {k: self._new_collection(v) for k, v in groups.items()}

    def group_by_custom_category(self) -> Dict[Optional[str], 'NotamCollection']:
        """Group NOTAMs by primary custom category."""
        groups = self.group_by(lambda n: n.primary_category)
        return {k: self._new_collection(v) for k, v in groups.items()}

    # --- Set operations (override to preserve model) ---

    def __or__(self, other: 'NotamCollection') -> 'NotamCollection':
        """Union operator (|) - combine two collections."""
        result = super().__or__(other)
        return self._new_collection(result._items)

    def __and__(self, other: 'NotamCollection') -> 'NotamCollection':
        """Intersection operator (&) - items in both collections."""
        result = super().__and__(other)
        return self._new_collection(result._items)

    def __sub__(self, other: 'NotamCollection') -> 'NotamCollection':
        """Difference operator (-) - items in first but not second."""
        result = super().__sub__(other)
        return self._new_collection(result._items)
