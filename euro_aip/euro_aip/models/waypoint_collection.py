"""
Specialized queryable collection for Waypoint objects.

Provides domain-specific filtering methods for querying named navigation
waypoints (5-letter codes, VORs, DMEs, NDBs, etc.).
"""

from typing import Optional, List, TYPE_CHECKING
from .queryable_collection import QueryableCollection

if TYPE_CHECKING:
    from .waypoint import Waypoint
    from .navpoint import NavPoint


class WaypointCollection(QueryableCollection['Waypoint']):
    """
    Specialized collection for querying waypoints with domain-specific filters.

    Examples:
        collection.by_type("VOR")
        collection.by_fir("LFFF")
        collection.navaids()
        collection.five_letter_codes()
        collection.nearest(navpoint, count=10)
    """

    def by_type(self, point_type: str) -> 'WaypointCollection':
        """Filter waypoints by point type (e.g., "VOR", "DME", "NDB", "5LNC")."""
        upper = point_type.upper()
        return WaypointCollection([
            w for w in self._items
            if w.point_type and w.point_type.upper() == upper
        ])

    def by_fir(self, fir_code: str) -> 'WaypointCollection':
        """Filter waypoints by FIR code (checks comma-separated fir_codes field)."""
        upper = fir_code.upper()
        return WaypointCollection([
            w for w in self._items
            if w.fir_codes and upper in [f.strip().upper() for f in w.fir_codes.split(",")]
        ])

    def navaids(self) -> 'WaypointCollection':
        """Filter to only NAVAID waypoints (VOR, DME, NDB, etc.)."""
        return WaypointCollection([w for w in self._items if w.is_navaid])

    def five_letter_codes(self) -> 'WaypointCollection':
        """Filter to only 5-letter name code waypoints."""
        return WaypointCollection([
            w for w in self._items
            if w.point_type is None or w.point_type == "5LNC"
        ])

    def by_source(self, source: str) -> 'WaypointCollection':
        """Filter waypoints by data source."""
        return WaypointCollection([
            w for w in self._items
            if w.source == source
        ])

    def nearest(self, point: 'NavPoint', count: int = 10) -> 'WaypointCollection':
        """Return the nearest waypoints to a given NavPoint, sorted by distance."""
        with_dist = []
        for w in self._items:
            _, dist = point.haversine_distance(w.navpoint)
            with_dist.append((dist, w))
        with_dist.sort(key=lambda x: x[0])
        return WaypointCollection([w for _, w in with_dist[:count]])

    def __getitem__(self, key):
        """Support dict-style lookup by waypoint name."""
        if isinstance(key, str):
            for w in self._items:
                if w.name == key:
                    return w
            raise KeyError(f"Waypoint '{key}' not found")
        return super().__getitem__(key)

    def __contains__(self, item) -> bool:
        """Support 'name' in collection checks."""
        if isinstance(item, str):
            return any(w.name == item for w in self._items)
        return super().__contains__(item)

    def get(self, name: str) -> Optional['Waypoint']:
        """Get a waypoint by name, or None if not found."""
        for w in self._items:
            if w.name == name:
                return w
        return None
