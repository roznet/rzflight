"""
ICAO Flight Plan (FPL) parser and model.

Parses ICAO FPL format strings into a rich ICAOFlightPlan dataclass with
all extractable fields, a populated Route, and derived convenience properties.

Example:
    from euro_aip.briefing.models.icao_fpl import parse_icao_fpl

    fpl = parse_icao_fpl('''
        (FPL-N122DR-VG
        -S22T/L-SBDGORVY/LB2
        -LFAT0930
        -N0166VFR DCT LYD DCT VESAN 4830N00210E DCT
        -EGTF0033 EGLL
        -PBN/B2C2D2 DOF/260318 RMK/FIKI EQUIPPED)
    ''')

    fpl.route.departure       # "LFAT"
    fpl.is_vfr                # True
    fpl.altitude_feet          # None (VFR)
    fpl.has_gnss              # True
    fpl.speed_knots           # 166
"""

import re
import logging
from dataclasses import dataclass, field
from datetime import date, time, datetime, timedelta, timezone
from typing import Optional, List, Dict, Tuple, TYPE_CHECKING

from euro_aip.briefing.models.route import Route, RoutePoint
from euro_aip.utils.dms_parser import parse_icao_coordinate, is_icao_coordinate

if TYPE_CHECKING:
    from euro_aip.models.route_resolver import RouteResolver

logger = logging.getLogger(__name__)

# Tokens to filter from route strings
_SKIP_TOKENS = {"DCT", "IFR", "VFR", "->", "TO", "STAY"}

# Airway pattern: 1-2 uppercase letters followed by 1-4 digits (e.g., L613, UL9, N871, UN872)
_AIRWAY_PATTERN = re.compile(r'^[A-Z]{1,2}\d{1,4}$')

# Speed prefix: N (knots) or K (km/h) followed by 4 digits
_SPEED_PATTERN = re.compile(r'^([NK])(\d{4})')

# Level/altitude prefix patterns in field 15 after speed
# F = flight level, A = altitude (hundreds of feet), S = standard metric,
# M = metric altitude (tens of meters), VFR/IFR = rules only
_LEVEL_PATTERN = re.compile(r'^([FASM]\d{3,4}|VFR|IFR)\b')

# Field 18 key/value pattern: KEY/VALUE (value runs until next KEY/ or end)
_FIELD18_KEY_PATTERN = re.compile(r'\b([A-Z]{2,4})/')

# Known field 18 keys
_FIELD18_KEYS = {
    "DOF", "PBN", "NAV", "COM", "DAT", "SUR", "DEP", "DEST", "ALTN",
    "REG", "EET", "SEL", "TYP", "CODE", "DLE", "OPR", "ORGN", "PER",
    "RMK", "RIF", "RVR", "STS", "TALT",
}


