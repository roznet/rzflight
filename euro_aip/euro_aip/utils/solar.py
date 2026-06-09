"""Solar position and twilight calculations (UTC in, UTC out).

Stateless helpers in the style of ``utils/geometry.py`` — thin wrappers over
``astral`` so the rest of the codebase never imports astral directly. All
inputs and outputs are timezone-aware UTC ``datetime`` objects.

A single pair of primitives — :func:`solar_elevation` and
:func:`solar_azimuth` — answers "where is the sun, seen from (lat, lon) at
time T". :func:`sun_events` gives the day's sunrise/sunset (or civil
dawn/dusk) for margin checks.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Dict, Optional, Tuple

from astral import Observer
from astral.sun import azimuth, dawn, dusk, elevation, sunrise, sunset

# astral depression angles (degrees the sun centre sits below the horizon).
CIVIL_TWILIGHT_DEG = 6.0  # sun centre 6 deg below horizon = end of usable light


def _aware_utc(when: datetime) -> datetime:
    """Coerce a datetime to timezone-aware UTC (astral wants tz-aware)."""
    if when.tzinfo is None:
        return when.replace(tzinfo=timezone.utc)
    return when.astimezone(timezone.utc)


def solar_elevation(lat: float, lon: float, when_utc: datetime) -> float:
    """Sun elevation above the horizon in degrees (negative = below)."""
    return elevation(Observer(lat, lon), _aware_utc(when_utc))


def solar_azimuth(lat: float, lon: float, when_utc: datetime) -> float:
    """Sun bearing, degrees true, clockwise from north (0-360)."""
    return azimuth(Observer(lat, lon), _aware_utc(when_utc))


def solar_position(lat: float, lon: float, when_utc: datetime) -> Tuple[float, float]:
    """(elevation_deg, azimuth_deg_true) - single call, both values."""
    obs = Observer(lat, lon)
    when = _aware_utc(when_utc)
    return elevation(obs, when), azimuth(obs, when)


def sun_events(
    lat: float,
    lon: float,
    on: date,
    depression: float = 0.0,
) -> Dict[str, Optional[datetime]]:
    """Sunrise/sunset (depression=0) or dawn/dusk (depression=6 civil), all UTC.

    The result always has the **fixed keys** ``"morning"`` and ``"evening"`` so
    callers never have to guess which key name a given ``depression`` produced:

    - ``depression == 0`` → ``morning`` = sunrise, ``evening`` = sunset
    - ``depression > 0``  → ``morning`` = dawn,    ``evening`` = dusk
      (e.g. ``depression=6`` for civil twilight)

    Each value is ``None`` when that event does not occur on this date (polar day
    or polar night), where astral raises ``ValueError``. ``depression`` must be
    ``>= 0`` (degrees the sun centre sits *below* the horizon); a negative value
    is a programming error and raises ``ValueError`` rather than being masked.
    """
    if depression < 0.0:
        raise ValueError(
            f"depression must be >= 0 (degrees below the horizon), got {depression}"
        )

    obs = Observer(lat, lon)

    if depression == 0.0:
        def _morning() -> Optional[datetime]:
            return sunrise(obs, on)

        def _evening() -> Optional[datetime]:
            return sunset(obs, on)
    else:
        def _morning() -> Optional[datetime]:
            return dawn(obs, on, depression=depression)

        def _evening() -> Optional[datetime]:
            return dusk(obs, on, depression=depression)

    def _safe(fn) -> Optional[datetime]:
        try:
            return _aware_utc(fn())
        except ValueError:
            # Sun never reaches the requested depression today (polar day/night).
            return None

    return {"morning": _safe(_morning), "evening": _safe(_evening)}
