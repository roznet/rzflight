"""
ICAO Field-15 route tokenizer.

Parses a Field 15 route string into an ordered, classified list of tokens.
Pure function: no DB access, no resolution. Callers can filter/reuse tokens
as they need — see :func:`waypoints_of` and :func:`annotations_of`.

Example:
    >>> tokens = parse_field15("N0175F160 EGTF DCT BILGO/N0180F100 UL612 XIDIL VFR LSGS")
    >>> [t.kind.value for t in tokens]
    ['speed_level', 'waypoint', 'direct', 'waypoint', 'airway', 'waypoint', 'flight_rule', 'waypoint']
    >>> waypoints_of(tokens)
    ['EGTF', 'BILGO', 'XIDIL', 'LSGS']
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional


class TokenKind(Enum):
    WAYPOINT = "waypoint"
    AIRWAY = "airway"
    SPEED_LEVEL = "speed_level"
    FLIGHT_RULE = "flight_rule"
    DIRECT = "direct"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class RouteToken:
    """A classified Field-15 token.

    ``raw`` is the original substring as it appeared (case preserved for
    round-trip). ``value`` is the normalized payload used by consumers —
    uppercased, and with any ``/QUALIFIER`` suffix stripped off. When a
    token carried a ``/QUALIFIER`` suffix (e.g. ``BILGO/N0180F100``), the
    suffix is captured in ``qualifier``. ``position`` is the character
    offset of ``raw`` in the original route string.
    """

    raw: str
    kind: TokenKind
    value: str
    qualifier: Optional[str] = None
    position: int = 0


_DIRECT_LITERALS = {"DCT", "->", "TO"}
_FLIGHT_RULE_LITERALS = {"IFR", "VFR"}

# Order matters in _classify: SPEED_LEVEL before AIRWAY because both can
# start with a letter+digit. The SPEED_LEVEL regex requires an [FASM]
# separator plus a trailing digit group, so the two don't actually overlap,
# but the ordering makes the intent explicit.
_SPEED_LEVEL_RE = re.compile(r"^[NMK]\d{3,4}[FASM]\d{3,4}$")
_AIRWAY_RE = re.compile(r"^[A-Z]{1,2}\d+[A-Z]?$")
_WAYPOINT_RE = re.compile(r"^[A-Z]{2,5}$")


def _classify(value: str) -> TokenKind:
    if value in _DIRECT_LITERALS:
        return TokenKind.DIRECT
    if value in _FLIGHT_RULE_LITERALS:
        return TokenKind.FLIGHT_RULE
    if _SPEED_LEVEL_RE.match(value):
        return TokenKind.SPEED_LEVEL
    if _AIRWAY_RE.match(value):
        return TokenKind.AIRWAY
    if _WAYPOINT_RE.match(value):
        return TokenKind.WAYPOINT
    return TokenKind.UNKNOWN


def parse_field15(route_string: str) -> List[RouteToken]:
    """Parse an ICAO Field-15 route string into an ordered token list.

    Splits on whitespace; for each whitespace-delimited chunk, an optional
    ``/QUALIFIER`` suffix is peeled off before classification (so
    ``BILGO/N0180F100`` becomes one WAYPOINT token with the qualifier
    captured, not two tokens).

    Order is preserved: callers can reconstruct original intent
    ('airway UL612 between these two waypoints') or report drops in context
    ('dropped IFR between BILGO and XIDIL').

    Args:
        route_string: Raw Field-15 text. May be empty/whitespace-only.

    Returns:
        Ordered list of ``RouteToken``. Empty if the input is blank.
    """
    if not route_string or not route_string.strip():
        return []

    tokens: List[RouteToken] = []
    # Walk the original string so ``position`` is the real char offset.
    i = 0
    n = len(route_string)
    while i < n:
        if route_string[i].isspace():
            i += 1
            continue
        start = i
        while i < n and not route_string[i].isspace():
            i += 1
        raw = route_string[start:i]

        head, sep, tail = raw.partition("/")
        value = head.upper()
        qualifier = tail.upper() if sep else None

        tokens.append(
            RouteToken(
                raw=raw,
                kind=_classify(value),
                value=value,
                qualifier=qualifier,
                position=start,
            )
        )

    return tokens


def waypoints_of(tokens: List[RouteToken]) -> List[str]:
    """Return just the waypoint names, in order."""
    return [t.value for t in tokens if t.kind is TokenKind.WAYPOINT]


def annotations_of(tokens: List[RouteToken]) -> List[RouteToken]:
    """Return every non-waypoint token, in order (for debug/feedback)."""
    return [t for t in tokens if t.kind is not TokenKind.WAYPOINT]