@dataclass
class ICAOFlightPlan:
    """Parsed ICAO flight plan with all extractable fields.

    The route field is a standard Route object populated with departure,
    destination, waypoints, coordinates (if resolver provided), and times.
    """

    # Core parsed fields
    aircraft_registration: Optional[str] = None
    aircraft_type: Optional[str] = None
    flight_rules: Optional[str] = None
    flight_type: Optional[str] = None
    speed: Optional[str] = None
    speed_knots: Optional[int] = None
    level: Optional[str] = None
    altitude_feet: Optional[int] = None
    equipment: Optional[str] = None
    surveillance: Optional[str] = None
    date_of_flight: Optional[date] = None
    departure_time_utc: Optional[time] = None
    eet_minutes: Optional[int] = None
    raw_route: Optional[str] = None
    other_info: Dict[str, str] = field(default_factory=dict)
    raw_text: str = ""

    # Populated route
    route: Route = field(default_factory=lambda: Route(departure="", destination=""))

    @property
    def is_ifr(self) -> bool:
        """True if flight rules include IFR (I, Y, or Z)."""
        return self.flight_rules in ("I", "Y", "Z") if self.flight_rules else False

    @property
    def is_vfr(self) -> bool:
        """True if flight rules are pure VFR."""
        return self.flight_rules == "V" if self.flight_rules else False

    @property
    def has_gnss(self) -> bool:
        """True if GNSS/GPS equipment indicated."""
        return "G" in (self.equipment or "")

    @property
    def has_rnav(self) -> bool:
        """True if PBN/RNAV approved."""
        return "R" in (self.equipment or "")

    @property
    def has_adsb(self) -> bool:
        """True if ADS-B out capability indicated."""
        surv = self.surveillance or ""
        return "B" in surv or "1" in surv or "2" in surv

    @property
    def has_rvsm(self) -> bool:
        """True if RVSM approved."""
        return "W" in (self.equipment or "")

    @property
    def pbn_codes(self) -> Optional[str]:
        """PBN capability codes from field 18."""
        return self.other_info.get("PBN")

    @property
    def remarks(self) -> Optional[str]:
        """Remarks from field 18."""
        return self.other_info.get("RMK")

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            "aircraft_registration": self.aircraft_registration,
            "aircraft_type": self.aircraft_type,
            "flight_rules": self.flight_rules,
            "flight_type": self.flight_type,
            "speed": self.speed,
            "speed_knots": self.speed_knots,
            "level": self.level,
            "altitude_feet": self.altitude_feet,
            "equipment": self.equipment,
            "surveillance": self.surveillance,
            "date_of_flight": self.date_of_flight.isoformat() if self.date_of_flight else None,
            "departure_time_utc": self.departure_time_utc.isoformat() if self.departure_time_utc else None,
            "eet_minutes": self.eet_minutes,
            "raw_route": self.raw_route,
            "other_info": self.other_info,
            "raw_text": self.raw_text,
            "route": self.route.to_dict(),
            "is_ifr": self.is_ifr,
            "is_vfr": self.is_vfr,
            "has_gnss": self.has_gnss,
            "has_rnav": self.has_rnav,
            "has_adsb": self.has_adsb,
            "has_rvsm": self.has_rvsm,
        }

    def __repr__(self) -> str:
        reg = self.aircraft_registration or "?"
        rules = self.flight_rules or "?"
        return f"ICAOFlightPlan({reg} {self.route} {rules})"


# ========================================================================
# Parser
# ========================================================================

def parse_icao_fpl(
    text: str,
    resolver: Optional['RouteResolver'] = None,
) -> Optional[ICAOFlightPlan]:
    """Parse an ICAO FPL string into an ICAOFlightPlan.

    Args:
        text: String containing an ICAO flight plan in (FPL-...) format.
        resolver: Optional RouteResolver to resolve waypoint/airport coordinates.

    Returns:
        ICAOFlightPlan with all extractable fields, or None if no FPL block found.
    """
    # Step 1: Extract FPL block
    match = re.search(r'\(FPL[^)]*\)', text, re.DOTALL)
    if not match:
        return None

    fpl_body = match.group(0)
    raw_text = fpl_body

    # Strip outer parens and collapse whitespace
    fpl_body = fpl_body[1:-1]  # remove ( and )
    fpl_body = re.sub(r'\s+', ' ', fpl_body).strip()

    # Step 2: Split fields
    fields = _split_fields(fpl_body)
    if len(fields) < 6:
        logger.warning("FPL has fewer than 6 fields, cannot parse: %s", fields)
        return None

    result = ICAOFlightPlan(raw_text=raw_text)

    # Step 3: Parse each field
    _parse_field7(fields[0], result)
    _parse_field8(fields[1], result)
    _parse_field9(fields[2], result)

    # Field 10 (equipment) may cause an extra split
    if len(fields) > 7:
        _parse_field10(fields[3], result)
        field13_idx = 4
    else:
        field13_idx = 3

    _parse_field13(fields[field13_idx], result)

    field15_idx = field13_idx + 1
    if field15_idx < len(fields):
        _parse_field15(fields[field15_idx], result)

    field16_idx = field15_idx + 1
    if field16_idx < len(fields):
        _parse_field16(fields[field16_idx], result)

    field18_idx = field16_idx + 1
    if field18_idx < len(fields):
        # Field 18 may span remaining fields if there were stray dashes
        field18_text = " -".join(fields[field18_idx:])
        _parse_field18(field18_text, result)

    # Step 4: Parse route tokens
    _parse_route_tokens(result, resolver)

    # Step 5: Compute derived fields
    _compute_derived(result)

    return result


