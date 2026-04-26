"""FIR (Flight Information Region) model.

A FIR is a large block of airspace identified by an ICAO code (e.g. ``LFFF``
for Paris, ``EGTT`` for London). Boundaries come from VATSpy's
``Boundaries.geojson`` and are stored as MultiPolygons in (lon, lat) decimal
degrees. A precomputed bounding box enables cheap spatial prefiltering.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple

from euro_aip.utils.geometry import (
    bbox_of_ring,
    bbox_union,
    point_in_multipolygon,
    bbox_contains_point,
)


# Type aliases for clarity
Coord = Tuple[float, float]            # (lon, lat)
Ring = List[Coord]                      # ring of coordinates
Polygon = List[Ring]                    # outer ring + holes
MultiPolygon = List[Polygon]            # zero or more polygons


@dataclass
class FIR:
    """Flight Information Region with polygon boundary."""

    icao: str                                       # "LFFF", "EGTT", etc.
    polygons: MultiPolygon = field(default_factory=list)
    name: Optional[str] = None
    is_oceanic: bool = False
    region: Optional[str] = None                    # e.g. "EMEA", "APAC"
    label_lon: Optional[float] = None               # display label centroid
    label_lat: Optional[float] = None
    source: str = "vatspy"
    bbox: Optional[Tuple[float, float, float, float]] = None  # (min_lon, min_lat, max_lon, max_lat)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def __post_init__(self):
        if self.bbox is None and self.polygons:
            self.bbox = self._compute_bbox()

    def _compute_bbox(self) -> Tuple[float, float, float, float]:
        outer_bboxes = [bbox_of_ring(poly[0]) for poly in self.polygons if poly]
        return bbox_union(outer_bboxes) if outer_bboxes else (0.0, 0.0, 0.0, 0.0)

    def contains(self, lon: float, lat: float) -> bool:
        """True if (lon, lat) is inside this FIR's geometry."""
        if self.bbox and not bbox_contains_point(self.bbox, lon, lat):
            return False
        return point_in_multipolygon(lon, lat, self.polygons)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "icao": self.icao,
            "polygons": self.polygons,
            "name": self.name,
            "is_oceanic": self.is_oceanic,
            "region": self.region,
            "label_lon": self.label_lon,
            "label_lat": self.label_lat,
            "source": self.source,
            "bbox": list(self.bbox) if self.bbox else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FIR":
        created_at = data.get("created_at")
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)
        updated_at = data.get("updated_at")
        if isinstance(updated_at, str):
            updated_at = datetime.fromisoformat(updated_at)
        bbox = data.get("bbox")
        if bbox is not None:
            bbox = tuple(bbox)
        return cls(
            icao=data["icao"],
            polygons=data.get("polygons") or [],
            name=data.get("name"),
            is_oceanic=bool(data.get("is_oceanic", False)),
            region=data.get("region"),
            label_lon=data.get("label_lon"),
            label_lat=data.get("label_lat"),
            source=data.get("source", "vatspy"),
            bbox=bbox,
            created_at=created_at or datetime.now(),
            updated_at=updated_at or datetime.now(),
        )

    def __repr__(self) -> str:
        n_poly = len(self.polygons)
        n_pts = sum(len(p[0]) if p else 0 for p in self.polygons)
        return f"FIR({self.icao}, {n_poly} polygon(s), {n_pts} pts)"
