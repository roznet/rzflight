"""
Custom and immigration field interpreter.

This interpreter extracts structured information about custom and immigration
requirements from standardized AIP fields.
"""

import re
import logging
from typing import Dict, List, Any, Optional
from .base import BaseInterpreter, InterpretationResult

logger = logging.getLogger(__name__)

class CustomInterpreter(BaseInterpreter):
    """
    Interprets custom and immigration fields for notification periods.
    
    Processes standardized field 302 (Custom and Immigration) to extract:
    - Weekday notification periods
    - Weekend notification periods
    - Advance notice requirements
    - Custom availability
    """
    
    def get_standard_field_id(self) -> int:
        """Return the standard field ID for custom and immigration (302)."""
        return 302
    
    def get_structured_fields(self) -> List[str]:
        """Return list of structured fields this interpreter calculates."""
        return [
            'weekday_pn',           # Weekday prior notification period
            'weekend_pn',           # Weekend prior notification period
            'advance_notice_required',  # Whether advance notice is required
            'custom_available',     # Whether custom services are available
            'immigration_available' # Whether immigration services are available
        ]
    
    def interpret_field_value(self, field_value: str, airport: Optional['Airport'] = None) -> Optional[Dict[str, Any]]:
        """
        Interpret a custom field value into structured data.
        
        Args:
            field_value: The raw field value to interpret
            airport: Optional airport object for additional context
            
        Returns:
            Dictionary with structured custom information, or None if interpretation failed
        """
        return self._interpret_custom_field(field_value, airport.ident if airport else None)
    
    def _interpret_custom_field(self, field_value: str, airport_icao: str) -> Optional[Dict[str, Any]]:
        """
        Interpret a custom field value into structured data.
        """
        def extract_pn_value(text: str) -> Optional[str]:
            """Extract prior notification value from text."""
            # Look for PN/PPR patterns with hours (more specific)
            match = re.search(r'\b(?:PN|PPR)\s+(\d{1,2})\s*H(?:R)?\b', text, re.IGNORECASE)
            if match:
                return f"{match.group(1)}H"
            
            # Look for "préavis X heures" patterns
            match = re.search(r'préavis\s+(\d{1,2})\s*heures', text, re.IGNORECASE)
            if match:
                return f"{match.group(1)}H"
            
            # Look for "X heures" after PN context
            match = re.search(r'(?:PN|PPR|préavis).*?(\d{1,2})\s*heures', text, re.IGNORECASE)
            if match:
                return f"{match.group(1)}H"
            
            # Look for "Xh avant" patterns (like "24h avant")
            match = re.search(r'(\d{1,2})h\s+avant', text, re.IGNORECASE)
            if match:
                return f"{match.group(1)}H"
            
            # Look for direct hour patterns (24H, 48H, etc.) but not in O/R context
            match = re.search(r'(?<!O/R\s)\b(\d{1,2})\s*H(?:R)?\b', text, re.IGNORECASE)
            if match:
                return f"{match.group(1)}H"
            
            return None

        def extract_h24_value(text: str) -> Optional[str]:
            """Extract H24 (24-hour availability) value."""
            if re.search(r'\bH24\b', text, re.IGNORECASE):
                return "H24"
            return None

        def extract_on_request_value(text: str) -> Optional[str]:
            """Extract O/R (on request) value."""
            if re.search(r'\b(?:O/R|OR|A LA DEMANDE|À LA DEMANDE|ON REQUEST|DEMANDE|REQUEST)\b', text, re.IGNORECASE):
                return "O/R"
            return None

        def is_custom_available(text: str) -> bool:
            """Check if custom services are available."""
            return bool(re.search(r'\b(?:DOUANE|DOUANES|CUSTOMS|CUSTOM)\b', text, re.IGNORECASE))

        def is_immigration_available(text: str) -> bool:
            """Check if immigration services are available."""
            return bool(re.search(r'\b(?:IMMIGRATION|POLICE|PASSPORT)\b', text, re.IGNORECASE))

        def extract_weekday_weekend_values(text: str) -> tuple[Optional[str], Optional[str]]:
            """Extract weekday and weekend values from text."""
            weekday_pn = None
            weekend_pn = None
            
            # Normalize text for better matching
            text_upper = text.upper()
            
            # Check for H24 first (overrides other patterns)
            h24_match = extract_h24_value(text_upper)
            if h24_match:
                return h24_match, h24_match
            
            # Look for explicit weekday/weekend patterns first
            weekday_patterns = [
                r'WEEKDAYS?:?\s*(.*?)(?:\n|WEEKEND|SAT|SUN|$)',
                r'MON-FRI:?\s*(.*?)(?:\n|WEEKEND|SAT|SUN|$)',
                r'MONDAY-FRIDAY:?\s*(.*?)(?:\n|WEEKEND|SAT|SUN|$)',
                r'LUN-VEN:?\s*(.*?)(?:\n|WEEKEND|SAT|SUN|$)',
                r'MAR-VEN:?\s*(.*?)(?:\n|WEEKEND|SAT|SUN|$)',
            ]
            
            weekend_patterns = [
                r'WEEKENDS?:?\s*(.*?)(?:\n|WEEKDAY|MON|TUE|WED|THU|FRI|$)',
                r'WEEK-END:?\s*(.*?)(?:\n|WEEKDAY|MON|TUE|WED|THU|FRI|$)',
                r'SAT-SUN:?\s*(.*?)(?:\n|WEEKDAY|MON|TUE|WED|THU|FRI|$)',
                r'SATURDAY-SUNDAY:?\s*(.*?)(?:\n|WEEKDAY|MON|TUE|WED|THU|FRI|$)',
                r'SAM-DIM:?\s*(.*?)(?:\n|WEEKDAY|MON|TUE|WED|THU|FRI|$)',
                r'SAM,\s*DIM\s+ET\s+JF:?\s*(.*?)(?:\n|WEEKDAY|MON|TUE|WED|THU|FRI|$)',
                r'SAM,\s*DIM(?!\s+ET\s+JF):?\s*(.*?)(?:\n|WEEKDAY|MON|TUE|WED|THU|FRI|$)',
            ]
            
            # Try to extract weekday value
            for pattern in weekday_patterns:
                match = re.search(pattern, text_upper, re.IGNORECASE | re.DOTALL)
                if match:
                    weekday_text = match.group(1).strip()
                    weekday_pn = extract_pn_value(weekday_text)
                    if weekday_pn:
                        break
            
            # Try to extract weekend value
            for pattern in weekend_patterns:
                match = re.search(pattern, text_upper, re.IGNORECASE | re.DOTALL)
                if match:
                    weekend_text = match.group(1).strip()
                    weekend_pn = extract_pn_value(weekend_text)
                    if weekend_pn:
                        break
            
            # If no explicit weekday/weekend found, look for global patterns
            if not weekday_pn and not weekend_pn:
                global_pn = extract_pn_value(text_upper)
                if global_pn:
                    weekday_pn = global_pn
                    weekend_pn = global_pn
                else:
                    # Only check for O/R if no PN patterns were found
                    or_match = extract_on_request_value(text_upper)
                    if or_match:
                        weekday_pn = or_match
                        weekend_pn = or_match
            
            return weekday_pn, weekend_pn

        # Normalize text
        text = field_value.upper()
        
        # Extract weekday and weekend values
        weekday_pn, weekend_pn = extract_weekday_weekend_values(text)
        
        # Determine if advance notice is required
        advance_notice_required = bool(weekday_pn or weekend_pn)
        
        # If we have H24 or O/R, advance notice is not required
        if weekday_pn in ["H24", "O/R"] and weekend_pn in ["H24", "O/R"]:
            advance_notice_required = False

        return {
            'weekday_pn': weekday_pn,
            'weekend_pn': weekend_pn,
            'advance_notice_required': advance_notice_required,
            'custom_available': is_custom_available(text),
            'immigration_available': is_immigration_available(text),
            'raw_value': field_value
        }