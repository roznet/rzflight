"""Country border-area membership and crossing-requirements helpers.

Pure, offline reference data (no network, no I/O) answering a single
question consumers keep re-encoding: what **border formalities** —
immigration, customs, both, or neither — apply when flying between two
countries? That is a function of two overlapping-but-distinct European
blocs:

- the **Schengen area** (passport-free travel → drives *immigration*), and
- the **EU customs union** (goods move duty-free → drives *customs*).

The two memberships do not coincide. CH/NO/IS/LI are Schengen but outside
the EU customs union; CY/IE are in the EU customs union but outside
Schengen. So a France→Switzerland flight needs customs but no immigration,
while France→Ireland needs immigration but no customs.

All predicates take ISO-3166-1 alpha-2 country codes (case-insensitive).
Unknown codes return ``False`` from the predicates but are surfaced through
``from_known`` / ``to_known`` on :func:`crossing_requirements` so callers
can say "couldn't determine" rather than silently assume an open border.

.. note::
   **Review annually.** Bloc memberships change — Bulgaria and Romania
   fully joined Schengen on 2024-03-31 (air/sea) and 2025-01-01 (land),
   and Croatia joined on 2023-01-01. Re-check these tables against the
   sources below at least once a year.

Sources (verified 2026-07):
- Schengen area members —
  https://home-affairs.ec.europa.eu/policies/schengen-borders-and-visa/schengen-area_en
- EU customs union / EU member states —
  https://taxation-customs.ec.europa.eu/customs-4/eu-customs-union_en
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import FrozenSet, Optional

# --- Reference tables --------------------------------------------------------
# ISO-3166-1 alpha-2 codes. Keep these two sets as the single source of truth;
# everything else derives from them.

#: Schengen area member states. CH/NO/IS/LI are Schengen but NOT EU-customs.
SCHENGEN: FrozenSet[str] = frozenset({
    "AT", "BE", "BG", "HR", "CZ", "DK", "EE", "FI", "FR", "DE", "GR", "HU",
    "IS", "IT", "LV", "LI", "LT", "LU", "MT", "NL", "NO", "PL", "PT", "RO",
    "SK", "SI", "ES", "SE", "CH",
})

#: EU customs union members (the EU-27). CY/IE are EU-customs but NOT Schengen.
EU_CUSTOMS_UNION: FrozenSet[str] = frozenset({
    "AT", "BE", "BG", "HR", "CY", "CZ", "DK", "EE", "FI", "FR", "DE", "GR",
    "HU", "IE", "IT", "LV", "LT", "LU", "MT", "NL", "PL", "PT", "RO", "SK",
    "SI", "ES", "SE",
})

#: Union of both tables — the set of countries we can make a statement about.
_KNOWN: FrozenSet[str] = SCHENGEN | EU_CUSTOMS_UNION


def _normalize(cc: Optional[str]) -> Optional[str]:
    """Upper-case and strip a country code; ``None`` for empty/falsy input."""
    if not cc:
        return None
    normalized = cc.strip().upper()
    return normalized or None


def is_known(cc: str) -> bool:
    """True if ``cc`` appears in either membership table (Schengen or EU-customs).

    A country can be "known" here without being in a given bloc — e.g. ``IE``
    is known (it is in the EU customs union) even though it is not Schengen.
    """
    return _normalize(cc) in _KNOWN


def is_schengen(cc: str) -> bool:
    """True if ``cc`` is a Schengen area member (ISO-3166-1 alpha-2, case-insensitive)."""
    return _normalize(cc) in SCHENGEN


def is_eu_customs_union(cc: str) -> bool:
    """True if ``cc`` is an EU customs union member (ISO-3166-1 alpha-2, case-insensitive)."""
    return _normalize(cc) in EU_CUSTOMS_UNION


@dataclass(frozen=True)
class CrossingRequirements:
    """Border formalities for a flight from one country to another.

    Attributes:
        immigration_required: Immigration/passport check applies (i.e. the pair
            is not both-Schengen).
        customs_required: A customs declaration applies (i.e. the pair is not
            both-in-the-EU-customs-union).
        from_known: The origin country was found in the reference tables.
        to_known: The destination country was found in the reference tables.

    When ``from_known`` or ``to_known`` is ``False`` the ``*_required`` flags
    are computed as if the unknown country were outside every bloc (so they
    default to ``True``). Callers that want to distinguish "definitely a border"
    from "couldn't determine" should check the ``*_known`` flags first.
    """

    immigration_required: bool
    customs_required: bool
    from_known: bool
    to_known: bool


def crossing_requirements(from_cc: str, to_cc: str) -> CrossingRequirements:
    """Border formalities for a flight from ``from_cc`` to ``to_cc``.

    Both arguments are ISO-3166-1 alpha-2 codes (case-insensitive):

    - ``immigration_required = not (is_schengen(from) and is_schengen(to))``
    - ``customs_required     = not (is_eu_customs_union(from) and is_eu_customs_union(to))``
    - Same country → both ``False`` (no domestic border), even for a country
      that is outside both blocs, and even if the code is unknown.
    - Unknown country → ``from_known`` / ``to_known`` is ``False`` so callers can
      report "couldn't determine" instead of assuming an open border.

    Known edge cases the caller may want to special-case (the rule below does
    not encode them, because in aviation terms they are correct as-is):

    - **IE↔GB Common Travel Area** — this rule flags immigration (GB is not
      Schengen), but the CTA means there is no immigration check in practice.
    - **Channel Islands / Isle of Man** (``JE``, ``GG``, ``IM``) — outside both
      blocs, so a flight to/from the EU reads as customs + immigration, which
      is correct.
    """
    f = _normalize(from_cc)
    t = _normalize(to_cc)

    from_known = f in _KNOWN
    to_known = t in _KNOWN

    # Same country (including an unknown-but-identical code) → no border.
    if f is not None and f == t:
        return CrossingRequirements(
            immigration_required=False,
            customs_required=False,
            from_known=from_known,
            to_known=to_known,
        )

    immigration_required = not (f in SCHENGEN and t in SCHENGEN)
    customs_required = not (f in EU_CUSTOMS_UNION and t in EU_CUSTOMS_UNION)

    return CrossingRequirements(
        immigration_required=immigration_required,
        customs_required=customs_required,
        from_known=from_known,
        to_known=to_known,
    )
