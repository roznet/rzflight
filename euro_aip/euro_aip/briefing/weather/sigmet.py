"""SIGMET report model and parser.

A SIGMET (Significant Meteorological Information) warns of weather hazards over
a Flight Information Region (FIR) — turbulence, icing, thunderstorms, mountain
waves, volcanic ash, etc. — bounded by a polygon and a vertical band.

This module models the *international* SIGMETs served by aviationweather.gov's
``/api/data/isigmet`` endpoint. Coordinates follow the euro_aip convention of
``(lon, lat)`` decimal degrees so the polygon plugs straight into
``euro_aip.utils.geometry`` and the FIR machinery.

NB: AWC reworked this JSON schema in Sept 2025 (the legacy ``isigmetId`` was
dropped). The parser reads fields defensively — every accessor tolerates a
missing key, and the level/time helpers accept the several encodings AWC has
shipped over time — so a future tweak degrades gracefully rather than crashing.
"""

import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from euro_aip.utils.geometry import (
    bbox_of_ring,
    point_in_multipolygon,
)

Coord = Tuple[float, float]  # (lon, lat)


def _parse_level(value: Any) -> Optional[int]:
    """Parse an AWC base/top level into feet MSL.

    Handles plain integers/floats (feet), numeric strings, ``"SFC"``/``"GND"``
    (→ 0) and flight-level strings such as ``"FL340"`` (→ 34000 ft).
    """
    if value is None:
        return None
    if isinstance(value, bool):  # guard: bool is an int subclass
        return None
    if isinstance(value, (int, float)):
        return int(value)
    text = str(value).strip().upper()
    if not text:
        return None
    if text in ("SFC", "GND", "SURFACE"):
        return 0
    if text.startswith("FL"):
        digits = text[2:].strip()
        if digits.isdigit():
            return int(digits) * 100
        return None
    # Plain numeric string, possibly with a unit suffix like "FT".
    cleaned = text.replace("FT", "").replace(",", "").strip()
    try:
        return int(float(cleaned))
    except ValueError:
        return None


def _parse_time(value: Any) -> Optional[datetime]:
    """Parse an AWC validity timestamp into an aware UTC datetime.

    Accepts epoch seconds (int/float), ISO-8601 strings (with ``T`` or a space
    separator, optional trailing ``Z``). Naive results are assumed UTC.
    """
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, tz=timezone.utc)
    text = str(value).strip()
    if not text:
        return None
    if text.isdigit():
        return datetime.fromtimestamp(int(text), tz=timezone.utc)
    iso = text.replace("Z", "+00:00")
    if " " in iso and "T" not in iso:
        iso = iso.replace(" ", "T", 1)
    try:
        dt = datetime.fromisoformat(iso)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _parse_coords(value: Any) -> List[Coord]:
    """Parse AWC ``coords`` into a ring of ``(lon, lat)`` tuples.

    AWC returns a list of ``{"lat": .., "lon": ..}`` dicts. Two-element
    ``[lon, lat]`` pairs are also accepted. Malformed entries are skipped.
    """
    if not value or not isinstance(value, (list, tuple)):
        return []
    ring: List[Coord] = []
    for pt in value:
        lat = lon = None
        if isinstance(pt, dict):
            lat = pt.get("lat", pt.get("latitude"))
            lon = pt.get("lon", pt.get("lng", pt.get("longitude")))
        elif isinstance(pt, (list, tuple)) and len(pt) >= 2:
            lon, lat = pt[0], pt[1]
        if lat is None or lon is None:
            continue
        try:
            ring.append((float(lon), float(lat)))
        except (TypeError, ValueError):
            continue
    return ring


#: One ICAO SIGMET point, hemisphere first: ``N4230 E00215`` or ``N42 E002``
#: (degrees, optional minutes). Annex 3 also allows the space to be omitted.
_TEXT_POINT = r"([NS])(\d{2})(\d{2})?\s*([EW])(\d{3})(\d{2})?"
#: ``WI <point> - <point> - ...``: an area given as a polygon.
_TEXT_POLYGON_RE = re.compile(
    r"\bWI\s+(" + _TEXT_POINT + r"(?:\s*-\s*" + _TEXT_POINT + r")+)"
)
_TEXT_POINT_RE = re.compile(_TEXT_POINT)


