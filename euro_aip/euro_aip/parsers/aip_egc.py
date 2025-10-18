import re
import logging
from typing import List, Dict, Any, Optional
from bs4 import BeautifulSoup
from .aip_base import AIPParser
from .procedure_factory import ProcedureParserFactory

logger = logging.getLogger(__name__)

class EGCAIPParser(AIPParser):
    """Parser for UK (EGC) AIP HTML documents."""
    
    def get_supported_authorities(self) -> List[str]:
        """Get list of supported authority codes."""
        return ['EGC']
    
    def parse(self, html_data: bytes, icao: str) -> List[Dict[str, Any]]:
        """
        Parse UK AIP HTML document data.
        
        Args:
            html_data: Raw HTML data
            icao: ICAO airport code
            
        Returns:
            List of dictionaries containing parsed data
        """
        # Convert bytes to string
        html_content = html_data.decode('utf-8', errors='ignore')
        
        # Parse HTML with BeautifulSoup
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Map section numbers to section names for AIP data
        section_mapping = {
            '2': 'admin',
            '3': 'operational', 
            '4': 'handling',
            '5': 'passenger'
        }
        
        # Extract tables from AIP sections
        tables = self._extract_tables_from_sections(soup, icao, section_mapping)
        
        rv = []
        for table in tables:
            table_data = self._parse_table(table['table'], table['section'], icao)
            rv.extend(table_data)
        
        return rv
    
    def extract_procedures(self, html_data: bytes, icao: str) -> List[Dict[str, Any]]:
        """
        Extract procedures from UK AIP HTML document data.
        
        Args:
            html_data: Raw HTML data
            icao: ICAO airport code
            
        Returns:
            List of dictionaries containing procedure data
        """
        # Convert bytes to string
        html_content = html_data.decode('utf-8', errors='ignore')
        
        # Parse HTML with BeautifulSoup
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Map section numbers to section names for procedures
        section_mapping = {
            '24': 'procedures'
        }
        
        # Extract tables from procedure sections
        tables = self._extract_tables_from_sections(soup, icao, section_mapping)
        
        rv = []
        for table in tables:
            table_data = self._parse_procedure_table(table['table'], table['section'], icao)
            rv.extend(table_data)
        
        return rv
    
    def _extract_tables_from_sections(self, soup: BeautifulSoup, icao: str, section_mapping: Dict[str, str]) -> List[Dict[str, Any]]:
        """
        Extract tables from HTML sections based on the provided section mapping.
        
        Args:
            soup: BeautifulSoup object
            icao: ICAO airport code
            section_mapping: Dictionary mapping section numbers to section names
            
        Returns:
            List of dictionaries containing table and section information
        """
        tables = []
        
        # Look for div elements with pattern {ICAO}-AD-2.[section_number]
        for section_num in section_mapping.keys():
            pattern = f"{icao}-AD-2\\.{section_num}"
            div_elements = soup.find_all('div', id=re.compile(pattern))
            
            logger.debug(f"Found {len(div_elements)} div elements for {icao} section {section_num}")
            
            for div in div_elements:
                # Extract section number from ID
                match = re.search(pattern, div.get('id', ''))
                if not match:
                    continue
                    
                section_name = section_mapping.get(section_num)
                if not section_name:
                    continue
                    
                logger.debug(f"Processing section {section_num} ({section_name}) for {icao}")
                
                # Find all tables in this div
                div_tables = div.find_all('table')
                
                for table in div_tables:
                    tables.append({
                        'table': table,
                        'section': section_name
                    })
        
        return tables
    
    def _parse_table(self, table, section: str, icao: str) -> List[Dict[str, Any]]:
        """
        Parse a table element and extract structured data.
        
        Args:
            table: BeautifulSoup table element
            section: Section name (admin, operational, handling, passenger)
            icao: ICAO airport code
            
        Returns:
            List of dictionaries containing parsed table data
        """
        rv = []
        
        # Map section names to numbers for std_field_id construction
        section_number_map = {
            'admin': '2',
            'operational': '3', 
            'handling': '4',
            'passenger': '5'
        }
        section_num = section_number_map.get(section, '2')
        
        # Find all rows in the table
        rows = table.find_all('tr')
        
        for row in rows:
            # Find all cells in the row
            cells = row.find_all(['td', 'th'])
            
            if len(cells) < 2:
                continue

            # UK tables structure:
            # - col0: field number (for std_field_id construction)
            # - col1: field (EN label)
            # - col2+: value(s)
            field_number_cell = cells[0] if len(cells) > 0 else None
            field_cell = cells[1] if len(cells) > 1 else None
            value_cell = cells[2] if len(cells) > 2 else None
            alt_value_cell = cells[3] if len(cells) > 3 else None

            # Extract field number for std_field_id construction
            field_number = self._extract_text(field_number_cell)
            if not field_number or not field_number.isdigit():
                continue
                
            # Construct std_field_id: section number + field number (e.g., "203" for section 2, field 3)
            # Format field number as 2-digit string (e.g., "02" for field 2)
            std_field_id = f"{section_num}{field_number.zfill(2)}"

            # Extract field text
            field = self._extract_text(field_cell)
            value = self._extract_text(value_cell)
            alt_value = self._extract_text(alt_value_cell) if alt_value_cell else None
            
            # Skip empty rows
            if not field or (not value and not alt_value):
                continue
                
            # Clean up the field and value
            field = field.strip()
            value = value.strip() if value else None
            
            # Skip header rows or empty content
            if not field or field.lower() in ['field', 'item', 'description']:
                continue
                
            # Create data structure
            data = {
                'ident': icao,
                'section': section,
                'std_field_id': std_field_id,
                'field': field,
                'value': value,
                'alt_field': None,
                'alt_value': alt_value.strip() if alt_value else None
            }
            
            rv.append(data)
            
        return rv
    
    def _parse_procedure_table(self, table, section: str, icao: str) -> List[Dict[str, Any]]:
        """
        Parse a procedure table element and extract structured data.
        
        Args:
            table: BeautifulSoup table element
            section: Section name (procedures)
            icao: ICAO airport code
            
        Returns:
            List of dictionaries containing parsed procedure data
        """
        rv = []
        parser = ProcedureParserFactory.get_parser('EGC')
        
        # Find all rows in the table
        rows = table.find_all('tr')
        
        for row in rows:
            # Find all cells in the row
            cells = row.find_all(['td', 'th'])
            
            if len(cells) < 1:
                continue
                
            # Extract text from cells
            procedure_cell = cells[0] if len(cells) > 0 else None
            
            # Extract text content
            procedure = self._extract_text(procedure_cell)
            # Clean up the procedure name
            procedure = procedure.strip()
            
            # Skip rows that are of the kind "AD 2.*" (these are section headers)
            if procedure.startswith('AD 2.'):
                continue
                
            # Skip header rows or empty content
            parsed = parser.parse(procedure, icao)
            if parsed:
                rv.append(parsed)
            
        return rv
    
    def _extract_text(self, element) -> str:
        """
        Extract text content from a BeautifulSoup element.
        
        Args:
            element: BeautifulSoup element
            
        Returns:
            Extracted text string
        """
        if element is None:
            return ""
            
        # Get text content and clean it up
        text = element.get_text(separator=' ', strip=True)
        
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text)
        
        return text.strip() 