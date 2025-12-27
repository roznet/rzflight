"""
Norway (ENC) AIP HTML Parser

Norway uses the same Eurocontrol MakeAIP format as UK (EGC),
so this parser extends EGCAIPParser with only the authority code changed.
"""

from typing import List
from .aip_egc import EGCAIPParser


class ENCAIPParser(EGCAIPParser):
    """Parser for Norway (ENC) AIP HTML documents.

    Norway's AIP uses the same Eurocontrol MakeAIP format as UK,
    with identical HTML structure, div patterns, and span classes.
    """

    def get_supported_authorities(self) -> List[str]:
        """Get list of supported authority codes."""
        return ['ENC']
