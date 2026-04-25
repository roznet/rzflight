"""
Eurocontrol SDO (Static Data Operations) Designated Points source.

Parses HTML exports from the Eurocontrol European AIS Database (EAD) SDO
reporting tool. The export covers ICAO designated points hemisphere by
hemisphere; each export is ~50-100k rows and is fetched manually behind a
login, so this source is local-file-only — no auto-download.

Filters applied:
- Type = ICAO (skips ADHP procedure points, OTHER runway-relative points,
  COORD grid intersections — none of these are useful for route resolution)
- Bounding box: Europe (lat 30-75, lon -30 to 50) or North America
  (lat 15-75, lon -180 to -50). Out-of-scope rows (Asia, S America, Pacific)
  are skipped, since the app targets EU/NA pilots.

Coordinate formats handled (the SDO export mixes all four within one file):
- DDMMSS[NS]            integer DMS               e.g. 535520N
- DDMMSS.s[NS]          DMS with decimal seconds  e.g. 420712.680N
- DDMM[.m][NS]          degrees+minutes only      e.g. 3243N, 0200.4N
- DD.dddd[NS]           decimal degrees           e.g. 56.64128497N
(Longitude variants use 3-digit degree prefix.)
"""

import logging
import re
from pathlib import Path
from typing import Iterable, List, Optional, Sequence, Tuple

from ..models.euro_aip_model import EuroAipModel
from ..models.waypoint import Waypoint
from .base import SourceInterface

logger = logging.getLogger(__name__)

# Bounding boxes for in-scope geography (lat_min, lat_max, lon_min, lon_max)
EUROPE_BBOX = (30.0, 75.0, -30.0, 50.0)
NORTH_AMERICA_BBOX = (15.0, 75.0, -180.0, -50.0)

# Row regex: matches one <tr>...</tr> with the 9 SDO columns.
# Uses non-greedy match on every <td> body to keep parsing robust to whitespace.
_ROW_RE = re.compile(
    r"<tr>\s*"
    r"<td>(?P<guid>\d+)</td>\s*"
    r"<td>(?P<type>[A-Z]+)</td>\s*"
    r"<td>(?P<ident>[^<]*)</td>\s*"
    r"<td>(?P<name>[^<]*)</td>\s*"
    r"<td>(?P<lat>[^<]+)</td>\s*"
    r"<td>(?P<lon>[^<]+)</td>\s*"
    r"<td>(?P<datum>[^<]*)</td>\s*"
    r"<td>(?P<eff_date>[^<]*)</td>\s*"
    r"<td>(?P<originator>[^<]*)</td>\s*"
    r"</tr>",
    re.IGNORECASE,
)

# Coord regexes — order matters: DMS variants before decimal so DDMMSS doesn't
# accidentally match the decimal pattern.
_LAT_DMS = re.compile(r"^(\d{2})(\d{2})(\d{2}(?:\.\d+)?)([NS])$")
_LAT_DM = re.compile(r"^(\d{2})(\d{2}(?:\.\d+)?)([NS])$")
_LAT_DEC = re.compile(r"^(\d{1,3}\.\d+)([NS])$")
_LON_DMS = re.compile(r"^(\d{3})(\d{2})(\d{2}(?:\.\d+)?)([EW])$")
_LON_DM = re.compile(r"^(\d{3})(\d{2}(?:\.\d+)?)([EW])$")
_LON_DEC = re.compile(r"^(\d{1,3}\.\d+)([EW])$")


def _parse_lat(s: str) -> Optional[float]:
    s = s.strip()
    if m := _LAT_DMS.match(s):
        v = int(m[1]) + int(m[2]) / 60.0 + float(m[3]) / 3600.0
        return -v if m[4] == "S" else v
    if m := _LAT_DM.match(s):
        v = int(m[1]) + float(m[2]) / 60.0
        return -v if m[3] == "S" else v
    if m := _LAT_DEC.match(s):
        v = float(m[1])
        return -v if m[2] == "S" else v
    return None


def _parse_lon(s: str) -> Optional[float]:
    s = s.strip()
    if m := _LON_DMS.match(s):
        v = int(m[1]) + int(m[2]) / 60.0 + float(m[3]) / 3600.0
        return -v if m[4] == "W" else v
    if m := _LON_DM.match(s):
        v = int(m[1]) + float(m[2]) / 60.0
        return -v if m[3] == "W" else v
    if m := _LON_DEC.match(s):
        v = float(m[1])
        return -v if m[2] == "W" else v
    return None


