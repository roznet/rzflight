"""Autorouter GRAMET cross-section source.

Fetches GRAMET (vertical meteorological cross-section) images from the
Autorouter API. Returns raw image bytes (PNG or PDF).

API docs: https://www.autorouter.aero/wiki/api/
"""

import logging
import requests
from datetime import datetime
from typing import Dict, List, Optional

from euro_aip.utils.autorouter_credentials import AutorouterCredentialManager

logger = logging.getLogger(__name__)

GRAMET_URL = "https://api.autorouter.aero/v1.0/met/gramet"


class AutorouterGrametSource:
    """Fetches GRAMET cross-section images from the Autorouter API."""

    def __init__(self, credential_manager: AutorouterCredentialManager):
        self.credential_manager = credential_manager
        self.session = requests.Session()

    def _get_headers(self) -> Dict[str, str]:
        """Get headers with Bearer token for API requests."""
        return {
            "Authorization": f"Bearer {self.credential_manager.get_token()}",
        }

    def fetch_gramet(
        self,
        waypoints: List[str],
        altitude_ft: int,
        departure_time: datetime,
        duration_hours: float,
        fmt: str = "png",
    ) -> bytes:
        """Fetch a GRAMET cross-section image.

        Args:
            waypoints: Ordered list of ICAO waypoints defining the route.
            altitude_ft: Cruise altitude in feet.
            departure_time: Departure datetime (converted to Unix timestamp).
            duration_hours: Total estimated elapsed time in hours.
            fmt: Output format, ``"png"`` or ``"pdf"``.

        Returns:
            Raw bytes of the GRAMET image.

        Raises:
            requests.HTTPError: If the API returns an error status.
        """
        params = {
            "waypoints": " ".join(waypoints),
            "altitude": altitude_ft,
            "departuretime": int(departure_time.timestamp()),
            "totaleet": int(duration_hours * 3600),
            "format": fmt,
        }

        logger.info(
            "Fetching GRAMET: %s at FL%03d",
            " ".join(waypoints),
            altitude_ft // 100,
        )

        resp = self.session.get(
            GRAMET_URL,
            params=params,
            headers=self._get_headers(),
            timeout=30,
        )
        resp.raise_for_status()
        return resp.content
