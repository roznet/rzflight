"""
Parser for ICAO NOTAM format.

Handles both full NOTAM format and abbreviated formats found in briefing documents.
"""

import re
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple

from euro_aip.briefing.models.notam import Notam, NotamCategory


class NotamParser:
    """
    Parser for ICAO NOTAM format.

    Parses NOTAMs from text, extracting structured fields including:
    - NOTAM ID and series
    - Q-line (FIR, code, traffic, purpose, scope, limits, coordinates)
    - A-line (location)
    - B/C lines (effective times)
    - D-line (schedule)
    - E-line (message)
    - F/G lines (altitude limits)

    Example:
        notam = NotamParser.parse('''
            A1234/24 NOTAMN
            Q) LFFF/QMRLC/IV/NBO/A/000/999/4901N00225E005
            A) LFPG B) 2401150800 C) 2401152000
            E) RWY 09L/27R CLSD DUE TO MAINTENANCE
        ''')
    """

    # Regex patterns
    NOTAM_ID_PATTERN = re.compile(
        r'([A-Z])(\d{4})/(\d{2})',
        re.IGNORECASE
    )

    # Q-line pattern: FIR/QCODE/TRAFFIC/PURPOSE/SCOPE/LOWER/UPPER/COORDS
    # Note: \s* before each / to handle occasional whitespace in Q-lines
    Q_LINE_PATTERN = re.compile(
        r'Q\)\s*'
        r'([A-Z]{4})\s*/'           # FIR (4 letters)
        r'Q([A-Z]{2,5})\s*/'        # Q-code (2-5 letters after Q)
        r'([IVK]+)\s*/'             # Traffic type
        r'([NBOMK]+)\s*/'           # Purpose
        r'([AEW]+)\s*/'             # Scope
        r'(\d{3})\s*/'              # Lower limit (FL)
        r'(\d{3})\s*/'              # Upper limit (FL)
        r'(\d{4}[NS]\d{5}[EW])'     # Coordinates
        r'(\d{3})?',                # Radius (optional)
        re.IGNORECASE
    )

    # Alternative Q-line pattern for simpler formats
    Q_LINE_SIMPLE_PATTERN = re.compile(
        r'Q\)\s*([A-Z]{4})/Q([A-Z]{2,5})',
        re.IGNORECASE
    )

    # Date/time pattern: YYMMDDHHMM
    DATETIME_PATTERN = re.compile(r'(\d{10})')

    # Coordinate pattern for parsing: DDMMN/S DDDMME/W or decimal
    COORD_PATTERN = re.compile(
        r'(\d{2})(\d{2})([NS])\s*(\d{3})(\d{2})([EW])',
        re.IGNORECASE
    )

    # Q-code to category mapping
    Q_CODE_CATEGORIES: Dict[str, NotamCategory] = {
        'MR': NotamCategory.RUNWAY,
        'MX': NotamCategory.MOVEMENT_AREA,
        'MA': NotamCategory.MOVEMENT_AREA,
        'LR': NotamCategory.LIGHTING,
        'LL': NotamCategory.LIGHTING,
        'LX': NotamCategory.LIGHTING,
        'NA': NotamCategory.NAVIGATION,
        'NV': NotamCategory.NAVIGATION,
        'ND': NotamCategory.NAVIGATION,
        'NI': NotamCategory.NAVIGATION,
        'NL': NotamCategory.NAVIGATION,
        'NM': NotamCategory.NAVIGATION,
        'NB': NotamCategory.NAVIGATION,
        'CO': NotamCategory.COMMUNICATION,
        'FA': NotamCategory.AIRSPACE,
        'AR': NotamCategory.AIRSPACE,
        'AH': NotamCategory.AIRSPACE,
        'AL': NotamCategory.AIRSPACE,
        'AT': NotamCategory.AIRSPACE,
        'AX': NotamCategory.AIRSPACE,
        'RD': NotamCategory.AIRSPACE,
        'RT': NotamCategory.AIRSPACE,
        'OB': NotamCategory.OBSTACLE,
        'OL': NotamCategory.OBSTACLE,
        'PI': NotamCategory.PROCEDURE,
        'PA': NotamCategory.PROCEDURE,
        'PD': NotamCategory.PROCEDURE,
        'PS': NotamCategory.PROCEDURE,
        'PT': NotamCategory.PROCEDURE,
        'SE': NotamCategory.SERVICES,
        'SA': NotamCategory.SERVICES,
        'SN': NotamCategory.SERVICES,
        'SV': NotamCategory.SERVICES,
        'WA': NotamCategory.WARNING,
        'WE': NotamCategory.WARNING,
        'WM': NotamCategory.WARNING,
        'WP': NotamCategory.WARNING,
        'WU': NotamCategory.WARNING,
        'WV': NotamCategory.WARNING,
        'WZ': NotamCategory.WARNING,
    }

    @classmethod
    def parse(cls, text: str, source: Optional[str] = None) -> Optional[Notam]:
        """
        Parse a single NOTAM from text.

        Args:
            text: Raw NOTAM text
            source: Source identifier

        Returns:
            Parsed Notam object or None if parsing fails
        """
        text = text.strip()
        if not text:
            return None

        # Extract NOTAM ID
        notam_id, series, number, year = cls._parse_notam_id(text)
        if not notam_id:
            # Try to generate an ID from content hash
            notam_id = f"X{abs(hash(text)) % 10000:04d}/00"

        # Parse Q-line
        q_data = cls._parse_q_line(text)

        # Parse location (A-line)
        location = cls._parse_location(text)
        if not location and q_data.get('fir'):
            # Use FIR as fallback location
            location = q_data['fir']
        if not location:
            location = "ZZZZ"  # Unknown

        # Parse effective times
        effective_from, effective_to = cls._parse_effective_times(text)

        # Check if permanent
        is_permanent = cls._is_permanent(text, effective_to)

        # Parse schedule
        schedule_text = cls._parse_schedule(text)

        # Parse message (E-line)
        message = cls._parse_message(text)

        # Parse altitude limits
        lower_limit, upper_limit = cls._parse_altitude_limits(text, q_data)

        # Determine category from Q-code
        category = cls._determine_category(q_data.get('q_code'))

        return Notam(
            id=notam_id,
            series=series,
            number=number,
            year=year,
            location=location,
            fir=q_data.get('fir'),
            affected_locations=[location] if location and location != "ZZZZ" else [],
            q_code=q_data.get('q_code'),
            traffic_type=q_data.get('traffic_type'),
            purpose=q_data.get('purpose'),
            scope=q_data.get('scope'),
            lower_limit=lower_limit,
            upper_limit=upper_limit,
            coordinates=q_data.get('coordinates'),
            radius_nm=q_data.get('radius_nm'),
            category=category,
            effective_from=effective_from,
            effective_to=effective_to,
            is_permanent=is_permanent,
            schedule_text=schedule_text,
            raw_text=text,
            message=message,
            source=source,
            parsed_at=datetime.now(),
        )

    @classmethod
    def parse_many(cls, text: str, source: Optional[str] = None) -> List[Notam]:
        """
        Parse multiple NOTAMs from a text block.

        Args:
            text: Text containing multiple NOTAMs
            source: Source identifier

        Returns:
            List of parsed Notam objects
        """
        notams = []

        # Split on NOTAM boundaries
        # Look for patterns like "A1234/24" or "NOTAM" headers
        chunks = cls._split_notams(text)

        for chunk in chunks:
            notam = cls.parse(chunk, source=source)
            if notam:
                notams.append(notam)

        return notams

    @classmethod
    def _split_notams(cls, text: str) -> List[str]:
        """
        Split text into individual NOTAM blocks.

        Handles various formats including:
        - NOTAMs separated by blank lines
        - NOTAMs starting with ID pattern
        - NOTAMs prefixed with airport codes
        """
        # Find all NOTAM ID positions
        id_pattern = re.compile(r'[A-Z]\d{4}/\d{2}', re.MULTILINE)
        matches = list(id_pattern.finditer(text))

        if not matches:
            # No NOTAM IDs found - try splitting on double newlines
            parts = re.split(r'\n\s*\n', text)
            chunks = [p.strip() for p in parts if p.strip() and len(p.strip()) > 20]
            if chunks:
                return chunks
            # Fallback: treat entire text as one NOTAM
            return [text] if text.strip() else []

        # Extract text from each NOTAM ID to the next
        chunks = []
        for i, match in enumerate(matches):
            start = match.start()
            if i + 1 < len(matches):
                end = matches[i + 1].start()
            else:
                end = len(text)
            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)

        return chunks

    @classmethod
    def _parse_notam_id(cls, text: str) -> Tuple[Optional[str], Optional[str], Optional[int], Optional[int]]:
        """Parse NOTAM ID, series, number, and year."""
        match = cls.NOTAM_ID_PATTERN.search(text)
        if match:
            series = match.group(1).upper()
            number = int(match.group(2))
            year = int(match.group(3))
            notam_id = f"{series}{number:04d}/{year:02d}"
            return notam_id, series, number, year
        return None, None, None, None

    @classmethod
    def _parse_q_line(cls, text: str) -> Dict[str, Any]:
        """Parse Q-line and extract fields."""
        result: Dict[str, Any] = {}

        # Try full Q-line pattern
        match = cls.Q_LINE_PATTERN.search(text)
        if match:
            result['fir'] = match.group(1).upper()
            result['q_code'] = f"Q{match.group(2).upper()}"
            result['traffic_type'] = match.group(3).upper()
            result['purpose'] = match.group(4).upper()
            result['scope'] = match.group(5).upper()
            result['lower_fl'] = int(match.group(6))
            result['upper_fl'] = int(match.group(7))

            # Parse coordinates
            coords_str = match.group(8)
            result['coordinates'] = cls._parse_coordinates(coords_str)

            # Parse radius
            if match.group(9):
                result['radius_nm'] = int(match.group(9))

            return result

        # Try simple Q-line pattern
        match = cls.Q_LINE_SIMPLE_PATTERN.search(text)
        if match:
            result['fir'] = match.group(1).upper()
            result['q_code'] = f"Q{match.group(2).upper()}"

        return result

    @classmethod
    def _parse_coordinates(cls, coords_str: str) -> Optional[Tuple[float, float]]:
        """
        Parse NOTAM coordinate string to (lat, lon) tuple.

        Format: DDMMN/S DDDMME/W (e.g., 4901N00225E)
        """
        if not coords_str:
            return None

        # Pattern: DDMMN/S DDDMME/W
        match = re.match(
            r'(\d{2})(\d{2})([NS])(\d{3})(\d{2})([EW])',
            coords_str,
            re.IGNORECASE
        )
        if match:
            lat_deg = int(match.group(1))
            lat_min = int(match.group(2))
            lat_dir = match.group(3).upper()
            lon_deg = int(match.group(4))
            lon_min = int(match.group(5))
            lon_dir = match.group(6).upper()

            lat = lat_deg + lat_min / 60.0
            if lat_dir == 'S':
                lat = -lat

            lon = lon_deg + lon_min / 60.0
            if lon_dir == 'W':
                lon = -lon

            return (lat, lon)

        return None

    @classmethod
    def _parse_location(cls, text: str) -> Optional[str]:
        """Parse A-line location."""
        # Pattern: A) ICAO or A)ICAO
        match = re.search(r'A\)\s*([A-Z]{4})', text, re.IGNORECASE)
        if match:
            return match.group(1).upper()
        return None

    @classmethod
    def _parse_effective_times(cls, text: str) -> Tuple[Optional[datetime], Optional[datetime]]:
        """Parse B-line (from) and C-line (to) times."""
        effective_from = None
        effective_to = None

        # B) line - effective from
        match = re.search(r'B\)\s*(\d{10})', text)
        if match:
            effective_from = cls._parse_notam_datetime(match.group(1))

        # C) line - effective to
        match = re.search(r'C\)\s*(\d{10}|PERM|UFN)', text, re.IGNORECASE)
        if match:
            if match.group(1).upper() in ('PERM', 'UFN'):
                effective_to = None  # Permanent
            else:
                effective_to = cls._parse_notam_datetime(match.group(1))

        return effective_from, effective_to

    @classmethod
    def _parse_notam_datetime(cls, dt_str: str) -> Optional[datetime]:
        """
        Parse NOTAM datetime format: YYMMDDHHMM.

        Args:
            dt_str: 10-digit datetime string

        Returns:
            Parsed datetime or None
        """
        if not dt_str or len(dt_str) != 10:
            return None

        try:
            year = int(dt_str[0:2])
            month = int(dt_str[2:4])
            day = int(dt_str[4:6])
            hour = int(dt_str[6:8])
            minute = int(dt_str[8:10])

            # Assume 20xx for year
            year = 2000 + year

            return datetime(year, month, day, hour, minute)
        except (ValueError, IndexError):
            return None

    @classmethod
    def _is_permanent(cls, text: str, effective_to: Optional[datetime]) -> bool:
        """Check if NOTAM is permanent."""
        if effective_to is None:
            # Check for PERM or UFN indicators
            if re.search(r'\b(PERM|UFN)\b', text, re.IGNORECASE):
                return True
            # Check C) line
            if re.search(r'C\)\s*(PERM|UFN)', text, re.IGNORECASE):
                return True
        return False

    @classmethod
    def _parse_schedule(cls, text: str) -> Optional[str]:
        """Parse D-line schedule text."""
        match = re.search(r'D\)\s*(.+?)(?=\n[A-G]\)|$)', text, re.IGNORECASE | re.DOTALL)
        if match:
            schedule = match.group(1).strip()
            # Clean up the schedule text
            schedule = re.sub(r'\s+', ' ', schedule)
            return schedule if schedule else None
        return None

    @classmethod
    def _parse_message(cls, text: str) -> str:
        """Parse E-line message."""
        # Look for E) line
        match = re.search(r'E\)\s*(.+?)(?=\n[FG]\)|$)', text, re.IGNORECASE | re.DOTALL)
        if match:
            message = match.group(1).strip()
            # Clean up the message
            message = re.sub(r'\s+', ' ', message)
            return message

        # Fallback: try to extract message from text after basic fields
        # This handles abbreviated formats
        lines = text.split('\n')
        for i, line in enumerate(lines):
            if re.match(r'^[A-Z]\d{4}/\d{2}', line):
                # Found NOTAM ID line, message is likely after
                remaining = '\n'.join(lines[i+1:])
                # Remove Q), A), B), C) lines
                remaining = re.sub(r'[QABCD]\)[^\n]*', '', remaining)
                remaining = remaining.strip()
                if remaining:
                    return re.sub(r'\s+', ' ', remaining)

        return ""

    @classmethod
    def _parse_altitude_limits(
        cls,
        text: str,
        q_data: Dict[str, Any]
    ) -> Tuple[Optional[int], Optional[int]]:
        """Parse altitude limits from F/G lines or Q-line."""
        lower_limit = None
        upper_limit = None

        # Try Q-line flight levels first (convert to feet)
        if 'lower_fl' in q_data:
            lower_limit = q_data['lower_fl'] * 100
        if 'upper_fl' in q_data:
            upper_limit = q_data['upper_fl'] * 100

        # F) line - lower limit
        match = re.search(r'F\)\s*(SFC|GND|FL\s*(\d+)|(\d+)\s*(FT|M)?)', text, re.IGNORECASE)
        if match:
            full_match = match.group(1).upper()
            if full_match in ('SFC', 'GND'):
                lower_limit = 0
            elif full_match.startswith('FL'):
                fl_value = match.group(2)
                if fl_value:
                    lower_limit = int(fl_value) * 100
            else:
                value = int(match.group(3))
                unit = (match.group(4) or '').upper()
                if unit == 'M':
                    lower_limit = int(value * 3.28084)
                else:
                    lower_limit = value

        # G) line - upper limit
        match = re.search(r'G\)\s*(UNL|FL\s*(\d+)|(\d+)\s*(FT|M)?)', text, re.IGNORECASE)
        if match:
            full_match = match.group(1).upper()
            if full_match == 'UNL':
                upper_limit = 99999  # Unlimited
            elif full_match.startswith('FL'):
                fl_value = match.group(2)
                if fl_value:
                    upper_limit = int(fl_value) * 100
            else:
                value = int(match.group(3))
                unit = (match.group(4) or '').upper()
                if unit == 'M':
                    upper_limit = int(value * 3.28084)
                else:
                    upper_limit = value

        return lower_limit, upper_limit

    @classmethod
    def _determine_category(cls, q_code: Optional[str]) -> Optional[NotamCategory]:
        """Determine NOTAM category from Q-code."""
        if not q_code:
            return None

        # Remove 'Q' prefix if present
        code = q_code.upper()
        if code.startswith('Q'):
            code = code[1:]

        # Check first 2 letters
        prefix = code[:2] if len(code) >= 2 else code
        return cls.Q_CODE_CATEGORIES.get(prefix, NotamCategory.OTHER)

    @classmethod
    def parse_q_code(cls, q_code: str) -> Dict[str, Any]:
        """
        Decode ICAO Q-code into category and meaning.

        Args:
            q_code: 5-letter Q-code (e.g., "QMRLC")

        Returns:
            Dictionary with decoded information
        """
        if not q_code:
            return {}

        code = q_code.upper()
        if code.startswith('Q'):
            code = code[1:]

        result = {
            'raw': q_code,
            'code': code,
        }

        if len(code) >= 2:
            prefix = code[:2]
            result['category'] = cls.Q_CODE_CATEGORIES.get(prefix, NotamCategory.OTHER)
            result['prefix'] = prefix

        # Common suffixes
        if len(code) >= 3:
            suffix = code[2:]
            result['suffix'] = suffix

            # Decode common suffixes
            suffix_meanings = {
                'LC': 'closed',
                'LH': 'hours changed',
                'LA': 'activated',
                'LT': 'limited',
                'AS': 'unserviceable',
                'AU': 'unavailable',
                'AH': 'hours of service',
                'CA': 'activated',
                'CH': 'changed',
                'CN': 'cancelled',
                'CR': 'created',
                'HW': 'work in progress',
                'XX': 'other',
            }
            result['suffix_meaning'] = suffix_meanings.get(suffix[:2], 'unknown')

        return result
