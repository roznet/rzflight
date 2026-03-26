"""
DMS (Degrees, Minutes, Seconds) coordinate parsers.

Supports two formats:
  Eurocontrol FRA:  N404519 / E0183830  (compact, hemisphere prefix)
  OpenNav:          49° 54' 7.00" N / 3° 26' 50.00" E  (human-readable, hemisphere suffix)
"""

import re
from typing import Tuple


def parse_fra_latitude(s: str) -> float:
    """Parse FRA latitude string to decimal degrees.

    Format: [N/S]DDMMSS (hemisphere + 6 digits)

    Args:
        s: Latitude string, e.g. "N404519"

    Returns:
        Latitude in decimal degrees (negative for South)

    Raises:
        ValueError: If the string format is invalid
    """
    s = s.strip()
    if len(s) != 7:
        raise ValueError(f"Invalid FRA latitude format (expected 7 chars): '{s}'")

    hemisphere = s[0].upper()
    if hemisphere not in ("N", "S"):
        raise ValueError(f"Invalid latitude hemisphere '{hemisphere}', expected N or S")

    degrees = int(s[1:3])
    minutes = int(s[3:5])
    seconds = int(s[5:7])

    decimal = degrees + minutes / 60.0 + seconds / 3600.0
    return -decimal if hemisphere == "S" else decimal


def parse_fra_longitude(s: str) -> float:
    """Parse FRA longitude string to decimal degrees.

    Format: [E/W]DDDMMSS (hemisphere + 7 digits)

    Args:
        s: Longitude string, e.g. "E0183830"

    Returns:
        Longitude in decimal degrees (negative for West)

    Raises:
        ValueError: If the string format is invalid
    """
    s = s.strip()
    if len(s) != 8:
        raise ValueError(f"Invalid FRA longitude format (expected 8 chars): '{s}'")

    hemisphere = s[0].upper()
    if hemisphere not in ("E", "W"):
        raise ValueError(f"Invalid longitude hemisphere '{hemisphere}', expected E or W")

    degrees = int(s[1:4])
    minutes = int(s[4:6])
    seconds = int(s[6:8])

    decimal = degrees + minutes / 60.0 + seconds / 3600.0
    return -decimal if hemisphere == "W" else decimal


def parse_fra_coordinates(lat_str: str, lon_str: str) -> Tuple[float, float]:
    """Parse FRA latitude and longitude strings to decimal degrees.

    Args:
        lat_str: Latitude string, e.g. "N404519"
        lon_str: Longitude string, e.g. "E0183830"

    Returns:
        Tuple of (latitude, longitude) in decimal degrees
    """
    return parse_fra_latitude(lat_str), parse_fra_longitude(lon_str)


# ========================================================================
# OpenNav DMS format: 49° 54' 7.00" N / 3° 26' 50.00" E
# ========================================================================

_DMS_PATTERN = re.compile(
    r"""(\d+)\s*(?:°|&deg;)\s*(\d+)\s*(?:['′]|&prime;)\s*([\d.]+)\s*(?:["″]|&Prime;)\s*([NSEW])""",
    re.IGNORECASE,
)


def parse_dms(s: str) -> float:
    """Parse a human-readable DMS string to decimal degrees.

    Handles formats like:
      49° 54' 7.00" N
      3° 26' 50.00" E
      007° 11' 29.00" W

    Args:
        s: DMS string with hemisphere letter (N/S/E/W)

    Returns:
        Decimal degrees (negative for S/W)

    Raises:
        ValueError: If the string cannot be parsed
    """
    m = _DMS_PATTERN.search(s.strip())
    if not m:
        raise ValueError(f"Cannot parse DMS string: '{s}'")

    degrees = int(m.group(1))
    minutes = int(m.group(2))
    seconds = float(m.group(3))
    hemisphere = m.group(4).upper()

    decimal = degrees + minutes / 60.0 + seconds / 3600.0
    if hemisphere in ("S", "W"):
        decimal = -decimal
    return decimal


def parse_dms_coordinates(lat_str: str, lon_str: str) -> Tuple[float, float]:
    """Parse human-readable DMS lat/lon strings to decimal degrees.

    Args:
        lat_str: e.g. "49° 54' 7.00\" N"
        lon_str: e.g. "3° 26' 50.00\" E"

    Returns:
        Tuple of (latitude, longitude) in decimal degrees
    """
    return parse_dms(lat_str), parse_dms(lon_str)