def _split_fields(body: str) -> List[str]:
    """Split FPL body into fields."""
    # Remove FPL prefix
    if body.startswith("FPL"):
        body = body[3:]
    body = body.strip().lstrip("-").strip()

    # Split on " -" (field boundaries after whitespace normalization)
    parts = body.split(" -")
    fields = []
    for i, part in enumerate(parts):
        if i == 0:
            # First part has registration-rules with internal dashes
            subparts = part.split("-")
            fields.extend(sp.strip() for sp in subparts if sp.strip())
        else:
            stripped = part.strip()
            if stripped:
                fields.append(stripped)
    return fields


def _parse_field7(field: str, result: ICAOFlightPlan) -> None:
    """Field 7: Aircraft identification (registration)."""
    result.aircraft_registration = field.strip().upper()


def _parse_field8(field: str, result: ICAOFlightPlan) -> None:
    """Field 8: Flight rules and type."""
    trimmed = field.strip().upper()
    if len(trimmed) >= 1:
        result.flight_rules = trimmed[0]
    if len(trimmed) >= 2:
        result.flight_type = trimmed[1:]


def _parse_field9(field: str, result: ICAOFlightPlan) -> None:
    """Field 9: Aircraft type (and possibly equipment if joined by dash).

    Field 9 may contain equipment joined by a dash when the FPL field boundary
    dash is not space-separated: "S22T/L-SBDGORVY/LB2"
    In this case we split on "-" and parse equipment from the second part.
    """
    trimmed = field.strip().upper()

    # Check if equipment is embedded (e.g., "S22T/L-SBDGORVY/LB2")
    if "-" in trimmed:
        parts = trimmed.split("-", 1)
        type_part = parts[0].strip()
        equip_part = parts[1].strip()

        # Parse aircraft type from first part
        if "/" in type_part:
            result.aircraft_type = type_part[:type_part.index("/")].strip()
        else:
            result.aircraft_type = type_part

        # Parse equipment from second part
        _parse_equipment_string(equip_part, result)
    else:
        if "/" in trimmed:
            result.aircraft_type = trimmed[:trimmed.index("/")].strip()
        else:
            result.aircraft_type = trimmed


def _parse_equipment_string(s: str, result: ICAOFlightPlan) -> None:
    """Parse an equipment/surveillance string like 'SBDGORVY/LB2'."""
    s = s.strip().upper()
    if "/" in s:
        parts = s.split("/", 1)
        result.equipment = parts[0]
        result.surveillance = parts[1]
    else:
        result.equipment = s


def _parse_field10(field: str, result: ICAOFlightPlan) -> None:
    """Field 10: Equipment and surveillance (from an extra split part)."""
    _parse_equipment_string(field, result)


def _parse_field13(field: str, result: ICAOFlightPlan) -> None:
    """Field 13: Departure aerodrome and time."""
    trimmed = field.strip().upper()
    if len(trimmed) < 8:
        # May just have the ICAO code
        if len(trimmed) >= 4:
            result.route = Route(departure=trimmed[:4], destination="")
        return

    icao = trimmed[:4]
    time_str = trimmed[4:8]

    try:
        hour = int(time_str[:2])
        minute = int(time_str[2:4])
        if 0 <= hour <= 23 and 0 <= minute <= 59:
            result.departure_time_utc = time(hour, minute)
    except ValueError:
        pass

    result.route = Route(departure=icao, destination=result.route.destination)


