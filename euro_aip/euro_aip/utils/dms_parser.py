"""
DMS (Degrees, Minutes, Seconds) coordinate parser for Eurocontrol FRA format.

Parses coordinates in the format used by the Eurocontrol FRA Points list:
  Latitude:  N404519  -> 40 degrees, 45 minutes, 19 seconds North
  Longitude: E0183830 -> 18 degrees, 38 minutes, 30 seconds East
"""

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
