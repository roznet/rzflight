"""Q-code based NOTAM categorizer using ICAO standard structure.

Q-code structure:
- Q (prefix)
- 2 letters: Subject (what is affected)
- 2 letters: Condition (what happened to it)

Example: QMRLC = Q + MR (Runway) + LC (Closed)

Special codes:
- QKKKK: Checklist of all currently valid NOTAMs
- XX: Situation too unique for standard code, refer to Item E text
"""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional

from euro_aip.briefing.categorization.base import NotamCategorizer, CategorizationResult
from euro_aip.briefing.models.notam import Notam


# Load Q-codes data at module level
_Q_CODES_PATH = Path(__file__).parent.parent.parent.parent / "data" / "q_codes.json"
_Q_CODES_DATA: Optional[Dict] = None


def _load_q_codes() -> Dict:
    """Load Q-codes data from JSON file."""
    global _Q_CODES_DATA
    if _Q_CODES_DATA is None:
        if _Q_CODES_PATH.exists():
            with open(_Q_CODES_PATH, 'r') as f:
                _Q_CODES_DATA = json.load(f)
        else:
            # Fallback if file not found
            _Q_CODES_DATA = {"subjects": {}, "conditions": {}}
    return _Q_CODES_DATA


@dataclass
class QCodeInfo:
    """Parsed Q-code information."""

    # The raw Q-code (e.g., "QMRLC")
    q_code: str

    # Subject (2-letter code, e.g., "MR")
    subject_code: str
    subject_meaning: str  # e.g., "Runway"
    subject_phrase: str   # e.g., "rwy"
    subject_category: str # e.g., "AGA Movement Area"

    # Condition (2-letter code, e.g., "LC")
    condition_code: str
    condition_meaning: str  # e.g., "Closed"
    condition_phrase: str   # e.g., "clsd"
    condition_category: str # e.g., "Limitations"

    # Derived
    is_checklist: bool = False  # True if QKKKK
    is_plain_language: bool = False  # True if XX condition (refer to Item E)

    @property
    def display_text(self) -> str:
        """Human-readable display: 'Runway: Closed'"""
        return f"{self.subject_meaning}: {self.condition_meaning}"

    @property
    def short_text(self) -> str:
        """Short display using phrases: 'RWY CLSD'"""
        return f"{self.subject_phrase.upper()} {self.condition_phrase.upper()}"

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "q_code": self.q_code,
            "subject_code": self.subject_code,
            "subject_meaning": self.subject_meaning,
            "subject_phrase": self.subject_phrase,
            "subject_category": self.subject_category,
            "condition_code": self.condition_code,
            "condition_meaning": self.condition_meaning,
            "condition_phrase": self.condition_phrase,
            "condition_category": self.condition_category,
            "display_text": self.display_text,
            "short_text": self.short_text,
            "is_checklist": self.is_checklist,
            "is_plain_language": self.is_plain_language,
        }


def parse_q_code(q_code: str) -> QCodeInfo:
    """
    Parse a Q-code into its components with full metadata.

    Args:
        q_code: 5-letter Q-code (e.g., "QMRLC")

    Returns:
        QCodeInfo with all parsed fields
    """
    q_code = q_code.upper().strip()

    # Ensure Q prefix
    if not q_code.startswith('Q'):
        q_code = 'Q' + q_code

    data = _load_q_codes()

    # Handle special checklist code
    if q_code == "QKKKK":
        kk_info = data["subjects"].get("KK", {})
        return QCodeInfo(
            q_code=q_code,
            subject_code="KK",
            subject_meaning=kk_info.get("meaning", "Checklist"),
            subject_phrase=kk_info.get("phrase", "checklist"),
            subject_category=kk_info.get("cat", "System"),
            condition_code="KK",
            condition_meaning="All currently valid NOTAMs",
            condition_phrase="all valid",
            condition_category="System",
            is_checklist=True,
        )

    # Need at least 5 characters: Q + 2 subject + 2 condition
    if len(q_code) < 5:
        return QCodeInfo(
            q_code=q_code,
            subject_code="",
            subject_meaning="Unknown",
            subject_phrase="unknown",
            subject_category="Unknown",
            condition_code="",
            condition_meaning="Unknown",
            condition_phrase="unknown",
            condition_category="Unknown",
        )

    subject_code = q_code[1:3]
    condition_code = q_code[3:5]

    # Look up subject
    subject_info = data["subjects"].get(subject_code, {})
    subject_meaning = subject_info.get("meaning", f"Unknown ({subject_code})")
    subject_phrase = subject_info.get("phrase", subject_code.lower())
    subject_category = subject_info.get("cat", "Unknown")

    # Look up condition
    condition_info = data["conditions"].get(condition_code, {})
    condition_meaning = condition_info.get("meaning", f"Unknown ({condition_code})")
    condition_phrase = condition_info.get("phrase", condition_code.lower())
    condition_category = condition_info.get("cat", "Unknown")

    # Check for plain language (XX)
    is_plain_language = (subject_code == "XX" or condition_code == "XX")

    return QCodeInfo(
        q_code=q_code,
        subject_code=subject_code,
        subject_meaning=subject_meaning,
        subject_phrase=subject_phrase,
        subject_category=subject_category,
        condition_code=condition_code,
        condition_meaning=condition_meaning,
        condition_phrase=condition_phrase,
        condition_category=condition_category,
        is_plain_language=is_plain_language,
    )


def get_q_code_meaning(q_code: str) -> tuple[str, str]:
    """
    Parse Q-code into subject and condition descriptions.

    Args:
        q_code: 5-letter Q-code (e.g., "QMRLC")

    Returns:
        Tuple of (subject_meaning, condition_meaning)
    """
    info = parse_q_code(q_code)
    return (info.subject_meaning, info.condition_meaning)


