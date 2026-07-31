"""
Military aerodrome classification.

No open aerodrome dataset we consume carries a military flag: OurAirports only
distinguishes small/medium/large airport, and military fields are largely absent
from the civil AIP AD 2 sections, so ``aip_entries`` cannot supply one either.

This module derives the flag from two signals only:

1. **Curated overrides** — the hand-maintained lists in
   :mod:`euro_aip.utils.military_aerodromes`. Needed for joint-use fields whose
   published name gives nothing away (``EKYT`` Aalborg, ``LGTS`` Thessaloniki),
   and to veto rule false positives (``EGXG`` Leeds East, an ex-RAF station
   purely civil since 2014).
2. **ICAO code conventions** — only two national schemes actually encode the
   distinction: Germany reserves the ``ET`` prefix for military fields (vs ``ED``
   civil), and the UK reserves a set of third letters within ``EG``. No other
   country separates them; French military fields, for instance, are scattered
   across LFB/LFJ/LFK/LFM/LFO/LFP/LFQ/LFR/LFS/LFX/LFY alongside civil ones.

**Aerodrome names are deliberately not matched at runtime.** Name text is a good
way to *generate candidates* but a bad way to *decide*, because a published name
is not revoked when a base closes: five Belgian Air Force bases deactivated in
the 1990s are still called "X Air Base" while operating as civil gliding sites.
Candidate generation therefore lives in an offline review tool
(``tools/review_military_candidates.py`` in flyfun-apps) which cross-checks each
name match against AIP evidence and emits an artifact for manual promotion into
the curated list. That keeps every runtime verdict traceable to a reviewed
decision rather than to a regex over a name that may be decades out of date.

The OurAirports ``keywords`` column is never consulted either, and is worse than
names: it retains wartime identities, so ``EGSU`` Duxford carries "RAF Duxford"
and ``EDDF`` Frankfurt carries "Rhein-Main Air Base".

The result is a best-effort classification, not an authoritative one. A ``False``
verdict means "no military signal found", not a positive assertion that the
field is civil. For an authoritative flag the options are openAIP (whose
aerodrome type enum distinguishes military) or the per-country eAIP index
categories (Austro Control already publishes PRI/SRY/**MIL**, which
``AustriaEAIPWebSource`` currently discards).

Usage:
    from euro_aip.utils import MilitaryClassifier

    classifier = MilitaryClassifier()
    classifier.classify('ETAR').is_military  # True
    classifier.annotate(airport)  # sets airport.military in place
"""


import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Dict, FrozenSet, Optional, Tuple

from euro_aip.utils.military_aerodromes import (
    KNOWN_CIVIL_ICAOS,
    KNOWN_MILITARY_ICAOS,
)

if TYPE_CHECKING:
    from euro_aip.models.airport import Airport

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# ICAO code conventions
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class IcaoPrefixRule:
    """A national ICAO-code convention that separates military from civil.

    Args:
        prefix: Two-letter ICAO country prefix (e.g. ``ET``, ``EG``).
        third_letters: If given, only idents whose third letter is in this set
            match. Used for the UK, where the military split lives in the third
            character of an otherwise shared ``EG`` prefix.
        description: Human-readable note, surfaced in the classification reason.
    """

    prefix: str
    description: str
    third_letters: Optional[FrozenSet[str]] = None

    def matches(self, ident: str) -> bool:
        if not ident.startswith(self.prefix):
            return False
        if self.third_letters is None:
            return True
        return ident[2] in self.third_letters