def _parse_field15(field: str, result: ICAOFlightPlan) -> None:
    """Field 15: Cruising speed, level, and route."""
    trimmed = field.strip().upper()

    # Extract speed
    speed_match = _SPEED_PATTERN.match(trimmed)
    if speed_match:
        prefix = speed_match.group(1)
        digits = int(speed_match.group(2))
        result.speed = speed_match.group(0)

        if prefix == "N":
            result.speed_knots = digits
        elif prefix == "K":
            result.speed_knots = round(digits / 1.852)

        trimmed = trimmed[speed_match.end():].strip()

    # Extract level/altitude
    level_match = _LEVEL_PATTERN.match(trimmed)
    if level_match:
        result.level = level_match.group(1)
        result.altitude_feet = _parse_altitude(result.level)
        trimmed = trimmed[level_match.end():].strip()

    result.raw_route = trimmed if trimmed else None


def _parse_altitude(level: str) -> Optional[int]:
    """Convert level string to altitude in feet."""
    if not level:
        return None
    if level in ("VFR", "IFR"):
        return None
    prefix = level[0]
    try:
        digits = int(level[1:])
    except ValueError:
        return None

    if prefix == "F":
        return digits * 100  # Flight level → feet
    elif prefix == "A":
        return digits * 100  # Altitude in hundreds of feet
    elif prefix == "S":
        return round(digits * 10 * 3.28084)  # Standard metric (tens of meters) → feet
    elif prefix == "M":
        return round(digits * 10 * 3.28084)  # Metric altitude (tens of meters) → feet
    return None


def _parse_field16(field: str, result: ICAOFlightPlan) -> None:
    """Field 16: Destination aerodrome, EET, and alternates."""
    trimmed = field.strip().upper()
    if len(trimmed) < 4:
        return

    dest_icao = trimmed[:4]

    # Update route with destination
    result.route = Route(
        departure=result.route.departure,
        destination=dest_icao,
        alternates=result.route.alternates,
        waypoints=result.route.waypoints,
        aircraft_type=result.route.aircraft_type,
        departure_time=result.route.departure_time,
        arrival_time=result.route.arrival_time,
    )

    # EET: next 4 chars after destination ICAO
    if len(trimmed) >= 8:
        eet_str = trimmed[4:8]
        try:
            hour = int(eet_str[:2])
            minute = int(eet_str[2:4])
            if 0 <= hour <= 99 and 0 <= minute <= 59:
                result.eet_minutes = hour * 60 + minute
        except ValueError:
            pass

    # Alternates: remaining tokens after ICAO+EET
    remainder = trimmed[8:].strip() if len(trimmed) > 8 else ""
    if remainder:
        alternates = [tok for tok in remainder.split() if len(tok) == 4 and tok.isalpha()]
        if alternates:
            result.route = Route(
                departure=result.route.departure,
                destination=result.route.destination,
                alternates=alternates,
                waypoints=result.route.waypoints,
                aircraft_type=result.route.aircraft_type,
                departure_time=result.route.departure_time,
                arrival_time=result.route.arrival_time,
            )


def _parse_field18(field: str, result: ICAOFlightPlan) -> None:
    """Field 18: Other information — key/value pairs."""
    trimmed = field.strip()
    if not trimmed or trimmed == "0":
        return

    # Find all KEY/ positions
    keys_positions = []
    for m in _FIELD18_KEY_PATTERN.finditer(trimmed):
        key = m.group(1).upper()
        if key in _FIELD18_KEYS:
            keys_positions.append((m.start(), key, m.end()))

    if not keys_positions:
        # No recognized keys, store as-is
        result.other_info["RAW"] = trimmed
        return

    for i, (start, key, val_start) in enumerate(keys_positions):
        if i + 1 < len(keys_positions):
            val_end = keys_positions[i + 1][0]
        else:
            val_end = len(trimmed)
        value = trimmed[val_start:val_end].strip().rstrip()
        result.other_info[key] = value

    # Extract DOF → date_of_flight
    dof = result.other_info.get("DOF")
    if dof and len(dof) >= 6:
        try:
            dof_clean = dof[:6]
            yy = int(dof_clean[:2])
            mm = int(dof_clean[2:4])
            dd = int(dof_clean[4:6])
            result.date_of_flight = date(2000 + yy, mm, dd)
        except (ValueError, IndexError):
            logger.debug("Could not parse DOF: %s", dof)


