"""NOTAM data model."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, Set, Tuple, List, Any, Dict, TYPE_CHECKING

if TYPE_CHECKING:
    from euro_aip.briefing.models.document_reference import DocumentReference


class NotamCategory(Enum):
    """
    ICAO NOTAM categories based on Q-code subject first letter.

    These are standard ICAO categories matching q_codes.json.
    The first letter of the 2-letter subject code determines the category.

    Example: QMRLC → subject "MR" → first letter "M" → ATM_MOVEMENT
    """
    ATM_AIRSPACE = "A"          # ATM Airspace Organization (FIR, TMA, CTR, ATS routes)
    CNS_COMMUNICATIONS = "C"    # CNS Communications and Surveillance (Radar, ADS-B)
    AGA_FACILITIES = "F"        # AGA Facilities and Services (Aerodrome, fuel, helicopter)
    CNS_GNSS = "G"              # CNS GNSS Services
    CNS_ILS = "I"               # CNS ILS/MLS (ILS, localizer, glide path)
    AGA_LIGHTING = "L"          # AGA Lighting (ALS, PAPI, VASIS, runway lights)
    AGA_MOVEMENT = "M"          # AGA Movement Area (Runway, taxiway, apron)
    NAVIGATION = "N"            # Navigation Facilities (VOR, DME, NDB, TACAN)
    OTHER_INFO = "O"            # Other Information (Obstacles, AIS)
    ATM_PROCEDURES = "P"        # ATM Procedures (SID, STAR, approaches)
    AIRSPACE_RESTRICTIONS = "R" # Airspace Restrictions (D/P/R areas, TRA)
    ATM_SERVICES = "S"          # ATM Services (ATIS, ACC, TWR)

    @classmethod
    def from_q_code(cls, q_code: str) -> Optional['NotamCategory']:
        """
        Create category from Q-code.

        Args:
            q_code: 5-letter Q-code (e.g., "QMRLC")

        Returns:
            NotamCategory based on subject first letter, or None if invalid
        """
        if not q_code or len(q_code) < 3:
            return None
        subject_first = q_code[1].upper()
        try:
            return cls(subject_first)
        except ValueError:
            return None

    @classmethod
    def from_subject(cls, subject: str) -> Optional['NotamCategory']:
        """
        Create category from Q-code subject.

        Args:
            subject: 2-letter subject code (e.g., "MR")

        Returns:
            NotamCategory based on first letter, or None if invalid
        """
        if not subject:
            return None
        try:
            return cls(subject[0].upper())
        except ValueError:
            return None


@dataclass
class Notam:
    """
    NOTAM (Notice to Airmen) data model.

    Represents a parsed NOTAM with all extracted fields. Supports both
    full ICAO format NOTAMs and abbreviated formats found in briefing documents.

    Attributes:
        id: Unique NOTAM identifier (e.g., "A1234/24")
        location: Primary ICAO code from A) line
        raw_text: Full original NOTAM text
        message: E) line content - main message

    Example:
        notam = Notam(
            id="A1234/24",
            location="LFPG",
            raw_text="A1234/24 NOTAMN...",
            message="RWY 09L/27R CLSD DUE TO MAINTENANCE"
        )
    """

    # Identity - required fields
    id: str
    location: str
    raw_text: str = ""
    message: str = ""

    # Identity - parsed components
    series: Optional[str] = None          # A, B, C, etc.
    number: Optional[int] = None
    year: Optional[int] = None

    # Location details
    fir: Optional[str] = None             # FIR code from Q-line
    affected_locations: List[str] = field(default_factory=list)

    # Q-line decoded fields
    q_code: Optional[str] = None          # e.g., "QMXLC"
    traffic_type: Optional[str] = None    # I, V, IV
    purpose: Optional[str] = None         # N, B, O, M, K
    scope: Optional[str] = None           # A, E, W, AE, AW
    lower_limit: Optional[int] = None     # In feet
    upper_limit: Optional[int] = None     # In feet
    coordinates: Optional[Tuple[float, float]] = None  # (lat, lon)
    radius_nm: Optional[float] = None

    # Category (derived from Q-code)
    category: Optional[NotamCategory] = None
    subcategory: Optional[str] = None

    # Schedule
    effective_from: Optional[datetime] = None
    effective_to: Optional[datetime] = None
    is_permanent: bool = False
    schedule_text: Optional[str] = None   # e.g., "SR-SS"

    # Parsing metadata
    source: Optional[str] = None
    parsed_at: datetime = field(default_factory=datetime.now)
    parse_confidence: float = 1.0         # 0-1 confidence score

    # Custom categorization (populated by CategorizationPipeline)
    primary_category: Optional[str] = None
    custom_categories: Set[str] = field(default_factory=set)
    custom_tags: Set[str] = field(default_factory=set)

    # Document references (AIP supplements, etc.)
    document_references: List[Any] = field(default_factory=list)  # List[DocumentReference]

    def to_dict(self) -> dict:
        """
        Serialize to dictionary for JSON export.

        Returns:
            Dictionary representation suitable for JSON serialization.
        """
        # Parse Q-code info if available (lazy import to avoid circular dependency)
        q_code_info: Optional[Dict] = None
        if self.q_code:
            from euro_aip.briefing.categorization.q_code import parse_q_code
            q_code_info = parse_q_code(self.q_code).to_dict()

        return {
            'id': self.id,
            'location': self.location,
            'raw_text': self.raw_text,
            'message': self.message,
            'series': self.series,
            'number': self.number,
            'year': self.year,
            'fir': self.fir,
            'affected_locations': self.affected_locations,
            'q_code': self.q_code,
            'q_code_info': q_code_info,
            'traffic_type': self.traffic_type,
            'purpose': self.purpose,
            'scope': self.scope,
            'lower_limit': self.lower_limit,
            'upper_limit': self.upper_limit,
            'coordinates': list(self.coordinates) if self.coordinates else None,
            'radius_nm': self.radius_nm,
            'category': self.category.value if self.category else None,
            'subcategory': self.subcategory,
            'effective_from': self.effective_from.isoformat() if self.effective_from else None,
            'effective_to': self.effective_to.isoformat() if self.effective_to else None,
            'is_permanent': self.is_permanent,
            'schedule_text': self.schedule_text,
            'source': self.source,
            'parsed_at': self.parsed_at.isoformat(),
            'parse_confidence': self.parse_confidence,
            'primary_category': self.primary_category,
            'custom_categories': list(self.custom_categories),
            'custom_tags': list(self.custom_tags),
            'document_references': [ref.to_dict() for ref in self.document_references],
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'Notam':
        """
        Create Notam from dictionary.

        Args:
            data: Dictionary with NOTAM fields

        Returns:
            Notam instance
        """
        # Handle datetime fields
        effective_from = None
        if data.get('effective_from'):
            effective_from = datetime.fromisoformat(data['effective_from'])

        effective_to = None
        if data.get('effective_to'):
            effective_to = datetime.fromisoformat(data['effective_to'])

        parsed_at = datetime.now()
        if data.get('parsed_at'):
            parsed_at = datetime.fromisoformat(data['parsed_at'])

        # Handle category enum
        category = None
        if data.get('category'):
            try:
                category = NotamCategory(data['category'])
            except ValueError:
                pass

        # Handle coordinates tuple
        coordinates = None
        if data.get('coordinates'):
            coordinates = tuple(data['coordinates'])

        return cls(
            id=data['id'],
            location=data['location'],
            raw_text=data.get('raw_text', ''),
            message=data.get('message', ''),
            series=data.get('series'),
            number=data.get('number'),
            year=data.get('year'),
            fir=data.get('fir'),
            affected_locations=data.get('affected_locations', []),
            q_code=data.get('q_code'),
            traffic_type=data.get('traffic_type'),
            purpose=data.get('purpose'),
            scope=data.get('scope'),
            lower_limit=data.get('lower_limit'),
            upper_limit=data.get('upper_limit'),
            coordinates=coordinates,
            radius_nm=data.get('radius_nm'),
            category=category,
            subcategory=data.get('subcategory'),
            effective_from=effective_from,
            effective_to=effective_to,
            is_permanent=data.get('is_permanent', False),
            schedule_text=data.get('schedule_text'),
            source=data.get('source'),
            parsed_at=parsed_at,
            parse_confidence=data.get('parse_confidence', 1.0),
            primary_category=data.get('primary_category'),
            custom_categories=set(data.get('custom_categories', [])),
            custom_tags=set(data.get('custom_tags', [])),
            document_references=cls._parse_document_references(data.get('document_references', [])),
        )

    @staticmethod
    def _parse_document_references(refs_data: List[dict]) -> List[Any]:
        """Parse document references from dictionary data."""
        from euro_aip.briefing.models.document_reference import DocumentReference
        return [DocumentReference.from_dict(ref) for ref in refs_data]

    def __repr__(self) -> str:
        return f"Notam(id={self.id!r}, location={self.location!r})"

    def __str__(self) -> str:
        return f"{self.id} ({self.location}): {self.message[:50]}..." if len(self.message) > 50 else f"{self.id} ({self.location}): {self.message}"