# Only add a rule here when the convention is genuinely clean. Verified against
# OurAirports: Germany's ET/ED split is exact, and the UK third-letter set has a
# single stale member (EGXG, vetoed via FORMER_MILITARY). Every other European
# country mixes military and civil within the same prefixes.
ICAO_PREFIX_RULES: Tuple[IcaoPrefixRule, ...] = (
    IcaoPrefixRule(
        prefix='ET',
        description='German military prefix (ET vs ED civil)',
    ),
    IcaoPrefixRule(
        prefix='EG',
        third_letters=frozenset('DOQUVWXY'),
        description='UK military third letter (RAF/RNAS/MoD stations)',
    ),
)


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class MilitaryClassification:
    """Outcome of classifying one aerodrome.

    Attributes:
        is_military: Best-effort verdict. ``False`` means "no military signal
            found", not a positive assertion that the field is civil.
        rule: Stable slug for which signal decided it — ``override_military``,
            ``override_civil``, ``icao_prefix`` or ``none``. Suitable for
            grouping/logging a build breakdown.
        detail: What specifically matched (e.g. ``ET``, or the curated reason).
    """

    is_military: bool
    rule: str
    detail: Optional[str] = None

    @property
    def reason(self) -> str:
        """Compact ``rule:detail`` string for logs."""
        return f'{self.rule}:{self.detail}' if self.detail else self.rule


class MilitaryClassifier:
    """Derives a best-effort military flag for an aerodrome.

    Args:
        extra_military: Additional ICAO codes to force to military, merged over
            the built-in list. Values are free-text reasons.
        extra_civil: Additional ICAO codes to force to civil, merged over the
            built-in list. Takes precedence over ``extra_military``.
    """

    def __init__(
        self,
        extra_military: Optional[Dict[str, str]] = None,
        extra_civil: Optional[Dict[str, str]] = None,
    ):
        self.military_overrides = dict(KNOWN_MILITARY_ICAOS)
        if extra_military:
            self.military_overrides.update(extra_military)

        self.civil_overrides = dict(KNOWN_CIVIL_ICAOS)
        if extra_civil:
            self.civil_overrides.update(extra_civil)

    # -- public API ---------------------------------------------------------

    def classify(self, ident: str, name: Optional[str] = None) -> MilitaryClassification:
        """Classify one aerodrome.

        Args:
            ident: ICAO code. Case-insensitive.
            name: Accepted and ignored. Names are used to generate candidates in
                the offline review tool, never to decide at runtime — see the
                module docstring. Kept in the signature so callers can pass an
                airport's fields without special-casing.

        Returns:
            A MilitaryClassification. Never None — an unmatched aerodrome comes
            back as ``is_military=False, rule='none'``.
        """
        code = (ident or '').strip().upper()

        # 1. Curated overrides win outright, civil veto first.
        if code in self.civil_overrides:
            return MilitaryClassification(False, 'override_civil', self.civil_overrides[code])
        if code in self.military_overrides:
            return MilitaryClassification(True, 'override_military', self.military_overrides[code])

        # 2. ICAO code conventions. Guard on a well-formed 4-letter ident so
        #    local codes sharing a prefix are not swept up — e.g. ETT1
        #    (Etting-Adelmannsberg glider field) and EG74 (Bruntingthorpe).
        if len(code) == 4 and code.isalpha():
            for rule in ICAO_PREFIX_RULES:
                if rule.matches(code):
                    return MilitaryClassification(True, 'icao_prefix', rule.prefix)

        return MilitaryClassification(False, 'none')

    def is_military(self, ident: str, name: Optional[str] = None) -> bool:
        """Convenience wrapper returning just the verdict."""
        return self.classify(ident, name).is_military

    def classify_airport(self, airport: 'Airport') -> MilitaryClassification:
        """Classify an Airport model without mutating it."""
        return self.classify(airport.ident, airport.name)

    def annotate(self, airport: 'Airport') -> MilitaryClassification:
        """Classify an Airport and store the verdict on ``airport.military``.

        Returns the classification so callers can log a breakdown by rule.
        """
        result = self.classify_airport(airport)
        airport.military = result.is_military
        return result

    def annotate_all(self, airports) -> Dict[str, int]:
        """Annotate an iterable of Airports, returning counts keyed by rule.

        The counts are the point of this helper: they make it obvious at build
        time if a rule stops firing (e.g. an upstream name-format change).
        """
        counts: Dict[str, int] = {}
        for airport in airports:
            result = self.annotate(airport)
            if result.is_military:
                counts[result.rule] = counts.get(result.rule, 0) + 1
        return counts
