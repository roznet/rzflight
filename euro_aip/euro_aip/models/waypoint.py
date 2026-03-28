"""
Waypoint model for named navigation points (5-letter codes and NAVAIDs).

Waypoints are distinct from airports — they represent named fixes, VORs, DMEs,
NDBs, and other navigation points used in route strings.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, Any

from euro_aip.models.navpoint import NavPoint


@dataclass
class Waypoint:
    """A named navigation waypoint with coordinates.

    Waypoints come from sources like Eurocontrol's FRA (Free Route Airspace)
    points list. They have a `.navpoint` property for distance calculations,
    just like Airport does.
    """

    name: str  # "BILGO", "REM", "ABADI"
    latitude_deg: float
    longitude_deg: float
    point_type: Optional[str] = None  # "5LNC", "VOR", "DME", "VORDME", "NDB", "VORTAC", "NDBDME", "LOCATOR"
    fir_codes: Optional[str] = None  # Comma-separated FIR ICAOs e.g. "LFFF,LFBB"
    level_availability: Optional[str] = None  # e.g. "FL195 / FL660"
    source: str = "eurocontrol_fra"
    source_id: str = ""  # Unique per candidate, e.g. "fra:LFFF", "opennav:UK", "ourairports:GB"
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    _navpoint: Optional[NavPoint] = field(default=None, init=False, repr=False, compare=False)

    @property
    def navpoint(self) -> NavPoint:
        """Get NavPoint representation for distance calculations."""
        if self._navpoint is None:
            self._navpoint = NavPoint(
                latitude=self.latitude_deg,
                longitude=self.longitude_deg,
                name=self.name,
            )
        return self._navpoint

    @property
    def is_navaid(self) -> bool:
        """True if this waypoint is a NAVAID (VOR, DME, NDB, etc.) rather than a 5LNC."""
        return self.point_type is not None and self.point_type != "5LNC"

    @property
    def fir_list(self) -> list:
        """Get FIR codes as a list."""
        if not self.fir_codes:
            return []
        return [f.strip() for f in self.fir_codes.split(",") if f.strip()]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "name": self.name,
            "latitude_deg": self.latitude_deg,
            "longitude_deg": self.longitude_deg,
            "point_type": self.point_type,
            "fir_codes": self.fir_codes,
            "level_availability": self.level_availability,
            "source": self.source,
            "source_id": self.source_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Waypoint":
        """Create from dictionary."""
        created_at = data.get("created_at")
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)
        updated_at = data.get("updated_at")
        if isinstance(updated_at, str):
            updated_at = datetime.fromisoformat(updated_at)

        return cls(
            name=data["name"],
            latitude_deg=data["latitude_deg"],
            longitude_deg=data["longitude_deg"],
            point_type=data.get("point_type"),
            fir_codes=data.get("fir_codes"),
            level_availability=data.get("level_availability"),
            source=data.get("source", "eurocontrol_fra"),
            source_id=data.get("source_id", ""),
            created_at=created_at or datetime.now(),
            updated_at=updated_at or datetime.now(),
        )

    def __repr__(self):
        type_str = f" ({self.point_type})" if self.point_type else ""
        return f"Waypoint({self.name}{type_str}, {self.latitude_deg:.4f}, {self.longitude_deg:.4f})"