def _in_bbox(lat: float, lon: float, bbox: Tuple[float, float, float, float]) -> bool:
    lat_min, lat_max, lon_min, lon_max = bbox
    return lat_min <= lat <= lat_max and lon_min <= lon <= lon_max


def _slug_originator(orig: str) -> str:
    """Compress 'EUROCONTROL NMOC' style strings into a stable id token."""
    cleaned = re.sub(r"[^A-Z0-9]+", "_", orig.upper()).strip("_")
    return cleaned or "unknown"


class EurocontrolSDOSource(SourceInterface):
    """Local-file source for Eurocontrol SDO Designated Points HTML exports.

    Multiple export files (e.g. one per hemisphere) can be combined by passing
    a list of paths. Rows from all files are merged; the source de-duplicates
    by `(name, source_id)` so the same fix appearing in multiple hemisphere
    files isn't doubled.
    """

    def __init__(
        self,
        local_paths: Sequence[str],
        bboxes: Iterable[Tuple[float, float, float, float]] = (
            EUROPE_BBOX,
            NORTH_AMERICA_BBOX,
        ),
        types: Iterable[str] = ("ICAO",),
    ):
        """
        Args:
            local_paths: HTML export file(s) downloaded from EAD SDO.
            bboxes: Iterable of (lat_min, lat_max, lon_min, lon_max) tuples.
                A row is kept if it falls in any bbox. Default keeps Europe + NA.
            types: Row Type values to keep. Default is just "ICAO" — the
                standard 5-letter route waypoints.
        """
        self.local_paths = [Path(p) for p in local_paths]
        self.bboxes = tuple(bboxes)
        self.types = frozenset(types)

    def update_model(self, model: EuroAipModel, airports: Optional[List[str]] = None) -> None:
        waypoints = self._collect_waypoints()
        if not waypoints:
            logger.info("Eurocontrol SDO: no waypoints parsed from %d file(s)",
                        len(self.local_paths))
            return
        result = model.bulk_add_waypoints(waypoints)
        logger.info(
            "Eurocontrol SDO: added %d, updated %d waypoints from %d file(s)",
            result["added"], result["updated"], len(self.local_paths),
        )

    def _collect_waypoints(self) -> List[Waypoint]:
        # Dedupe across files by (name, source_id) — same fix in NE+NW would
        # otherwise be added twice with identical originator.
        seen: dict = {}
        for path in self.local_paths:
            if not path.exists():
                logger.warning("Eurocontrol SDO file not found: %s", path)
                continue
            for wp in self._parse_file(path):
                key = (wp.name, wp.source_id)
                if key not in seen:
                    seen[key] = wp
        return list(seen.values())

    def _parse_file(self, path: Path) -> List[Waypoint]:
        # Stream-friendly read: one regex pass over the whole file. SDO exports
        # are ~10 MB so this is fine; if it grows we can split on </tr>.
        text = path.read_text(encoding="utf-8", errors="replace")
        kept = 0
        skipped_type = 0
        skipped_bbox = 0
        skipped_coords = 0
        waypoints: List[Waypoint] = []

        for m in _ROW_RE.finditer(text):
            row_type = m.group("type").strip().upper()
            if row_type not in self.types:
                skipped_type += 1
                continue

            ident = m.group("ident").strip().upper()
            if not ident:
                continue

            lat = _parse_lat(m.group("lat").strip())
            lon = _parse_lon(m.group("lon").strip())
            if lat is None or lon is None:
                skipped_coords += 1
                continue

            if not any(_in_bbox(lat, lon, bb) for bb in self.bboxes):
                skipped_bbox += 1
                continue

            originator = m.group("originator").strip()
            waypoints.append(Waypoint(
                name=ident,
                latitude_deg=lat,
                longitude_deg=lon,
                point_type="5LNC",
                source="eurocontrol_sdo",
                source_id=f"eurocontrol_sdo:{_slug_originator(originator)}",
            ))
            kept += 1

        logger.info(
            "Eurocontrol SDO %s: kept %d, skipped %d (type), %d (bbox), %d (coords)",
            path.name, kept, skipped_type, skipped_bbox, skipped_coords,
        )
        return waypoints
