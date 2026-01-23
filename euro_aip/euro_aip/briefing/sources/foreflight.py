"""
ForeFlight PDF briefing source.

Parses ForeFlight briefing PDFs to extract NOTAMs, route information,
and other briefing data.
"""

import re
import logging
from pathlib import Path
from typing import Optional, List, Union, Dict, Any
from datetime import datetime
from io import BytesIO

from euro_aip.briefing.models.briefing import Briefing
from euro_aip.briefing.models.notam import Notam
from euro_aip.briefing.models.route import Route, RoutePoint
from euro_aip.briefing.parsers.notam_parser import NotamParser

logger = logging.getLogger(__name__)


class ForeFlightSource:
    """
    Parse ForeFlight briefing PDFs.

    ForeFlight briefings contain:
    - Route summary
    - METARs/TAFs for departure, destination, alternates
    - NOTAMs organized by location
    - TFRs and other advisories

    Example:
        source = ForeFlightSource(cache_dir="./cache")
        briefing = source.parse("path/to/foreflight_briefing.pdf")

        # Access NOTAMs
        for notam in briefing.notams:
            print(notam.id, notam.message)

        # Query NOTAMs
        runway_notams = briefing.notams_query.runway_related().all()
    """

    def __init__(self, cache_dir: Optional[str] = None):
        """
        Initialize ForeFlight source.

        Args:
            cache_dir: Optional cache directory for storing parsed briefings
        """
        self.cache_dir = Path(cache_dir) if cache_dir else None
        if self.cache_dir:
            self.cache_dir.mkdir(parents=True, exist_ok=True)

    def parse(self, pdf_path: Union[str, Path, bytes]) -> Briefing:
        """
        Parse a ForeFlight briefing PDF.

        Args:
            pdf_path: Path to PDF file or raw PDF bytes

        Returns:
            Briefing object with extracted data
        """
        # Extract text from PDF
        text = self._extract_text(pdf_path)

        # Extract route information
        route = self._extract_route(text)

        # Extract NOTAMs
        notams = self._extract_notams(text)

        # Create briefing
        briefing = Briefing(
            source="foreflight",
            route=route,
            notams=notams,
            created_at=datetime.now(),
            raw_data={'text_length': len(text)},
        )

        return briefing

    def parse_text(self, text: str) -> Briefing:
        """
        Parse briefing from pre-extracted text.

        Useful when text has already been extracted from PDF.

        Args:
            text: Extracted text from briefing

        Returns:
            Briefing object with extracted data
        """
        route = self._extract_route(text)
        notams = self._extract_notams(text)

        return Briefing(
            source="foreflight",
            route=route,
            notams=notams,
            created_at=datetime.now(),
        )

    def _extract_text(self, pdf_path: Union[str, Path, bytes]) -> str:
        """
        Extract text from PDF using pdfplumber.

        Handles two-column layouts by extracting columns separately
        to avoid interleaved text.

        Args:
            pdf_path: Path to PDF or raw bytes

        Returns:
            Extracted text
        """
        import pdfplumber

        # Handle bytes input
        if isinstance(pdf_path, bytes):
            pdf_file = BytesIO(pdf_path)
        else:
            pdf_path = Path(pdf_path)
            if not pdf_path.exists():
                raise FileNotFoundError(f"PDF file not found: {pdf_path}")
            pdf_file = pdf_path

        text_parts = []
        with pdfplumber.open(pdf_file) as pdf:
            for page in pdf.pages:
                page_text = self._extract_page_text(page)
                if page_text:
                    text_parts.append(page_text)

        return '\n\n'.join(text_parts)

    def _extract_page_text(self, page) -> str:
        """
        Extract text from a single page, handling multi-column layouts.

        ForeFlight briefings often use two-column layouts in landscape mode.
        This method detects such layouts and extracts columns separately.

        Args:
            page: pdfplumber page object

        Returns:
            Extracted text with columns properly ordered
        """
        width = page.width
        height = page.height

        # Check if landscape orientation (likely two-column NOTAM pages)
        if width > height:
            # Extract left and right columns separately
            left_bbox = (0, 0, width / 2, height)
            right_bbox = (width / 2, 0, width, height)

            left_page = page.crop(left_bbox)
            right_page = page.crop(right_bbox)

            left_text = left_page.extract_text() or ''
            right_text = right_page.extract_text() or ''

            # Combine columns - left first, then right
            if left_text and right_text:
                return left_text + '\n\n' + right_text
            return left_text or right_text

        # Portrait mode - extract normally
        return page.extract_text() or ''

    def _extract_route(self, text: str) -> Optional[Route]:
        """
        Extract route information from briefing text.

        Looks for patterns like:
        - "Departure LFPG" and "Destination EGLL"
        - "LFPG to EGLL"
        - Route section headers
        """
        departure = None
        destination = None

        # First, try to find explicit Departure and Destination labels
        # These are the most reliable indicators in ForeFlight briefings
        dep_match = re.search(r'\bDeparture\s+([A-Z]{4})\b', text, re.IGNORECASE)
        dest_match = re.search(r'\bDestination\s+([A-Z]{4})\b', text, re.IGNORECASE)

        if dep_match and dest_match:
            departure = dep_match.group(1).upper()
            destination = dest_match.group(1).upper()
        else:
            # Try other common patterns (in order of reliability)
            patterns = [
                # "From: LFPG To: EGLL"
                r'From:?\s*([A-Z]{4}).*?To:?\s*([A-Z]{4})',
                # Route header "LFPG EGLL"
                r'^Route:?\s*([A-Z]{4})\s+([A-Z]{4})',
                # "LFPG to EGLL" or "LFPG - EGLL" (less reliable, try last)
                r'([A-Z]{4})\s*(?:to|->|→)\s*([A-Z]{4})',
            ]

            for pattern in patterns:
                match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE | re.DOTALL)
                if match:
                    departure = match.group(1).upper()
                    destination = match.group(2).upper()
                    break

        if not departure or not destination:
            # Try to find any ICAO codes mentioned early in document
            icao_codes = re.findall(r'\b([A-Z]{4})\b', text[:2000])
            # Filter to likely airport codes (not common words)
            airport_codes = [
                code for code in icao_codes
                if code[0] in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
                and code not in ('NOTAM', 'METAR', 'SPECI', 'TEMPO', 'BECMG', 'NOSIG', 'CAVOK')
            ]
            if len(airport_codes) >= 2:
                departure = airport_codes[0]
                destination = airport_codes[1]

        if not departure:
            return None

        route = Route(
            departure=departure,
            destination=destination or departure,
        )

        # Try to extract alternates
        alternates = self._extract_alternates(text)
        if alternates:
            route.alternates = alternates

        # Try to extract waypoints
        waypoints = self._extract_waypoints(text)
        if waypoints:
            route.waypoints = waypoints

        return route

    def _extract_alternates(self, text: str) -> List[str]:
        """Extract alternate airports from briefing."""
        alternates = []

        # Look for "Alternate:" or "ALT:" patterns
        patterns = [
            r'Alternate[s]?:?\s*([A-Z]{4}(?:\s*,?\s*[A-Z]{4})*)',
            r'ALT:?\s*([A-Z]{4}(?:\s*,?\s*[A-Z]{4})*)',
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                codes = re.findall(r'[A-Z]{4}', match.group(1))
                alternates.extend(codes)

        return list(dict.fromkeys(alternates))  # Remove duplicates

    def _extract_waypoints(self, text: str) -> List[str]:
        """Extract waypoints from route section."""
        waypoints = []

        # Look for route string like "DCT POGOL DCT VESAN DCT"
        route_match = re.search(
            r'Route:?\s*(.+?)(?:\n\n|\n[A-Z]{4}:|\nNOTAM)',
            text,
            re.IGNORECASE | re.DOTALL
        )

        if route_match:
            route_str = route_match.group(1)
            # Extract waypoint names (5-letter fixes, airways, etc.)
            waypoint_pattern = r'\b([A-Z]{2,5})\b'
            candidates = re.findall(waypoint_pattern, route_str)

            # Filter out common non-waypoint words
            excluded = {
                'DCT', 'VIA', 'THEN', 'TO', 'FROM', 'AND', 'OR',
                'IFR', 'VFR', 'FL', 'ALT', 'ROUTE'
            }
            waypoints = [wp for wp in candidates if wp not in excluded]

        return waypoints

    def _extract_notams(self, text: str) -> List[Notam]:
        """
        Extract NOTAMs from briefing text.

        Handles various ForeFlight NOTAM section formats.
        """
        notams = []

        # Find NOTAM sections
        notam_sections = self._find_notam_sections(text)

        for section_text, location in notam_sections:
            # Parse NOTAMs from this section
            section_notams = self._parse_notam_section(section_text, location)
            notams.extend(section_notams)

        # Deduplicate by NOTAM ID
        seen_ids = set()
        unique_notams = []
        for notam in notams:
            if notam.id not in seen_ids:
                seen_ids.add(notam.id)
                unique_notams.append(notam)

        return unique_notams

    def _find_notam_sections(self, text: str) -> List[tuple]:
        """
        Find NOTAM sections in the briefing text.

        Returns:
            List of (section_text, location) tuples
        """
        sections = []

        # Pattern 1: "LFPG NOTAMs" or "NOTAMs for LFPG"
        pattern1 = re.compile(
            r'(?:([A-Z]{4})\s+NOTAMs?|NOTAMs?\s+(?:for\s+)?([A-Z]{4}))\s*[:\n](.+?)(?=(?:[A-Z]{4}\s+NOTAMs?|NOTAMs?\s+(?:for\s+)?[A-Z]{4}|\Z))',
            re.IGNORECASE | re.DOTALL
        )

        for match in pattern1.finditer(text):
            location = (match.group(1) or match.group(2)).upper()
            section_text = match.group(3)
            sections.append((section_text, location))

        # Pattern 2: Section headers with ICAO
        pattern2 = re.compile(
            r'^\s*([A-Z]{4})\s*$\s*\n((?:(?![A-Z]{4}\s*$).)+)',
            re.MULTILINE | re.DOTALL
        )

        for match in pattern2.finditer(text):
            location = match.group(1).upper()
            section_text = match.group(2)
            # Only add if contains NOTAM-like content
            if re.search(r'[A-Z]\d{4}/\d{2}|NOTAM', section_text, re.IGNORECASE):
                sections.append((section_text, location))

        # Pattern 3: FDC NOTAMs section
        fdc_match = re.search(
            r'FDC\s+NOTAMs?\s*[:\n](.+?)(?=\n\n[A-Z]|\Z)',
            text,
            re.IGNORECASE | re.DOTALL
        )
        if fdc_match:
            sections.append((fdc_match.group(1), 'FDC'))

        # If no sections found, try to find NOTAMs in the entire text
        if not sections:
            # Look for NOTAM content anywhere
            if re.search(r'[A-Z]\d{4}/\d{2}', text):
                sections.append((text, 'UNKNOWN'))

        return sections

    def _parse_notam_section(self, section_text: str, location: str) -> List[Notam]:
        """
        Parse NOTAMs from a section of text.

        Args:
            section_text: Text containing NOTAMs
            location: Default location for NOTAMs in this section

        Returns:
            List of parsed Notam objects
        """
        notams = []

        # Split section into individual NOTAMs
        notam_chunks = self._split_notam_section(section_text)

        for chunk in notam_chunks:
            notam = NotamParser.parse(chunk, source='foreflight')
            if notam:
                # Use section location if NOTAM location is unknown
                if notam.location == 'ZZZZ' and location != 'UNKNOWN':
                    notam.location = location
                    if location not in notam.affected_locations:
                        notam.affected_locations.append(location)
                notams.append(notam)

        return notams

    def _split_notam_section(self, section_text: str) -> List[str]:
        """
        Split a NOTAM section into individual NOTAM texts.

        Handles various delimiter formats used in ForeFlight.
        Only splits on NOTAM IDs that start a new NOTAM (followed by NOTAM[NRC]),
        not on IDs that appear as references (after NOTAMR/NOTAMC).
        """
        # Pattern for NOTAM ID at start of a new NOTAM
        # Must be followed by NOTAM[NRC] (with possible space)
        # This avoids splitting on referenced NOTAMs like "NOTAMR E1234/25"
        start_pattern = re.compile(r'([A-Z]\d{4}/\d{2})\s*NOTAM[NRC]')
        matches = list(start_pattern.finditer(section_text))

        if matches:
            # Extract text from each NOTAM start to the next
            chunks = []
            for i, match in enumerate(matches):
                start = match.start()
                if i + 1 < len(matches):
                    end = matches[i + 1].start()
                else:
                    end = len(section_text)
                chunk = section_text[start:end].strip()
                if chunk:
                    chunks.append(chunk)
            if chunks:
                return chunks

        # Fallback: try the simple ID pattern if no NOTAM[NRC] markers found
        # (some briefings may have truncated NOTAM headers)
        id_pattern = re.compile(r'[A-Z]\d{4}/\d{2}')
        id_matches = list(id_pattern.finditer(section_text))

        if id_matches:
            # Filter out IDs that appear after NOTAMR/NOTAMC (references)
            valid_starts = []
            for match in id_matches:
                # Check what comes before this ID
                prefix_start = max(0, match.start() - 10)
                prefix = section_text[prefix_start:match.start()]
                # Skip if this ID follows NOTAMR or NOTAMC
                if not re.search(r'NOTAM[RC]\s*$', prefix):
                    valid_starts.append(match)

            if valid_starts:
                chunks = []
                for i, match in enumerate(valid_starts):
                    start = match.start()
                    if i + 1 < len(valid_starts):
                        end = valid_starts[i + 1].start()
                    else:
                        end = len(section_text)
                    chunk = section_text[start:end].strip()
                    if chunk:
                        chunks.append(chunk)
                if chunks:
                    return chunks

        # Fallback: try splitting on double newline
        chunks = []
        parts = re.split(r'\n\s*\n', section_text)
        for part in parts:
            part = part.strip()
            if part and len(part) > 20:
                chunks.append(part)

        # If still nothing, return whole section
        if not chunks and section_text.strip():
            chunks = [section_text.strip()]

        return chunks

    def get_supported_formats(self) -> List[str]:
        """Get list of supported input formats."""
        return ['pdf']

    def save_briefing(self, briefing: Briefing, filename: Optional[str] = None) -> Path:
        """
        Save parsed briefing to cache directory.

        Args:
            briefing: Briefing to save
            filename: Optional filename (defaults to briefing ID)

        Returns:
            Path to saved file
        """
        if not self.cache_dir:
            raise ValueError("Cache directory not configured")

        if not filename:
            filename = f"briefing_{briefing.id}.json"

        path = self.cache_dir / "briefings" / filename
        briefing.save(path)
        return path
