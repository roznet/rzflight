import os
import logging
import traceback
from typing import List, Dict, Any
from .aip_base import AIPParser
from .aip_base import DEFAULT_AUTHORITY
import re

logger = logging.getLogger(__name__)

class DefaultAIPParser(AIPParser):
    """Parser for default AIP format (used when authority is not known or specialized)."""

    FIELD_ID_INDEX = 0
    FIELD_INDEX = 1
    VALUE_INDEX = 2
    ALT_VALUE_INDEX = 3
    FIELD_SEPARATOR = r' / '
    
    def get_supported_authorities(self) -> List[str]:
        """Get list of supported authority codes."""
        return [DEFAULT_AUTHORITY]  # This parser is used as a fallback
    
    def parse(self, pdf_data: bytes, icao: str) -> List[Dict[str, Any]]:
        """
        Parse AIP document data using the default format.
        
        Args:
            pdf_data: Raw PDF data
            icao: ICAO airport code
            
        Returns:
            List of dictionaries containing parsed data
        """
        rv = []
        try:
            tables = self._pdf_to_tables(pdf_data)
            if len(tables) > 1:
                admin = tables[0].to_dict('records')
                operational = tables[1].to_dict('records')
                
                rv.extend(self._process_table(admin, 'admin', icao))
                rv.extend(self._process_table(operational, 'operational', icao))
                
            if len(tables) > 3:
                handling = tables[2].to_dict('records')
                passenger = tables[3].to_dict('records')
                
                rv.extend(self._process_table(handling, 'handling', icao))
                rv.extend(self._process_table(passenger, 'passenger', icao))
            # for all the other tables assign it as other
            for table in tables[4:]:
                other = table.to_dict('records')
                rv.extend(self._process_table(other, 'other', icao))
                
        except Exception as e:
            logger.error(f"Error parsing PDF for {icao}: {e}")
            logger.error(f"Full traceback:\n{traceback.format_exc()}")
            return None
                
        if not rv:
            return [{'ident': icao, 'section': 'admin', 'field': 'Observations', 'value': 'Empty file', 'alt_value': ''}]
            
        return rv
    
    def _process_table(self, table: List[Dict[str, Any]], section: str, icao: str) -> List[Dict[str, Any]]:
        """
        Process a table from the PDF.
        
        Args:
            table: List of dictionaries containing table data
            section: Section name (admin, operational, handling, passenger)
            icao: ICAO airport code
            
        Returns:
            List of dictionaries containing processed table data
        """
        rv = []
        field = None
        alt_field = None
        values = []
        alt_values = []
        field_aip_id = None

        for row in table:
            field_sep_line = False
            # we have at least a field and a value
            row_field = row[self.FIELD_INDEX] if self.FIELD_INDEX in row else None
            row_alt_field = None
            row_value = row[self.VALUE_INDEX] if self.VALUE_INDEX in row else None
            row_alt_value = row[self.ALT_VALUE_INDEX] if self.ALT_VALUE_INDEX in row else None
            row_field_aip_id = row[self.FIELD_ID_INDEX] if self.FIELD_ID_INDEX in row else None

            if row_field_aip_id == '':
                row_field_aip_id = None

            # if not None we start a new field
            if row_field is not None:
                if field and len(values) > 0:
                    data = {
                        'ident': icao,
                        'section': section,
                        'field_aip_id': row_field_aip_id,
                        'field': field,
                        'alt_field': alt_field,
                        'value': '\n'.join(values),
                        'alt_value': '\n'.join(alt_values)
                    }
                    rv.append(data)
                values = []
                alt_values = []

                if row_field_aip_id is not None:
                    field_aip_id = row_field_aip_id    
                # first see if field is a single field or a pair of fields
                fields = re.split(self.FIELD_SEPARATOR,row_field)
                if len(fields) == 2:
                    # typically the first field is in local language and the second is in english
                    # so we swap them for consistency on field name
                    field = fields[1]
                    alt_field = fields[0]
                else:
                    field = row_field.strip()
                    alt_field = None
            if row_value is not None:
                values.append(row_value)
            if row_alt_value is not None:
                alt_values.append(row_alt_value)
        if field and len(values) > 0:
            data = {
                'ident': icao,
                'section': section,
                'field': field,
                'alt_field': alt_field,
                'field_aip_id': field_aip_id,
                'value': '\n'.join(values),
                'alt_value': '\n'.join(alt_values)
            }

            # if we have an alt field, usually field is in native language and alt_field is in english
            # so we swap them for consistency on field name
            if alt_field:
                data['field'] = alt_field
                data['alt_field'] = field

            # if we have an alt value, usually value is in native language and alt_value is in english
            # so we swap them for consistency on value
            if alt_values:
                data['value'] = '\n'.join(alt_values)
                data['alt_value'] = '\n'.join(values)

            rv.append(data)
        return rv 