def _parse_text_polygon(raw_text: str) -> List[Coord]:
    """Parse the ``WI <point> - <point> - ...`` polygon of a SIGMET bulletin.

    The fallback for entries where AWC sends no ``coords`` (LFBB, 2026-10-23).
    Returns a closed ring of ``(lon, lat)`` tuples, or ``[]`` when the text
    has no polygon, has fewer than three distinct points, or has more than one
    ``WI`` polygon (e.g. an observed area plus a ``FCST AT`` position): the
    model holds one ring, and picking one of two areas could drop the part
    a route crosses, so those stay coordless and fall back to the FIR match.
    ``OF LINE`` areas, ``ENTIRE FIR`` and radius forms are not parsed either.
    """
    if not raw_text:
        return []
    text = " ".join(raw_text.split())
    matches = _TEXT_POLYGON_RE.findall(text)
    if len(matches) != 1:
        return []
    ring: List[Coord] = []
    for ns, lat_d, lat_m, ew, lon_d, lon_m in _TEXT_POINT_RE.findall(matches[0][0]):
        lat = int(lat_d) + int(lat_m or 0) / 60.0
        lon = int(lon_d) + int(lon_m or 0) / 60.0
        if lat > 90 or lon > 180:
            return []
        ring.append((-lon if ew == "W" else lon, -lat if ns == "S" else lat))
    if len(set(ring)) < 3:
        return []
    if ring[0] != ring[-1]:
        ring.append(ring[0])
    return ring


