"""
FAA NASR Fixes/Waypoints source.

Downloads the FIX_CSV subscription file from the FAA NASR (National Airspace
System Resources) 28-day subscription, which contains ~70,000 US named fixes
and waypoints with decimal coordinates, ARTCC assignments, and charting usage.

Used as a supplementary source for US coverage — the Eurocontrol FRA dataset
only covers ECAC, so US named fixes like ENRT intersections are missing without
this source.

Publication page: https://www.faa.gov/air_traffic/flight_info/aeronav/aero_data/NASR_Subscription/
Direct download (current cycle): https://nfdc.faa.gov/webContent/28DaySub/extra/{DD}_{MonAbbr}_{YYYY}_FIX_CSV.zip
No authentication required.
"""

import csv
import io
import logging
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import requests

from ..models.euro_aip_model import EuroAipModel
from ..models.waypoint import Waypoint
from .base import SourceInterface
from .cached import CachedSource

logger = logging.getLogger(__name__)

EFFECTIVE_DATE_URL = (
    "https://nfdc.faa.gov/nfdcApps/controllers/PublicDataController/"
    "getNasr56EffectiveDate"
)

# The CSV zip lives under /extra/ with a human-readable date in the filename.
# Example: 16_Apr_2026_FIX_CSV.zip
DOWNLOAD_URL_TEMPLATE = (
    "https://nfdc.faa.gov/webContent/28DaySub/extra/{date_str}_FIX_CSV.zip"
)


class FAANasrFixSource(CachedSource, SourceInterface):
    """Source for FAA NASR fixes/waypoints data.

    Downloads FIX_CSV.zip from the 28-day subscription, extracts FIX_BASE.csv,
    and emits Waypoint objects with decimal coordinates and ARTCC-based FIR codes.
    """

    def __init__(
        self,
        cache_dir: str,
        effective_date: Optional[str] = None,
        local_path: Optional[str] = None,
    ):
        """
        Args:
            cache_dir: Directory for caching the downloaded zip.
            effective_date: Optional cycle start date (YYYY-MM-DD). If not given,
                            discovered automatically via the NASR effective-date
                            endpoint.
            local_path: Optional path to a pre-downloaded FIX_CSV.zip. Skips
                        both discovery and download.
        """
        super().__init__(cache_dir)
        self.effective_date = effective_date
        self.local_path = Path(local_path) if local_path else None

    def update_model(self, model: EuroAipModel, airports: Optional[List[str]] = None) -> None:
        """Update the model with FAA NASR fixes."""
        waypoints = self._get_waypoints()
        if not waypoints:
            logger.info("FAA NASR: no waypoints parsed")
            return

        result = model.bulk_add_waypoints(waypoints)
        logger.info(
            "FAA NASR: added %d, updated %d waypoints",
            result["added"], result["updated"],
        )

    def _get_waypoints(self, max_age_days: int = 28) -> List[Waypoint]:
        zip_bytes = self._get_zip_bytes(max_age_days)
        csv_text = self._extract_fix_base_csv(zip_bytes)
        return self._parse_csv(csv_text)

    def _get_zip_bytes(self, max_age_days: int) -> bytes:
        """Return the FIX_CSV zip bytes, preferring local_path → cache → download."""
        if self.local_path and self.local_path.exists():
            logger.info("Using local FAA NASR file: %s", self.local_path)
            return self.local_path.read_bytes()

        effective_date = self.effective_date or self._discover_effective_date()
        cache_file = self._get_cache_file(f"fix_csv_{effective_date}", "zip")

        is_valid, reason = self._is_cache_valid(cache_file, max_age_days)
        if is_valid:
            logger.info("Using cached FAA NASR file: %s", cache_file)
            return cache_file.read_bytes()

        url = self._build_download_url(effective_date)
        logger.info("Downloading FAA NASR FIX_CSV from %s (cache %s)", url, reason)
        response = requests.get(url, timeout=60)
        response.raise_for_status()
        cache_file.write_bytes(response.content)
        return response.content

    def _discover_effective_date(self) -> str:
        """Query the NASR effective-date endpoint for the current cycle start date."""
        logger.info("Discovering current NASR effective date")
        response = requests.get(EFFECTIVE_DATE_URL, timeout=30)
        response.raise_for_status()
        data = response.json()
        start = data.get("start_effective_date")
        if not start:
            raise RuntimeError(f"No start_effective_date in response: {data}")
        return start

    @staticmethod
    def _build_download_url(effective_date: str) -> str:
        """Format '2026-04-16' into the '16_Apr_2026_FIX_CSV.zip' URL."""
        dt = datetime.strptime(effective_date, "%Y-%m-%d")
        date_str = dt.strftime("%d_%b_%Y")  # 16_Apr_2026
        return DOWNLOAD_URL_TEMPLATE.format(date_str=date_str)

    @staticmethod
    def _extract_fix_base_csv(zip_bytes: bytes) -> str:
        """Extract FIX_BASE.csv text from the FIX_CSV.zip archive."""
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            with zf.open("FIX_BASE.csv") as f:
                return f.read().decode("utf-8-sig")

    def _parse_csv(self, csv_text: str) -> List[Waypoint]:
        """Parse FIX_BASE.csv into Waypoint objects.

        Keeps all candidates — same ident in different states is stored as a
        distinct candidate (different source_id), letting the resolver's detour
        gate pick the right one at query time.
        """
        reader = csv.DictReader(io.StringIO(csv_text))
        seen: Dict[tuple, Waypoint] = {}
        skipped = 0

        for row in reader:
            try:
                wp = self._parse_row(row)
                if wp is None:
                    skipped += 1
                    continue
                key = (wp.name, wp.source_id)
                if key not in seen:
                    seen[key] = wp
            except Exception as e:
                logger.debug("FAA NASR row parse error: %s — %s", row.get("FIX_ID", "?"), e)
                skipped += 1

        logger.info(
            "Parsed %d fixes from FAA NASR CSV (%d skipped)",
            len(seen), skipped,
        )
        return list(seen.values())

    @staticmethod
    def _parse_row(row: Dict[str, str]) -> Optional[Waypoint]:
        ident = (row.get("FIX_ID") or "").strip().upper()
        if not ident:
            return None

        try:
            lat = float(row["LAT_DECIMAL"])
            lon = float(row["LONG_DECIMAL"])
        except (ValueError, KeyError, TypeError):
            return None

        state = (row.get("STATE_CODE") or "").strip().upper()

        # ARTCC = US equivalent of FIR; join high+low when they differ
        artcc_high = (row.get("ARTCC_ID_HIGH") or "").strip().upper()
        artcc_low = (row.get("ARTCC_ID_LOW") or "").strip().upper()
        if artcc_high and artcc_low and artcc_high != artcc_low:
            fir_codes = f"{artcc_high},{artcc_low}"
        else:
            fir_codes = artcc_high or artcc_low or None

        return Waypoint(
            name=ident,
            latitude_deg=lat,
            longitude_deg=lon,
            point_type="5LNC",
            fir_codes=fir_codes,
            source="faa_nasr",
            source_id=f"faa_nasr:{state}" if state else "faa_nasr:",
        )
