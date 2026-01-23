"""Q-code based NOTAM categorizer."""

from typing import Dict, Tuple, Set

from euro_aip.briefing.categorization.base import NotamCategorizer, CategorizationResult
from euro_aip.briefing.models.notam import Notam


class QCodeCategorizer(NotamCategorizer):
    """
    Categorize based on ICAO Q-code.

    This is the most reliable categorizer when Q-code is available.
    Q-codes follow the ICAO standard format and provide consistent categorization.

    The Q-code structure:
    - First 2 letters: Subject (what is affected)
    - Letters 3-5: Condition/status (what happened to it)

    Example:
        QMRLC = Runway (MR) + Closed (LC)
        QNVAS = VOR (NV) + Unserviceable (AS)
    """

    # Q-code to (category, tags) mapping
    # Format: Q-code -> (primary_category, set of tags)
    Q_CODE_CATEGORIES: Dict[str, Tuple[str, Set[str]]] = {
        # Movement area - Runway
        'QMRLC': ('runway', {'closed'}),
        'QMRLT': ('runway', {'limited'}),
        'QMRXX': ('runway', set()),
        'QMRHW': ('runway', {'work_in_progress'}),
        'QMRTT': ('runway', {'threshold', 'displaced'}),
        'QMRAS': ('runway', {'unserviceable'}),

        # Movement area - Taxiway
        'QMXLC': ('taxiway', {'closed'}),
        'QMXLT': ('taxiway', {'limited'}),
        'QMXXX': ('taxiway', set()),
        'QMXHW': ('taxiway', {'work_in_progress'}),

        # Movement area - Apron
        'QMALC': ('apron', {'closed'}),
        'QMALT': ('apron', {'limited'}),
        'QMAXX': ('apron', set()),

        # Lighting - Runway
        'QLRLC': ('lighting', {'runway', 'closed'}),
        'QLRAS': ('lighting', {'runway', 'unserviceable'}),
        'QLRLT': ('lighting', {'runway', 'limited'}),

        # Lighting - Approach
        'QLLCL': ('lighting', {'approach', 'closed'}),
        'QLLAS': ('lighting', {'approach', 'unserviceable'}),
        'QLLLT': ('lighting', {'approach', 'limited'}),
        'QLALS': ('lighting', {'approach', 'unserviceable'}),

        # Lighting - PAPI/VASI
        'QLPAS': ('lighting', {'papi', 'unserviceable'}),
        'QLVAS': ('lighting', {'vasi', 'unserviceable'}),

        # Lighting - General
        'QLXAS': ('lighting', {'unserviceable'}),
        'QLXXX': ('lighting', set()),

        # Navigation - VOR
        'QNVAS': ('navaid', {'vor', 'unserviceable'}),
        'QNVXX': ('navaid', {'vor'}),
        'QNVLT': ('navaid', {'vor', 'limited'}),

        # Navigation - DME
        'QNDAS': ('navaid', {'dme', 'unserviceable'}),
        'QNDXX': ('navaid', {'dme'}),

        # Navigation - ILS
        'QNIAS': ('navaid', {'ils', 'unserviceable'}),
        'QNIXX': ('navaid', {'ils'}),
        'QNILT': ('navaid', {'ils', 'limited'}),

        # Navigation - Localizer
        'QNLAS': ('navaid', {'localizer', 'unserviceable'}),
        'QNLXX': ('navaid', {'localizer'}),

        # Navigation - Glide slope
        'QNGAS': ('navaid', {'glideslope', 'unserviceable'}),
        'QNGXX': ('navaid', {'glideslope'}),

        # Navigation - NDB
        'QNBAS': ('navaid', {'ndb', 'unserviceable'}),
        'QNBXX': ('navaid', {'ndb'}),

        # Navigation - TACAN
        'QNTAS': ('navaid', {'tacan', 'unserviceable'}),

        # Navigation - Marker
        'QNMAS': ('navaid', {'marker', 'unserviceable'}),

        # Procedures - Instrument approach
        'QPICH': ('procedure', {'approach', 'changed'}),
        'QPIAU': ('procedure', {'approach', 'unavailable'}),
        'QPIXX': ('procedure', {'approach'}),

        # Procedures - SID
        'QPDCH': ('procedure', {'sid', 'changed'}),
        'QPDAU': ('procedure', {'sid', 'unavailable'}),
        'QPDXX': ('procedure', {'sid'}),

        # Procedures - STAR
        'QPSCH': ('procedure', {'star', 'changed'}),
        'QPSAU': ('procedure', {'star', 'unavailable'}),
        'QPSXX': ('procedure', {'star'}),

        # Procedures - Holding
        'QPHCH': ('procedure', {'holding', 'changed'}),
        'QPHAU': ('procedure', {'holding', 'unavailable'}),

        # Procedures - Minima
        'QPMCH': ('procedure', {'minima', 'changed'}),

        # Airspace - Restricted
        'QARLC': ('airspace', {'restricted', 'closed'}),
        'QARAU': ('airspace', {'restricted', 'active'}),
        'QARXX': ('airspace', {'restricted'}),

        # Airspace - Danger
        'QADLC': ('airspace', {'danger', 'closed'}),
        'QADAU': ('airspace', {'danger', 'active'}),
        'QADXX': ('airspace', {'danger'}),

        # Airspace - Prohibited
        'QAPLC': ('airspace', {'prohibited', 'closed'}),
        'QAPAU': ('airspace', {'prohibited', 'active'}),

        # Airspace - TRA/TSA
        'QATAU': ('airspace', {'tra', 'active'}),
        'QATXX': ('airspace', {'tra'}),

        # Airspace - Other
        'QAHLC': ('airspace', {'closed'}),
        'QAHAU': ('airspace', {'active'}),
        'QAHXX': ('airspace', set()),

        # Obstacles
        'QOBCE': ('obstacle', {'crane', 'erected'}),
        'QOBCR': ('obstacle', {'crane'}),
        'QOBXX': ('obstacle', set()),
        'QOECE': ('obstacle', {'erected'}),
        'QOLXX': ('obstacle', {'lighting'}),

        # Communication
        'QCAAS': ('communication', {'unserviceable'}),
        'QCAXX': ('communication', set()),
        'QCFAS': ('communication', {'frequency', 'unserviceable'}),
        'QCFXX': ('communication', {'frequency'}),

        # Services - ATC
        'QSTAS': ('services', {'atc', 'unserviceable'}),
        'QSTLC': ('services', {'atc', 'closed'}),
        'QSTLH': ('services', {'atc', 'hours_changed'}),
        'QSTXX': ('services', {'atc'}),

        # Services - Approach control
        'QSAAS': ('services', {'approach_control', 'unserviceable'}),
        'QSALC': ('services', {'approach_control', 'closed'}),

        # Services - Tower
        'QSPAS': ('services', {'tower', 'unserviceable'}),
        'QSPLC': ('services', {'tower', 'closed'}),

        # Services - Fuel
        'QSFAS': ('services', {'fuel', 'unavailable'}),
        'QSFLT': ('services', {'fuel', 'limited'}),
        'QSFXX': ('services', {'fuel'}),

        # Warnings
        'QWPLW': ('warning', {'parachuting'}),
        'QWULW': ('warning', {'uas', 'drone'}),
        'QWMLW': ('warning', {'military'}),
        'QWELW': ('warning', {'exercise'}),
        'QWHLW': ('warning', {'hazard'}),
        'QWBLW': ('warning', {'birds'}),
        'QWALW': ('warning', {'airshow'}),
        'QWFLW': ('warning', {'fireworks'}),
        'QWCLW': ('warning', {'crane'}),
        'QWLLW': ('warning', {'laser'}),
    }

    @property
    def name(self) -> str:
        return "q_code"

    def categorize(self, notam: Notam) -> CategorizationResult:
        """
        Categorize NOTAM based on Q-code.

        Returns high confidence for exact matches,
        lower confidence for prefix matches.
        """
        result = CategorizationResult(source=self.name)

        if not notam.q_code:
            result.confidence = 0.0
            return result

        # Normalize Q-code
        q_code = notam.q_code.upper()
        if not q_code.startswith('Q'):
            q_code = 'Q' + q_code

        # Try exact match first
        if q_code in self.Q_CODE_CATEGORIES:
            cat, tags = self.Q_CODE_CATEGORIES[q_code]
            result.primary_category = cat
            result.categories.add(cat)
            result.tags.update(tags)
            result.confidence = 1.0
            return result

        # Try prefix matches (first 3, 4 characters)
        for prefix_len in [4, 3]:
            prefix = q_code[:prefix_len]
            for code, (cat, tags) in self.Q_CODE_CATEGORIES.items():
                if code.startswith(prefix):
                    result.primary_category = cat
                    result.categories.add(cat)
                    # Don't include tags for partial matches
                    result.confidence = 0.8 if prefix_len == 4 else 0.6
                    return result

        # Try 2-letter subject code
        subject = q_code[1:3] if len(q_code) >= 3 else None
        if subject:
            subject_categories = {
                'MR': 'runway',
                'MX': 'taxiway',
                'MA': 'apron',
                'LR': 'lighting',
                'LL': 'lighting',
                'LX': 'lighting',
                'LP': 'lighting',
                'LV': 'lighting',
                'NV': 'navaid',
                'ND': 'navaid',
                'NI': 'navaid',
                'NL': 'navaid',
                'NG': 'navaid',
                'NB': 'navaid',
                'NT': 'navaid',
                'NM': 'navaid',
                'PI': 'procedure',
                'PD': 'procedure',
                'PS': 'procedure',
                'PH': 'procedure',
                'PM': 'procedure',
                'AR': 'airspace',
                'AD': 'airspace',
                'AP': 'airspace',
                'AT': 'airspace',
                'AH': 'airspace',
                'OB': 'obstacle',
                'OE': 'obstacle',
                'OL': 'obstacle',
                'CA': 'communication',
                'CF': 'communication',
                'ST': 'services',
                'SA': 'services',
                'SP': 'services',
                'SF': 'services',
                'WP': 'warning',
                'WU': 'warning',
                'WM': 'warning',
                'WE': 'warning',
                'WH': 'warning',
                'WB': 'warning',
                'WA': 'warning',
                'WF': 'warning',
                'WC': 'warning',
                'WL': 'warning',
            }

            if subject in subject_categories:
                result.primary_category = subject_categories[subject]
                result.categories.add(subject_categories[subject])
                result.confidence = 0.5
                return result

        return result