@dataclass
class SigmetReport:
    """A parsed international SIGMET.

    Attributes:
        raw_text: Original raw SIGMET bulletin text.
        fir_id: ICAO id of the issuing FIR (e.g. ``"LFFF"``).
        fir_name: Human-readable FIR name, if provided.
        icao_id: ICAO id of the issuing office, if distinct from the FIR.
        hazard: Hazard type (``TURB``, ``ICE``, ``TS``, ``MTW``, ``VA``, ...).
        qualifier: Intensity/coverage qualifier (``SEV``, ``EMBD``, ``ISOL``, ...).
        base_ft: Lower bound of the affected layer, feet MSL (None if unknown).
        top_ft: Upper bound of the affected layer, feet MSL (None if unknown).
        valid_from: Start of validity (aware UTC).
        valid_to: End of validity (aware UTC).
        direction: Movement direction, e.g. ``"NE"`` (None if stationary/unknown).
        speed_kt: Movement speed in knots (None if unknown).
        coords: Polygon outline as ``(lon, lat)`` vertices.
        source: Data source identifier.
        coords_source: Where ``coords`` came from: ``"awc"`` (AWC's
            ``coords``), ``"text"`` (parsed from ``raw_text`` because AWC sent
            none) or None (no geometry).
    """

    raw_text: str = ""
    fir_id: str = ""
    fir_name: Optional[str] = None
    icao_id: Optional[str] = None
    hazard: Optional[str] = None
    qualifier: Optional[str] = None
    base_ft: Optional[int] = None
    top_ft: Optional[int] = None
    valid_from: Optional[datetime] = None
    valid_to: Optional[datetime] = None
    direction: Optional[str] = None
    speed_kt: Optional[int] = None
    coords: List[Coord] = field(default_factory=list)
    source: str = ""
    coords_source: Optional[str] = None

    @classmethod
    def from_awc(cls, data: Dict[str, Any], source: str = "avwx") -> "SigmetReport":
        """Build a SigmetReport from one aviationweather.gov isigmet JSON object."""
        fir_id = (data.get("firId") or "").strip().upper()
        hazard = data.get("hazard")
        qualifier = data.get("qualifier")
        direction = data.get("dir")
        if isinstance(direction, str):
            # AWC encodes a stationary/unknown system as "-"; normalise to None.
            direction = direction.strip().upper() or None
            if direction == "-":
                direction = None
        raw_text = data.get("rawSigmet") or data.get("rawAirSigmet") or ""
        # AWC's coords win when present; some entries come with none although
        # the bulletin carries a polygon, so read it from the text then.
        coords = _parse_coords(data.get("coords"))
        coords_source: Optional[str] = "awc" if coords else None
        if not coords:
            coords = _parse_text_polygon(raw_text)
            coords_source = "text" if coords else None
        return cls(
            raw_text=raw_text,
            fir_id=fir_id,
            fir_name=data.get("firName"),
            icao_id=data.get("icaoId"),
            hazard=hazard.strip().upper() if isinstance(hazard, str) else hazard,
            qualifier=qualifier.strip().upper() if isinstance(qualifier, str) else qualifier,
            base_ft=_parse_level(data.get("base")),
            top_ft=_parse_level(data.get("top")),
            valid_from=_parse_time(data.get("validTimeFrom")),
            valid_to=_parse_time(data.get("validTimeTo")),
            direction=direction,
            speed_kt=_parse_level(data.get("spd")),
            coords=coords,
            source=source,
            coords_source=coords_source,
        )

    @property
    def polygons(self) -> List[List[List[Coord]]]:
        """Geometry as a multipolygon (one polygon, one outer ring).

        Returns an empty list when the SIGMET has no usable outline. The shape
        matches ``euro_aip.utils.geometry`` helpers and ``FIR.polygons``.
        """
        if len(self.coords) < 3:
            return []
        return [[list(self.coords)]]

    @property
    def bbox(self) -> Optional[Tuple[float, float, float, float]]:
        """Bounding box ``(min_lon, min_lat, max_lon, max_lat)`` of the outline."""
        if not self.coords:
            return None
        return bbox_of_ring(self.coords)

    def contains_point(self, lon: float, lat: float) -> bool:
        """True if ``(lon, lat)`` lies inside the SIGMET polygon."""
        return point_in_multipolygon(lon, lat, self.polygons)

    def overlaps_altitude(self, low_ft: Optional[int], high_ft: Optional[int]) -> bool:
        """Whether the SIGMET's vertical band overlaps ``[low_ft, high_ft]``.

        Unknown bounds are treated permissively: a SIGMET with no base/top, or a
        query band left open, always overlaps. This errs toward surfacing a
        hazard rather than silently dropping it.
        """
        s_low = self.base_ft if self.base_ft is not None else float("-inf")
        s_high = self.top_ft if self.top_ft is not None else float("inf")
        q_low = low_ft if low_ft is not None else float("-inf")
        q_high = high_ft if high_ft is not None else float("inf")
        return s_low <= q_high and q_low <= s_high

    def is_valid_at(self, when: datetime) -> bool:
        """Whether ``when`` falls within the SIGMET's validity window.

        Open-ended (missing) bounds are treated as not constraining that side.
        """
        if self.valid_from is not None and when < self.valid_from:
            return False
        if self.valid_to is not None and when > self.valid_to:
            return False
        return True

    def overlaps_time(
        self,
        from_dt: Optional[datetime],
        to_dt: Optional[datetime],
    ) -> bool:
        """Whether the SIGMET's validity window overlaps ``[from_dt, to_dt]``.

        Mirrors :meth:`overlaps_altitude`: open-ended bounds (None) on either the
        SIGMET or the query are treated permissively, so an unconstrained query
        always overlaps. Naive datetimes are assumed UTC.
        """
        def _utc(dt: Optional[datetime]) -> Optional[datetime]:
            if dt is None:
                return None
            return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)

        s_from, s_to = _utc(self.valid_from), _utc(self.valid_to)
        q_from, q_to = _utc(from_dt), _utc(to_dt)
        if q_to is not None and s_from is not None and s_from > q_to:
            return False
        if q_from is not None and s_to is not None and q_from > s_to:
            return False
        return True

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to a JSON-friendly dictionary."""
        return {
            "raw_text": self.raw_text,
            "fir_id": self.fir_id,
            "fir_name": self.fir_name,
            "icao_id": self.icao_id,
            "hazard": self.hazard,
            "qualifier": self.qualifier,
            "base_ft": self.base_ft,
            "top_ft": self.top_ft,
            "valid_from": self.valid_from.isoformat() if self.valid_from else None,
            "valid_to": self.valid_to.isoformat() if self.valid_to else None,
            "direction": self.direction,
            "speed_kt": self.speed_kt,
            "coords": [list(c) for c in self.coords],
            "source": self.source,
            "coords_source": self.coords_source,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SigmetReport":
        """Reconstruct a SigmetReport from :meth:`to_dict` output."""
        coords = [tuple(c) for c in (data.get("coords") or []) if len(c) >= 2]
        return cls(
            raw_text=data.get("raw_text", ""),
            fir_id=data.get("fir_id", ""),
            fir_name=data.get("fir_name"),
            icao_id=data.get("icao_id"),
            hazard=data.get("hazard"),
            qualifier=data.get("qualifier"),
            base_ft=data.get("base_ft"),
            top_ft=data.get("top_ft"),
            valid_from=_parse_time(data.get("valid_from")),
            valid_to=_parse_time(data.get("valid_to")),
            direction=data.get("direction"),
            speed_kt=data.get("speed_kt"),
            coords=coords,
            source=data.get("source", ""),
            # Dicts written before coords_source existed only had AWC coords.
            coords_source=data.get("coords_source", "awc" if coords else None),
        )

    def __repr__(self) -> str:
        bits = " ".join(b for b in (self.qualifier, self.hazard) if b)
        return f"SigmetReport({self.fir_id} {bits})".replace("  ", " ")


#: How far inside a SIGMET's validity an isigmet query must fall before the
#: SIGMET's absence from it counts (:func:`isigmet_covers`). AWC lists the
#: SIGMETs valid at the query's ``date``; whether it rounds or caches that time
#: has not been checked, so a query just inside the validity is not trusted.
ISIGMET_COVER_MARGIN = timedelta(minutes=30)


def _as_utc(t: datetime) -> datetime:
    return t if t.tzinfo is not None else t.replace(tzinfo=timezone.utc)


def isigmet_covers(
    queried_at: Optional[List[datetime]],
    valid_from: Optional[datetime],
    valid_to: Optional[datetime],
    margin: timedelta = ISIGMET_COVER_MARGIN,
) -> bool:
    """Whether isigmet queries made at ``queried_at`` would have listed a
    SIGMET valid ``[valid_from, valid_to]``: one of them falls inside that
    validity by at least ``margin`` on each side.

    So a SIGMET missing from such a fetch is no longer issued (cancelled or
    never there), rather than out of the queries' reach. False when the query
    times or the validity are unknown, and for a validity shorter than twice
    ``margin``. Naive datetimes are taken as UTC.
    """
    if not queried_at or valid_from is None or valid_to is None:
        return False
    lo = _as_utc(valid_from) + margin
    hi = _as_utc(valid_to) - margin
    return any(lo <= _as_utc(q) <= hi for q in queried_at)


@dataclass
class IsigmetFetch:
    """An isigmet fetch with its outcome (``AvWxSource.fetch_isigmet_result``).

    Attributes:
        reports: The SIGMETs fetched (what ``fetch_isigmet`` returns).
        base_ok: The base (now, or ``date``) query succeeded. When False,
            ``reports`` is empty and says nothing about what is issued.
        queried_at: The ``date`` of every query that succeeded, base first,
            then the lookahead steps up to the first failed one.
    """

    reports: List[SigmetReport] = field(default_factory=list)
    base_ok: bool = True
    queried_at: List[datetime] = field(default_factory=list)

    def covers(self, valid_from: Optional[datetime], valid_to: Optional[datetime]) -> bool:
        """See :func:`isigmet_covers`."""
        return isigmet_covers(self.queried_at, valid_from, valid_to)
