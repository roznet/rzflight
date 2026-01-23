"""Text pattern-based NOTAM categorizer."""

import re
from typing import List, Tuple, Set, Pattern

from euro_aip.briefing.categorization.base import NotamCategorizer, CategorizationResult
from euro_aip.briefing.models.notam import Notam


class TextRuleCategorizer(NotamCategorizer):
    """
    Categorize based on text pattern matching.

    Useful when Q-code is missing or incomplete. Uses regex patterns
    to identify common NOTAM content patterns.

    Patterns are ordered by specificity - more specific patterns
    are checked first.
    """

    # Text patterns to categories
    # Format: (pattern, category, tags)
    RULES: List[Tuple[str, str, Set[str]]] = [
        # Runway closures
        (r'\bRWY\s*\d+[LRC]?(/\d+[LRC]?)?\s*(CLSD|CLOSED)\b', 'runway', {'closed'}),
        (r'\bRUNWAY\s*\d*\s*(CLSD|CLOSED)\b', 'runway', {'closed'}),
        (r'\bRWY\s*\d+[LRC]?(/\d+[LRC]?)?\s*(RESTRICTED|LIMITED)\b', 'runway', {'limited'}),
        (r'\bRWY\s*\d+[LRC]?\s+.*\s+(U/S|UNSERVICEABLE|INOP)\b', 'runway', {'unserviceable'}),
        (r'\bRWY\s*\d+[LRC]?\s+.*\s+WIP\b', 'runway', {'work_in_progress'}),
        (r'\bRUNWAY\s+SURFACE\b', 'runway', {'surface'}),
        (r'\bRWY\s*\d+[LRC]?.*DISPLACED\s+THR', 'runway', {'threshold', 'displaced'}),

        # Taxiway closures
        (r'\bTWY\s*[A-Z]+\d*\s*(CLSD|CLOSED)\b', 'taxiway', {'closed'}),
        (r'\bTAXIWAY\s*[A-Z]*\d*\s*(CLSD|CLOSED)\b', 'taxiway', {'closed'}),
        (r'\bTWY\s*[A-Z]+\d*\s*(RESTRICTED|LIMITED)\b', 'taxiway', {'limited'}),

        # Apron
        (r'\bAPRON\s*\d*\s*(CLSD|CLOSED)\b', 'apron', {'closed'}),
        (r'\bAPRON\s*\d*\s*(RESTRICTED|LIMITED)\b', 'apron', {'limited'}),
        (r'\bSTAND\s*\d+\s*(CLSD|CLOSED|NOT AVBL)\b', 'apron', {'stand', 'closed'}),

        # Lighting - Approach
        (r'\bALS\s*(U/S|UNSERVICEABLE|INOP|OUT OF SERVICE)\b', 'lighting', {'approach', 'unserviceable'}),
        (r'\bAPPROACH\s+L(IGH)?T(ING|S)?\s*(U/S|UNSERVICEABLE|INOP)\b', 'lighting', {'approach', 'unserviceable'}),

        # Lighting - PAPI/VASI
        (r'\bPAPI\s*(U/S|UNSERVICEABLE|INOP|OUT OF SERVICE)\b', 'lighting', {'papi', 'unserviceable'}),
        (r'\bVASI\s*(U/S|UNSERVICEABLE|INOP|OUT OF SERVICE)\b', 'lighting', {'vasi', 'unserviceable'}),

        # Lighting - Runway
        (r'\bRWY\s*\d+.*L(IGH)?T(ING|S)?.*INOP\b', 'lighting', {'runway', 'unserviceable'}),
        (r'\bRWY\s*\d+.*EDGE\s+L(IGH)?T(S)?\s*(U/S|UNSERVICEABLE|INOP)\b', 'lighting', {'runway', 'edge', 'unserviceable'}),
        (r'\bRWY\s*\d+.*CENTRE\s*LINE\s+L(IGH)?T(S)?\s*(U/S|UNSERVICEABLE|INOP)\b', 'lighting', {'runway', 'centreline', 'unserviceable'}),

        # Lighting - Taxiway
        (r'\bTWY.*L(IGH)?T(ING|S)?.*INOP\b', 'lighting', {'taxiway', 'unserviceable'}),

        # Navigation aids - VOR
        (r'\bVOR\s+[A-Z]{3}\s*(U/S|UNSERVICEABLE|OUT OF SERVICE)\b', 'navaid', {'vor', 'unserviceable'}),
        (r'\bVOR\s+[A-Z]{3}\s*WITHDRAWN\b', 'navaid', {'vor', 'withdrawn'}),
        (r'\bVOR\s+[A-Z]{3}\s*(NOT AVBL|UNAVAILABLE)\b', 'navaid', {'vor', 'unavailable'}),

        # Navigation aids - ILS
        (r'\bILS\s*(CAT\s*[I]+)?\s*(U/S|UNSERVICEABLE|OUT OF SERVICE)\b', 'navaid', {'ils', 'unserviceable'}),
        (r'\bILS\s+RWY\s*\d+[LRC]?\s*(U/S|UNSERVICEABLE|OUT OF SERVICE)\b', 'navaid', {'ils', 'unserviceable'}),
        (r'\bLOC(ALIZER)?\s*(U/S|UNSERVICEABLE|OUT OF SERVICE)\b', 'navaid', {'localizer', 'unserviceable'}),
        (r'\bGLIDE\s*(PATH|SLOPE)\s*(U/S|UNSERVICEABLE|OUT OF SERVICE)\b', 'navaid', {'glideslope', 'unserviceable'}),
        (r'\bG/S\s*(U/S|UNSERVICEABLE)\b', 'navaid', {'glideslope', 'unserviceable'}),

        # Navigation aids - DME
        (r'\bDME\s+[A-Z]{3}\s*(U/S|UNSERVICEABLE|OUT OF SERVICE)\b', 'navaid', {'dme', 'unserviceable'}),
        (r'\bDME\s*(U/S|UNSERVICEABLE|OUT OF SERVICE)\b', 'navaid', {'dme', 'unserviceable'}),

        # Navigation aids - NDB
        (r'\bNDB\s+[A-Z]{2,3}\s*(U/S|UNSERVICEABLE|OUT OF SERVICE)\b', 'navaid', {'ndb', 'unserviceable'}),

        # Navigation aids - TACAN
        (r'\bTACAN\s*(U/S|UNSERVICEABLE|OUT OF SERVICE)\b', 'navaid', {'tacan', 'unserviceable'}),

        # Navigation aids - GPS/GNSS
        (r'\bGNSS\s*(U/S|UNSERVICEABLE|UNRELIABLE)\b', 'navaid', {'gnss', 'unserviceable'}),
        (r'\bGPS\s*(U/S|UNSERVICEABLE|UNRELIABLE|JAMMING)\b', 'navaid', {'gps', 'unserviceable'}),
        (r'\bRNAV\s*(U/S|UNSERVICEABLE|NOT AVBL)\b', 'navaid', {'rnav', 'unserviceable'}),

        # Procedures - Approach
        (r'\bIAP\s*.*\b(SUSPENDED|NOT AVAILABLE|NA|WITHDRAWN)\b', 'procedure', {'approach', 'unavailable'}),
        (r'\bINSTRUMENT\s+APPROACH\s*.*\b(SUSPENDED|NOT AVAILABLE|NA)\b', 'procedure', {'approach', 'unavailable'}),
        (r'\bAPCH\s+PROC\s*.*\b(SUSPENDED|NOT AVAILABLE|NA)\b', 'procedure', {'approach', 'unavailable'}),
        (r'\bILS\s+RWY\s*\d+[LRC]?\s+APCH\s*.*\b(NOT AVBL|SUSPENDED)\b', 'procedure', {'approach', 'ils', 'unavailable'}),

        # Procedures - SID/STAR
        (r'\bSID\s+[A-Z0-9]+\s*.*\b(SUSPENDED|NOT AVAILABLE|WITHDRAWN)\b', 'procedure', {'sid', 'unavailable'}),
        (r'\bSTAR\s+[A-Z0-9]+\s*.*\b(SUSPENDED|NOT AVAILABLE|WITHDRAWN)\b', 'procedure', {'star', 'unavailable'}),

        # Procedures - Minima
        (r'\bMINIM(UM|A)\s*(ALTITUDE|HEIGHT)?\s*(CHANGED|RAISED|INCREASED)\b', 'procedure', {'minima', 'changed'}),
        (r'\bMDA\s*(RAISED|INCREASED|CHANGED)\b', 'procedure', {'minima', 'changed'}),
        (r'\bDA\s*(RAISED|INCREASED|CHANGED)\b', 'procedure', {'minima', 'changed'}),

        # Procedures - Circling
        (r'\bCIRCLING\s*(NOT AUTH|NOT AUTHORIZED|PROHIBITED)\b', 'procedure', {'circling', 'prohibited'}),

        # Obstacles
        (r'\bCRANE\s*(ERECTED|OPR|OPERATING|ACTIVE)\b', 'obstacle', {'crane'}),
        (r'\bCRANE\s+\d+\s*(FT|M)\s+AGL\b', 'obstacle', {'crane'}),
        (r'\bWIND\s*TURBINE\b', 'obstacle', {'wind_turbine'}),
        (r'\bTOWER\b.*\b(\d+)\s*(FT|M)\s*(AGL|AMSL)\b', 'obstacle', {'tower'}),
        (r'\bOBSTACLE\s*LGT\b', 'obstacle', {'lighting'}),
        (r'\bMAST\s+\d+\s*(FT|M)\b', 'obstacle', {'mast'}),
        (r'\bCONSTRUCTION\s+(WORK|CRANE|ACTIVITY)\b', 'obstacle', {'construction'}),

        # Airspace - Restricted/Danger
        (r'\bTEMPORARY\s*(RESTRICTED|DANGER)\s*AREA\b', 'airspace', {'temporary', 'restricted'}),
        (r'\bTRA\s*[A-Z0-9]*\s*(ACTIVE|ACTIVATED)\b', 'airspace', {'tra', 'active'}),
        (r'\bTSA\s*[A-Z0-9]*\s*(ACTIVE|ACTIVATED)\b', 'airspace', {'tsa', 'active'}),
        (r'\bRESTRICTED\s+AREA\s*[A-Z0-9]*\s*(ACTIVE|ACTIVATED)\b', 'airspace', {'restricted', 'active'}),
        (r'\bDANGER\s+AREA\s*[A-Z0-9]*\s*(ACTIVE|ACTIVATED)\b', 'airspace', {'danger', 'active'}),
        (r'\bPROHIBITED\s+AREA\b', 'airspace', {'prohibited'}),

        # Airspace - Activities
        (r'\bPARA(CHUTE|CHUTING)\s*ACT(IVITY|IVITIES)?\b', 'airspace', {'parachuting'}),
        (r'\bSKYDIVING\b', 'airspace', {'parachuting'}),
        (r'\bUAS\s*ACT(IVITY|IVITIES)?\b', 'airspace', {'drone'}),
        (r'\bDRONE\s*ACT(IVITY|IVITIES)?\b', 'airspace', {'drone'}),
        (r'\bRPAS\b', 'airspace', {'drone'}),
        (r'\bAIRSHOW\b', 'airspace', {'airshow'}),
        (r'\bAIR\s+DISPLAY\b', 'airspace', {'airshow'}),
        (r'\bMILITARY\s*(EXERCISE|ACTIVITY|OPS)\b', 'airspace', {'military'}),
        (r'\bFIRING\b', 'airspace', {'military', 'firing'}),
        (r'\bLASER\s*(ACTIVITY|OPERATIONS)\b', 'airspace', {'laser'}),
        (r'\bFIREWORKS?\b', 'airspace', {'fireworks'}),
        (r'\bBALLOON\s*(ACTIVITY|RELEASE|OPS)\b', 'airspace', {'balloon'}),
        (r'\bROCKET\s*(LAUNCH|ACTIVITY)\b', 'airspace', {'rocket'}),
        (r'\bBLASTING\b', 'airspace', {'blasting'}),

        # Services - ATC
        (r'\bTWR\s*(CLSD|CLOSED|NOT AVBL)\b', 'services', {'tower', 'closed'}),
        (r'\bAPP\s*(CLSD|CLOSED|NOT AVBL)\b', 'services', {'approach_control', 'closed'}),
        (r'\bATC\s*(CLSD|CLOSED|NOT AVBL|UNSERVICEABLE)\b', 'services', {'atc', 'closed'}),
        (r'\bRADAR\s*(U/S|UNSERVICEABLE|OUT OF SERVICE)\b', 'services', {'radar', 'unserviceable'}),
        (r'\bATS\s*(NOT AVBL|UNSERVICEABLE)\b', 'services', {'ats', 'unserviceable'}),

        # Services - Fuel
        (r'\bFUEL\s*(NOT\s+AVAILABLE|UNAVAILABLE|LIMITED)\b', 'services', {'fuel', 'limited'}),
        (r'\bAVGAS\s*(NOT\s+AVBL|UNAVAILABLE)\b', 'services', {'fuel', 'avgas', 'unavailable'}),
        (r'\bJET\s*(FUEL|A1?)?\s*(NOT\s+AVBL|UNAVAILABLE)\b', 'services', {'fuel', 'jet', 'unavailable'}),

        # Services - Other
        (r'\bDE-?ICING\s*(NOT\s+AVBL|UNAVAILABLE|LIMITED)\b', 'services', {'deicing', 'limited'}),
        (r'\bFIRE\s*(SERVICE|FIGHTING)\s*(NOT\s+AVBL|REDUCED|LIMITED)\b', 'services', {'fire', 'limited'}),
        (r'\bRFF\s*(CATEGORY|CAT)\s*(DOWNGRADE|REDUCED)\b', 'services', {'fire', 'reduced'}),

        # Wildlife
        (r'\bBIRD\s*(ACTIVITY|CONCENTRATION|HAZARD|STRIKE)\b', 'wildlife', {'birds'}),
        (r'\bWILDLIFE\s*(HAZARD|ACTIVITY)\b', 'wildlife', set()),
        (r'\bBAT\s*(ACTIVITY|MIGRATION)\b', 'wildlife', {'bats'}),

        # Communication
        (r'\bFREQ(UENCY)?\s*\d+\.\d+\s*(U/S|UNSERVICEABLE)\b', 'communication', {'frequency', 'unserviceable'}),
        (r'\bATIS\s*(U/S|UNSERVICEABLE|NOT AVBL)\b', 'communication', {'atis', 'unserviceable'}),
        (r'\bVOLMET\s*(U/S|UNSERVICEABLE)\b', 'communication', {'volmet', 'unserviceable'}),

        # Airport general
        (r'\bAD\s*(CLSD|CLOSED)\b', 'aerodrome', {'closed'}),
        (r'\bAERODROME\s*(CLSD|CLOSED)\b', 'aerodrome', {'closed'}),
        (r'\bAIRPORT\s*(CLSD|CLOSED)\b', 'aerodrome', {'closed'}),
        (r'\bAD\s+AVBL\s+FOR\s+EMERGENCY\s+ONLY\b', 'aerodrome', {'emergency_only'}),
        (r'\bPPR\s+REQUIRED\b', 'aerodrome', {'ppr'}),
    ]

    def __init__(self):
        """Initialize with compiled patterns for performance."""
        self._compiled_rules: List[Tuple[Pattern, str, Set[str]]] = [
            (re.compile(pattern, re.IGNORECASE), cat, tags)
            for pattern, cat, tags in self.RULES
        ]

    @property
    def name(self) -> str:
        return "text_rules"

    def categorize(self, notam: Notam) -> CategorizationResult:
        """
        Categorize NOTAM based on text pattern matching.

        Checks all patterns and uses the most specific match
        (most tags) as primary category.
        """
        result = CategorizationResult(source=self.name)
        text = f"{notam.raw_text} {notam.message}"

        matches: List[Tuple[str, Set[str]]] = []
        for pattern, cat, tags in self._compiled_rules:
            if pattern.search(text):
                matches.append((cat, tags))

        if matches:
            # Use match with most tags as primary (most specific)
            best_match = max(matches, key=lambda x: len(x[1]))
            result.primary_category = best_match[0]

            # Collect all categories and tags
            for cat, tags in matches:
                result.categories.add(cat)
                result.tags.update(tags)

            result.confidence = 0.7  # Lower confidence than Q-code

        return result
