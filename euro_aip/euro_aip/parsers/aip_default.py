import os
import logging
from typing import List, Dict, Any
from .aip_base import AIPParser
from .aip_factory import DEFAULT_AUTHORITY

logger = logging.getLogger(__name__)

class DefaultAIPParser(AIPParser):
    """Parser for default AIP format (used when authority is not known or specialized)."""
    
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
                admin = tables[0].df.to_dict('records')
                operational = tables[1].df.to_dict('records')
                
                rv.extend(self._process_table(admin, 'admin', icao))
                rv.extend(self._process_table(operational, 'operational', icao))
                
            if len(tables) > 3:
                handling = tables[2].df.to_dict('records')
                passenger = tables[3].df.to_dict('records')
                
                rv.extend(self._process_table(handling, 'handling', icao))
                rv.extend(self._process_table(passenger, 'passenger', icao))
                
        except Exception as e:
            logger.error(f"Error parsing PDF for {icao}: {e}")
            return None
        finally:
            # Clean up the temporary file
            if 'temp_file' in locals():
                os.unlink(temp_file.name)
                
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
        for row in table:
            print(row)
            field_sep_line = False
            # we have at least a field and a value
            if 1 in row:
                fields = row[1].split(' / ')
                if len(fields) == 2:
                    field = fields[0]
                    alt_field = fields[1]
                else:
                    sp = row[1].splitlines()
                    if len(sp) == 2:
                        field_sep_line = True
                        field = sp[0]
                        alt_field = sp[1]
                    else:
                        field = row[1]
                        alt_field = None

                if 2 in row:
                    value = row[2]
                else:
                    value = None
                if 3 in row:
                    alt_value = row[3]
                else:
                    alt_value = None
                if alt_field and not alt_value and value:
                    sp = value.splitlines()
                    if len(sp) % 2 == 0:
                        half = len(sp) // 2
                        value = '\n'.join(sp[:half])
                        alt_value = '\n'.join(sp[half:])
                if 3 in row and alt_value == '':
                    sp = value.splitlines()
                    if len(sp) == 2:
                        value = sp[0]
                        alt_value = sp[1]

                data = {
                    'ident': icao,
                    'section': section,
                    'field': field,
                    'alt_field': alt_field,
                    'value': value,
                    'alt_value': alt_value
                }
                rv.append(data)
        return rv 