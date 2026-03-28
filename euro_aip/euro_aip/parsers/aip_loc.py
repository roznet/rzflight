"""
Parser for Austria (LOC) AIP PDF documents.

Austrian AIP PDFs are bilingual (German/English) with alternating rows:
- Numbered row: German field name + value
- Unnumbered row: English field name + usually empty value

This parser merges row pairs: English field name + German value.
When the English row also has a value, it takes the English value instead.
"""
from typing import List, Dict, Any
from .aip_default import DefaultAIPParser

import logging
import re

logger = logging.getLogger(__name__)


class LOCAIPParser(DefaultAIPParser):
    """Parser for Austria (LOC) AIP documents."""

    PREFERRED_PARSER = 'pdfplumber'

    def get_supported_authorities(self) -> List[str]:
        return ['LOC']

    def _process_table(self, table: List[Dict[str, Any]], section: str, icao: str) -> List[Dict[str, Any]]:
        """Process Austrian bilingual table by merging German/English row pairs.

        Pattern in the table:
        - Row with col 0 = digit  → German: field name (col 1), value (col 2)
        - Next row with col 0 = '' → English: field name (col 1), value (col 2, often empty)
        """
        rv = []
        i = 0
        rows = table

        while i < len(rows):
            row = rows[i]
            row_id = str(row.get(self.FIELD_ID_INDEX, '') or '').strip()
            de_field = str(row.get(self.FIELD_INDEX, '') or '').strip()
            de_value = str(row.get(self.VALUE_INDEX, '') or '').strip()

            # Check if next row is the English counterpart (no row number)
            en_field = ''
            en_value = ''
            if i + 1 < len(rows):
                next_row = rows[i + 1]
                next_id = str(next_row.get(self.FIELD_ID_INDEX, '') or '').strip()
                if next_id == '' and de_field:
                    en_field = str(next_row.get(self.FIELD_INDEX, '') or '').strip()
                    en_value = str(next_row.get(self.VALUE_INDEX, '') or '').strip()
                    i += 2  # skip both rows
                else:
                    i += 1
            else:
                i += 1

            if not de_field and not en_field:
                continue

            # Determine field name and value
            # Prefer English field name, fall back to German
            field = en_field if en_field else de_field
            # Prefer English value if present, otherwise use German value
            value = en_value if en_value else de_value
            alt_field = de_field if en_field else None
            alt_value = de_value if en_value and de_value != en_value else None

            if not field or not value:
                continue

            rv.append({
                'ident': icao,
                'section': section,
                'field_aip_id': row_id if row_id else None,
                'field': field,
                'alt_field': alt_field,
                'value': value,
                'alt_value': alt_value or '',
            })

        return rv
