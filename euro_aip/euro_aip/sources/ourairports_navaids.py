"""
OurAirports NAVAID source.

Downloads the navaids.csv from the OurAirports dataset on GitHub, which
contains ~4,700 worldwide NAVAIDs (VOR, DME, NDB, VORTAC, TACAN, etc.).

Used as a supplementary source — only adds NAVAIDs not already present
from Eurocontrol FRA or OpenNav, so it fills gaps without overwriting
more authoritative data.

Data source: https://github.com/davidmegginson/ourairports-data
CSV URL: https://raw.githubusercontent.com/davidmegginson/ourairports-data/main/navaids.csv
"""

import csv
import io
import logging
from typing import Dict, List, Optional

import requests

from ..models.euro_aip_model import EuroAipModel
from ..models.waypoint import Waypoint
from .base import SourceInterface
from .cached import CachedSource

logger = logging.getLogger(__name__)

CSV_URL = (
    "https://raw.githubusercontent.com/davidmegginson/ourairports-data"
    "/refs/heads/main/navaids.csv"
)

# Map OurAirports type names to our point_type values
_TYPE_MAP = {
    "VOR": "VOR",
    "VOR-DME": "VORDME",
    "VORTAC": "VORTAC",
    "DME": "DME",
    "NDB": "NDB",
    "NDB-DME": "NDBDME",
    "TACAN": "TACAN",
}


class OurAirportsNavaidSource(CachedSource, SourceInterface):
    """Source for OurAirports NAVAID data.

    Downloads navaids.csv and creates Waypoint objects for NAVAIDs not
    already in the model. Only adds missing entries — does not overwrite
    data from more authoritative sources (Eurocontrol FRA, OpenNav).
    """

    def __init__(self, cache_dir: str, countries: Optional[List[str]] = None):
        """
        Args:
            cache_dir: Directory for caching the downloaded CSV.
            countries: Optional ISO country codes to filter (e.g., ["FR", "GB"]).
                       If None, includes all countries.
        """
        super().__init__(cache_dir)
        self.countries = {c.upper() for c in countries} if countries else None

    def update_model(self, model: EuroAipModel, airports: Optional[List[str]] = None) -> None:
        """Update the model with OurAirports NAVAIDs, skipping existing waypoints."""
        all_waypoints = self._get_navaids()

        # Only add waypoints not already in the model
        new_waypoints = [
            wp for wp in all_waypoints
            if model.get_waypoint(wp.name) is None
        ]

        if new_waypoints:
            result = model.bulk_add_waypoints(new_waypoints)
            logger.info(
                "OurAirports: added %d NAVAIDs (%d already existed, skipped)",
                result["added"], len(all_waypoints) - len(new_waypoints),
            )
        else:
            logger.info(
                "OurAirports: all %d NAVAIDs already present, nothing to add",
                len(all_waypoints),
            )

    def _get_navaids(self, max_age_days: int = 28) -> List[Waypoint]:
        """Get NAVAID waypoints, using cache if available."""
        csv_data = self._get_csv_data(max_age_days)
        return self._parse_csv(csv_data)

    def _get_csv_data(self, max_age_days: int) -> str:
        """Get CSV data from cache or download."""
        cache_file = self._get_cache_file("navaids", "csv")
        is_valid, reason = self._is_cache_valid(cache_file, max_age_days)

        if is_valid:
            logger.info("Using cached OurAirports navaids CSV")
            return cache_file.read_text(encoding="utf-8")

        logger.info("Downloading OurAirports navaids CSV (cache %s)", reason)
        response = requests.get(CSV_URL, timeout=30)
        response.raise_for_status()
        data = response.text
        cache_file.write_text(data, encoding="utf-8")
        return data

    def _parse_csv(self, csv_text: str) -> List[Waypoint]:
        """Parse navaids.csv into Waypoint objects."""
        reader = csv.DictReader(io.StringIO(csv_text))
        waypoints: Dict[str, Waypoint] = {}
        skipped = 0

        for row in reader:
            try:
                wp = self._parse_row(row)
                if wp is None:
                    skipped += 1
                    continue

                # Deduplicate by ident — keep first occurrence
                if wp.name not in waypoints:
                    waypoints[wp.name] = wp
            except Exception as e:
                logger.debug("OurAirports row parse error: %s — %s", row.get("ident", "?"), e)
                skipped += 1

        logger.info(
            "Parsed %d unique NAVAIDs from OurAirports CSV (%d skipped)",
            len(waypoints), skipped,
        )
        return list(waypoints.values())

    def _parse_row(self, row: Dict[str, str]) -> Optional[Waypoint]:
        """Parse a single CSV row into a Waypoint, or None to skip."""
        ident = (row.get("ident") or "").strip().upper()
        if not ident:
            return None

        # Filter by country if specified
        country = (row.get("iso_country") or "").strip().upper()
        if self.countries and country not in self.countries:
            return None

        # Parse type
        raw_type = (row.get("type") or "").strip()
        point_type = _TYPE_MAP.get(raw_type)
        if point_type is None:
            return None  # Unknown type, skip

        # Parse coordinates
        try:
            lat = float(row["latitude_deg"])
            lon = float(row["longitude_deg"])
        except (ValueError, KeyError):
            return None

        return Waypoint(
            name=ident,
            latitude_deg=lat,
            longitude_deg=lon,
            point_type=point_type,
            source="ourairports",
        )
