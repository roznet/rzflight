"""Choosing the code an OurAirports row is stored under.

OurAirports' ``ident`` is its own primary key, not always the ICAO code. An
aerodrome that had no code when it was first added keeps a placeholder such as
``GB-0007`` (Enstone, ICAO EGTN), and some keep a code that has since been
reallocated: Logroño is ``LELO`` in ``ident`` but ``LERJ`` in the Spanish AIP.
When OurAirports knows the current ICAO code it is in ``icao_code`` or
``gps_code``.

The code a pilot types and reads should be the current one, so it wins. The
previous ``ident`` is kept as :attr:`Airport.alt_ident` rather than dropped,
because some services still publish under it — Logroño's METAR and TAF are
still issued as LELO.
"""

import logging
import re
from typing import Any, Optional, Tuple

import pandas as pd

logger = logging.getLogger(__name__)

_ICAO_RE = re.compile(r'[A-Z]{4}')


def _clean(value: Any) -> Optional[str]:
    """Upper-cased, stripped string, or None for blanks and pandas NaN."""
    if not isinstance(value, str):
        return None
    value = value.strip().upper()
    return value or None


def is_icao_code(code: Any) -> bool:
    """True for a well-formed ICAO location indicator: four letters, not X-prefixed.

    No ICAO region is allocated to X. OurAirports puts Russian internal
    indicators there (XRRT for Taganrog, whose ICAO code is URRT), and no
    international service publishes under them.
    """
    code = _clean(code)
    return bool(code and _ICAO_RE.fullmatch(code) and not code.startswith('X'))


def _is_storable_ident(ident: Optional[str]) -> bool:
    # The historical nav.db filter: any 4-character ident. Kept as-is so rows
    # that only have an ident are neither gained nor lost by this change.
    return ident is not None and len(ident) == 4


def select_airport_code(
    ident: Any,
    icao_code: Any = None,
    gps_code: Any = None,
) -> Tuple[Optional[str], Optional[str]]:
    """Pick the code to store an airport under, and the alias to keep.

    Preference is ``icao_code``, then ``gps_code`` (each only if it passes
    :func:`is_icao_code`), then ``ident`` if it is four characters.

    Returns:
        ``(code, alt_ident)``. ``code`` is None when nothing usable exists.
        ``alt_ident`` is the previous ``ident`` when it was itself storable and
        differs from ``code``; otherwise None.
    """
    ident = _clean(ident)
    code = next(
        (c for c in (_clean(icao_code), _clean(gps_code)) if is_icao_code(c)),
        None,
    )
    if code is None:
        code = ident if _is_storable_ident(ident) else None
    if code is None:
        return None, None
    alt_ident = ident if _is_storable_ident(ident) and ident != code else None
    return code, alt_ident


def assign_airport_codes(airports_df: pd.DataFrame) -> pd.DataFrame:
    """Add ``code`` and ``alt_ident`` columns to an OurAirports airports frame.

    Rows with no usable code are dropped. Two rows can want the same code when
    OurAirports lists it as one aerodrome's ``icao_code`` and another's
    ``ident`` (BISA: Sauðárflugvöllur vs Sandá). The row already stored under
    that code keeps it, so an existing airport is never displaced; the other is
    dropped and logged. An alias equal to another airport's code is cleared,
    so a code only ever names one airport.

    The source ``ident`` column is left untouched: runways still join on it.
    """
    df = airports_df.copy()
    none = [None] * len(df)
    picked = [
        select_airport_code(ident, icao, gps)
        for ident, icao, gps in zip(
            df['ident'],
            df['icao_code'] if 'icao_code' in df.columns else none,
            df['gps_code'] if 'gps_code' in df.columns else none,
        )
    ]
    df['code'] = [code for code, _ in picked]
    df['alt_ident'] = [alt for _, alt in picked]
    df = df[df['code'].notna()]

    holds_code = df['code'] == df['ident'].map(_clean)
    ordered = df.assign(_holds_code=holds_code).sort_values(
        '_holds_code', ascending=False, kind='stable'
    )
    duplicate = ordered['code'].duplicated(keep='first')
    for _, row in ordered[duplicate].iterrows():
        logger.warning(
            "Skipping %s (%s): code %s already belongs to another airport",
            row['ident'], row.get('name'), row['code'],
        )
    df = ordered[~duplicate].drop(columns='_holds_code').sort_index().copy()

    clashing_alias = df['alt_ident'].isin(set(df['code']))
    for _, row in df[clashing_alias].iterrows():
        logger.info(
            "Dropping alias %s of %s: it is another airport's code",
            row['alt_ident'], row['code'],
        )
    df.loc[clashing_alias, 'alt_ident'] = None
    return df