def get_q_code_display(q_code: str) -> str:
    """
    Get a human-readable display string for a Q-code.

    Args:
        q_code: 5-letter Q-code (e.g., "QMRLC")

    Returns:
        Human-readable string like "Runway: Closed"
    """
    info = parse_q_code(q_code)
    return info.display_text


# Map subject categories to our internal categorization
SUBJECT_CAT_TO_CATEGORY: Dict[str, str] = {
    "ATM Airspace Organization": "airspace",
    "CNS Communications and Surveillance": "communication",
    "AGA Facilities and Services": "services",
    "CNS ILS/MLS": "navaid",
    "AGA Lighting": "lighting",
    "AGA Movement Area": "movement_area",
    "Navigation Facilities": "navaid",
    "Other Information": "other",
    "ATM Procedures": "procedure",
    "Airspace Restrictions": "airspace",
    "ATM Services": "services",
    "Warnings": "warning",
    "System": "system",
    "Unknown": "other",
}

# More specific subject mappings for primary category
SUBJECT_CODE_CATEGORY: Dict[str, str] = {
    "MR": "runway",
    "MT": "runway",
    "MX": "taxiway",
    "MN": "apron",
    "IC": "navaid",
    "ID": "navaid",
    "IG": "navaid",
    "IL": "navaid",
    "IS": "navaid",
    "IT": "navaid",
    "IU": "navaid",
    "NV": "navaid",
    "NB": "navaid",
    "OB": "obstacle",
    "RD": "airspace",
    "RR": "airspace",
    "RT": "airspace",
    "PA": "procedure",
    "PD": "procedure",
    "PI": "procedure",
    "WA": "warning",
    "WG": "warning",
    "WM": "warning",
    "WP": "warning",
    "WU": "warning",
    "FH": "heliport",
    "FP": "heliport",
    "FU": "services",
    "ST": "services",
}

# Condition codes that indicate status
CONDITION_TAGS: Dict[str, set] = {
    "AC": {"maintenance"},
    "AD": {"available", "daylight"},
    "AH": {"hours_changed"},
    "AK": {"operational"},
    "AO": {"operational"},
    "AS": {"unserviceable"},
    "AU": {"unavailable"},
    "AW": {"withdrawn"},
    "CA": {"activated", "active"},
    "CH": {"changed"},
    "CL": {"closed"},
    "CN": {"cancelled"},
    "CP": {"reduced_power"},
    "CT": {"test"},
    "HA": {"braking"},
    "HB": {"friction"},
    "HW": {"work_in_progress"},
    "HX": {"birds"},
    "LC": {"closed"},
    "LD": {"unsafe"},
    "XX": set(),  # Plain language - no specific tags
}


class QCodeCategorizer(NotamCategorizer):
    """
    Categorize NOTAMs based on ICAO Q-code structure.

    Q-code format: Q + Subject(2) + Condition(2)

    Examples:
        QMRLC = Runway (MR) + Closed (LC)
        QNVAS = VOR (NV) + Unserviceable (AS)
        QKKKK = Special checklist code
    """

    @property
    def name(self) -> str:
        return "q_code"

    def categorize(self, notam: Notam) -> CategorizationResult:
        """
        Categorize NOTAM based on Q-code.

        Returns high confidence for valid Q-codes with known mappings,
        lower confidence for unknown codes or plain language.
        """
        result = CategorizationResult(source=self.name)

        if not notam.q_code:
            result.confidence = 0.0
            return result

        # Parse the Q-code
        info = parse_q_code(notam.q_code)

        # Handle checklist
        if info.is_checklist:
            result.primary_category = "checklist"
            result.categories.add("checklist")
            result.confidence = 1.0
            return result

        # Handle plain language (XX) - can't auto-categorize well
        if info.is_plain_language:
            result.primary_category = "other"
            result.categories.add("other")
            result.confidence = 0.3  # Low confidence, user should read Item E
            return result

        # Determine category from subject code
        if info.subject_code in SUBJECT_CODE_CATEGORY:
            # Specific subject mapping takes priority
            category = SUBJECT_CODE_CATEGORY[info.subject_code]
        elif info.subject_category in SUBJECT_CAT_TO_CATEGORY:
            # Fall back to category from JSON
            category = SUBJECT_CAT_TO_CATEGORY[info.subject_category]
        else:
            category = "other"

        result.primary_category = category
        result.categories.add(category)

        # Add subject phrase as tag (e.g., "rwy", "vor", "ils")
        if info.subject_phrase:
            result.tags.add(info.subject_phrase.lower().replace(" ", "_"))

        # Add condition tags
        if info.condition_code in CONDITION_TAGS:
            result.tags.update(CONDITION_TAGS[info.condition_code])

        # Set confidence based on whether we found valid mappings
        if category != "other" and info.condition_code in CONDITION_TAGS:
            result.confidence = 1.0
        elif category != "other":
            result.confidence = 0.9
        else:
            result.confidence = 0.5

        return result

    def get_display_text(self, q_code: str) -> str:
        """
        Get human-readable display text for a Q-code.

        Args:
            q_code: 5-letter Q-code

        Returns:
            Display string like "Runway: Closed"
        """
        return get_q_code_display(q_code)

    def parse(self, q_code: str) -> QCodeInfo:
        """
        Parse a Q-code into full metadata.

        Args:
            q_code: 5-letter Q-code

        Returns:
            QCodeInfo with all parsed fields
        """
        return parse_q_code(q_code)