def _parse_route_tokens(result: ICAOFlightPlan, resolver: Optional['RouteResolver']) -> None:
    """Parse route tokens from raw_route into waypoints and coordinates."""
    if not result.raw_route:
        return

    tokens = result.raw_route.split()
    waypoint_names: List[str] = []
    waypoint_coords: List[RoutePoint] = []

    for token in tokens:
        token = token.strip()
        if not token:
            continue

        # Skip filtered tokens
        if token in _SKIP_TOKENS:
            continue

        # GPS coordinate
        if is_icao_coordinate(token):
            try:
                lat, lon = parse_icao_coordinate(token)
                waypoint_names.append(token)
                waypoint_coords.append(RoutePoint(
                    name=token,
                    latitude=lat,
                    longitude=lon,
                    point_type="gps",
                ))
            except ValueError:
                logger.debug("Failed to parse GPS coordinate token: %s", token)
            continue

        # Airway — skip
        if _AIRWAY_PATTERN.match(token):
            continue

        # Waypoint or airport name
        waypoint_names.append(token)

        # Resolve if we have a resolver
        if resolver:
            point = resolver.resolve_point(token)
            if point:
                waypoint_coords.append(point)

    # Rebuild route with waypoints
    route = result.route
    dep_coords = None
    dest_coords = None
    alternate_coords = {}

    if resolver:
        dep_point = resolver.resolve_point(route.departure)
        if dep_point:
            dep_coords = (dep_point.latitude, dep_point.longitude)
        dest_point = resolver.resolve_point(route.destination)
        if dest_point:
            dest_coords = (dest_point.latitude, dest_point.longitude)
        for alt in route.alternates:
            alt_point = resolver.resolve_point(alt)
            if alt_point:
                alternate_coords[alt] = (alt_point.latitude, alt_point.longitude)

    result.route = Route(
        departure=route.departure,
        destination=route.destination,
        alternates=route.alternates,
        waypoints=waypoint_names,
        departure_coords=dep_coords,
        destination_coords=dest_coords,
        alternate_coords=alternate_coords,
        waypoint_coords=waypoint_coords,
        aircraft_type=result.aircraft_type,
        departure_time=route.departure_time,
        arrival_time=route.arrival_time,
    )


def _compute_derived(result: ICAOFlightPlan) -> None:
    """Compute derived fields from parsed data."""
    # Build departure datetime if we have both date and time
    dep_datetime = None
    if result.date_of_flight and result.departure_time_utc:
        dep_datetime = datetime.combine(
            result.date_of_flight, result.departure_time_utc, tzinfo=timezone.utc
        )

    # Compute arrival time from departure + EET
    arr_datetime = None
    if dep_datetime and result.eet_minutes:
        arr_datetime = dep_datetime + timedelta(minutes=result.eet_minutes)

    # Update route with times and aircraft type
    if dep_datetime or arr_datetime or result.aircraft_type:
        route = result.route
        result.route = Route(
            departure=route.departure,
            destination=route.destination,
            alternates=route.alternates,
            waypoints=route.waypoints,
            departure_coords=route.departure_coords,
            destination_coords=route.destination_coords,
            alternate_coords=route.alternate_coords,
            waypoint_coords=route.waypoint_coords,
            aircraft_type=result.aircraft_type,
            departure_time=dep_datetime or route.departure_time,
            arrival_time=arr_datetime or route.arrival_time,
        )

    # If equipment wasn't parsed from field 10 split, try extracting from field 9 area
    # (when equipment was part of field 9 and didn't create an extra split)
    if result.equipment is None and result.other_info:
        # Equipment info might be in the raw fields — already handled by split logic
        pass
