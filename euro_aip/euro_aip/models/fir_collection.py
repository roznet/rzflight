"""FIRCollection — fluent queries over FIR objects."""

from typing import Optional, TYPE_CHECKING
from .queryable_collection import QueryableCollection

if TYPE_CHECKING:
    from .fir import FIR


class FIRCollection(QueryableCollection['FIR']):
    """Specialized queryable collection for FIR objects.

    Examples:
        collection.by_icao("LFFF")
        collection.by_region("EMEA")
        collection.land()
        collection.containing_point(lon=2.5, lat=49.0)
    """

    def by_icao(self, icao: str) -> 'FIRCollection':
        upper = icao.upper()
        return FIRCollection([f for f in self._items if f.icao.upper() == upper])

    def by_region(self, region: str) -> 'FIRCollection':
        upper = region.upper()
        return FIRCollection([f for f in self._items if (f.region or '').upper() == upper])

    def by_source(self, source: str) -> 'FIRCollection':
        return FIRCollection([f for f in self._items if f.source == source])

    def land(self) -> 'FIRCollection':
        return FIRCollection([f for f in self._items if not f.is_oceanic])

    def oceanic(self) -> 'FIRCollection':
        return FIRCollection([f for f in self._items if f.is_oceanic])

    def containing_point(self, lon: float, lat: float) -> 'FIRCollection':
        """FIRs whose geometry contains (lon, lat)."""
        return FIRCollection([f for f in self._items if f.contains(lon, lat)])

    def __getitem__(self, key):
        if isinstance(key, str):
            for f in self._items:
                if f.icao == key.upper():
                    return f
            raise KeyError(f"FIR '{key}' not found")
        return super().__getitem__(key)

    def __contains__(self, item) -> bool:
        if isinstance(item, str):
            return any(f.icao == item.upper() for f in self._items)
        return super().__contains__(item)

    def get(self, icao: str) -> Optional['FIR']:
        upper = icao.upper()
        for f in self._items:
            if f.icao == upper:
                return f
        return None
