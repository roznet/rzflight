"""VATSpy FIR boundary source.

Loads Flight Information Region (FIR) polygons from the VATSpy Data Project's
``Boundaries.geojson``. The dataset uses VATSIM controller-position
identifiers, which generally match real-world ICAO FIR codes (4 letters);
sub-sectors use a hyphenated suffix (e.g. ``EDGG-N``). This source ingests
only the parent (no-hyphen) features.

Source: https://github.com/vatsimnetwork/vatspy-data-project
License: CC-BY-SA-4.0 — attribute the VATSpy Data Project and contributors.
Update cadence: every AIRAC cycle (~28 days). The parent ``Boundaries.geojson``
on the master branch always reflects the latest cycle.
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

from ..models.euro_aip_model import EuroAipModel
from ..models.fir import FIR
from .base import SourceInterface
from .cached import CachedSource

logger = logging.getLogger(__name__)

GEOJSON_URL = (
    "https://raw.githubusercontent.com/vatsimnetwork/"
    "vatspy-data-project/master/Boundaries.geojson"
)


class VatspyFirSource(CachedSource, SourceInterface):
    """FIR boundary source using VATSpy ``Boundaries.geojson``."""

    def __init__(self, cache_dir: str, local_path: Optional[str] = None):
        """
        Args:
            cache_dir: Directory for caching downloaded files.
            local_path: Optional path to a locally downloaded geojson. When
                provided, skips the download.
        """
        super().__init__(cache_dir)
        self.local_path = Path(local_path) if local_path else None

    # SourceInterface ----------------------------------------------------------

    def update_model(self, model: EuroAipModel,
                     airports: Optional[List[str]] = None) -> None:
        """Update the model with FIR boundaries from VATSpy."""
        firs = self.get_firs()
        result = model.bulk_add_firs(firs)
        logger.info(
            "VATSpy: added %d, updated %d FIRs", result["added"], result["updated"],
        )

    # Public -------------------------------------------------------------------

    def get_firs(self, max_age_days: int = 28) -> List[FIR]:
        """Fetch and parse FIRs from the VATSpy geojson (cached)."""
        data = self._get_geojson(max_age_days)
        return self._parse_features(data)

    # Internals ----------------------------------------------------------------

    def _get_geojson(self, max_age_days: int) -> Dict[str, Any]:
        if self.local_path and self.local_path.exists():
            logger.info("Using local VATSpy boundaries file: %s", self.local_path)
            return json.loads(self.local_path.read_text())

        cache_file = self._get_cache_file("vatspy_boundaries", "geojson")
        is_valid, _ = self._is_cache_valid(cache_file, max_age_days)
        if is_valid:
            logger.info("Using cached VATSpy boundaries: %s", cache_file)
            return json.loads(cache_file.read_text())

        logger.info("Downloading VATSpy boundaries from %s", GEOJSON_URL)
        response = requests.get(GEOJSON_URL, timeout=60)
        response.raise_for_status()
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        cache_file.write_text(response.text)
        return response.json()

    @staticmethod
    def _parse_features(data: Dict[str, Any]) -> List[FIR]:
        firs: List[FIR] = []
        for feature in data.get("features", []):
            props = feature.get("properties") or {}
            fir_id = (props.get("id") or "").upper()
            # Skip sub-sectors (hyphenated) and empty ids. v1: parent FIRs only.
            if not fir_id or "-" in fir_id:
                continue
            geom = feature.get("geometry") or {}
            polygons = _normalize_to_multipolygon(geom)
            if not polygons:
                continue
            firs.append(FIR(
                icao=fir_id,
                polygons=polygons,
                is_oceanic=str(props.get("oceanic")) == "1",
                region=props.get("region"),
                label_lon=_safe_float(props.get("label_lon")),
                label_lat=_safe_float(props.get("label_lat")),
                source="vatspy",
            ))
        logger.info("Parsed %d parent FIRs from VATSpy boundaries", len(firs))
        return firs


def _normalize_to_multipolygon(geom: Dict[str, Any]) -> List[List[List]]:
    """Wrap GeoJSON Polygon into MultiPolygon shape; pass through MultiPolygon."""
    gtype = geom.get("type")
    coords = geom.get("coordinates")
    if not coords:
        return []
    if gtype == "Polygon":
        return [coords]
    if gtype == "MultiPolygon":
        return list(coords)
    return []


def _safe_float(v: Any) -> Optional[float]:
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None
