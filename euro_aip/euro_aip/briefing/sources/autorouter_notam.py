"""Autorouter NOTAM API source.

Fetches NOTAMs from the Autorouter API and converts them to Notam dataclass instances.
Uses the same AutorouterCredentialManager as the AIP data source for OAuth2 authentication.

API docs: https://www.autorouter.aero/wiki/api/notams/
"""

import json
import logging
import requests
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any

from euro_aip.briefing.models.notam import Notam, NotamCategory
from euro_aip.utils.autorouter_credentials import AutorouterCredentialManager

logger = logging.getLogger(__name__)

# Maximum items per API request (API limit)
_PAGE_LIMIT = 100
# Maximum ICAOs per request to avoid URL length issues
_ICAO_BATCH_SIZE = 20


class AutorouterNotamSource:
    """Fetches NOTAMs from the Autorouter API and converts to Notam models."""

    def __init__(self, credential_manager: AutorouterCredentialManager):
        self.credential_manager = credential_manager
        self.base_url = "https://api.autorouter.aero/v1.0/notam"

    def _get_headers(self) -> Dict[str, str]:
        """Get headers with Bearer token for API requests."""
        return {
            "Authorization": f"Bearer {self.credential_manager.get_token()}",
            "Accept": "application/json",
        }

    def fetch_notams(
        self,
        icaos: List[str],
        start_validity: Optional[datetime] = None,
        end_validity: Optional[datetime] = None,
    ) -> List[Notam]:
        """
        Fetch NOTAMs for given ICAO airport/FIR codes.

        Handles pagination (API limit of 100 per request) and deduplication
        when the same NOTAM appears for multiple queried locations.

        Args:
            icaos: ICAO airport codes and/or FIR codes (e.g., ["LFPG", "EGTT"])
            start_validity: Only return NOTAMs valid after this time
            end_validity: Only return NOTAMs valid before this time

        Returns:
            Deduplicated list of Notam objects
        """
        if not icaos:
            return []

        start_epoch = int(start_validity.timestamp()) if start_validity else None
        end_epoch = int(end_validity.timestamp()) if end_validity else None

        all_notams: List[Notam] = []

        # Batch ICAOs to avoid URL length issues
        for i in range(0, len(icaos), _ICAO_BATCH_SIZE):
            batch = icaos[i : i + _ICAO_BATCH_SIZE]
            offset = 0
            while True:
                rows = self._fetch_page(batch, offset, _PAGE_LIMIT, start_epoch, end_epoch)
                for row in rows:
                    try:
                        notam = self._row_to_notam(row)
                        all_notams.append(notam)
                    except Exception as e:
                        logger.warning("Failed to convert NOTAM row: %s — %s", row.get("id", "?"), e)
                if len(rows) < _PAGE_LIMIT:
                    break
                offset += _PAGE_LIMIT

        # Deduplicate by NOTAM id
        seen = set()
        unique = []
        for notam in all_notams:
            if notam.id not in seen:
                seen.add(notam.id)
                unique.append(notam)

        logger.info(
            "Fetched %d NOTAMs (%d unique) for %d ICAO codes",
            len(all_notams), len(unique), len(icaos),
        )
        return unique

    def _fetch_page(
        self,
        icaos: List[str],
        offset: int,
        limit: int,
        start_validity: Optional[int],
        end_validity: Optional[int],
    ) -> List[Dict[str, Any]]:
        """
        Fetch a single page of NOTAMs from the API.

        Args:
            icaos: ICAO codes for this batch
            offset: Pagination offset
            limit: Max results per page (API max: 100)
            start_validity: Unix epoch seconds or None
            end_validity: Unix epoch seconds or None

        Returns:
            List of raw NOTAM row dicts from the API
        """
        # "itemas" is the correct param name per Autorouter API:
        # https://www.autorouter.aero/wiki/api/notams/
        params: Dict[str, Any] = {
            "itemas": json.dumps(icaos),
            "offset": offset,
            "limit": limit,
        }
        if start_validity is not None:
            params["startvalidity"] = start_validity
        if end_validity is not None:
            params["endvalidity"] = end_validity

        try:
            response = requests.get(
                self.base_url, headers=self._get_headers(), params=params
            )
            response.raise_for_status()
            data = response.json()
            rows = data.get("rows", [])
            logger.debug(
                "Fetched page: offset=%d, got %d rows (total=%s)",
                offset, len(rows), data.get("total", "?"),
            )
            return rows
        except requests.RequestException as e:
            logger.error("Autorouter NOTAM API request failed: %s", e)
            raise

    @staticmethod
    def _row_to_notam(row: Dict[str, Any]) -> Notam:
        """
        Convert an Autorouter NOTAM API row to a Notam dataclass.

        API response fields:
            code23, code45, endvalidity, fir, id, itema, iteme,
            lat, lon, lower, upper, modified, nof, number,
            purpose, scope, series, startvalidity, suppressed,
            traffic, type, year
        """
        # Build NOTAM ID: series + number/year (e.g., "A1234/24")
        series = row.get("series", "")
        number = row.get("number", 0)
        year = row.get("year", 0)
        notam_id = f"{series}{number:04d}/{year % 100:02d}" if series else str(row.get("id", ""))

        # Reconstruct Q-code from code23 + code45 (e.g., "MR" + "LC" → "QMRLC")
        code23 = row.get("code23", "")
        code45 = row.get("code45", "")
        q_code = f"Q{code23}{code45}" if code23 and code45 else None

        # Category from Q-code
        category = NotamCategory.from_q_code(q_code) if q_code else None

        # Coordinates
        lat = row.get("lat")
        lon = row.get("lon")
        coordinates = (lat, lon) if lat is not None and lon is not None else None

        # Validity times (unix epoch → datetime UTC)
        start_epoch = row.get("startvalidity")
        end_epoch = row.get("endvalidity")

        effective_from = (
            datetime.fromtimestamp(start_epoch, tz=timezone.utc)
            if start_epoch
            else None
        )

        # endvalidity of 0 or very large value typically means permanent
        is_permanent = end_epoch is None or end_epoch == 0
        effective_to = (
            datetime.fromtimestamp(end_epoch, tz=timezone.utc)
            if end_epoch and not is_permanent
            else None
        )

        # Altitude limits: API returns flight levels, convert to feet
        lower_fl = row.get("lower")
        upper_fl = row.get("upper")
        lower_limit = lower_fl * 100 if lower_fl is not None else None
        upper_limit = upper_fl * 100 if upper_fl is not None else None

        message = row.get("iteme", "")

        return Notam(
            id=notam_id,
            location=row.get("itema", ""),
            raw_text=message,
            message=message,
            series=series or None,
            number=number or None,
            year=year or None,
            fir=row.get("fir"),
            q_code=q_code,
            traffic_type=row.get("traffic"),
            purpose=row.get("purpose"),
            scope=row.get("scope"),
            lower_limit=lower_limit,
            upper_limit=upper_limit,
            coordinates=coordinates,
            category=category,
            effective_from=effective_from,
            effective_to=effective_to,
            is_permanent=is_permanent,
            source="autorouter",
        )
