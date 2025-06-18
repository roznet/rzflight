import re
import logging
from typing import List, Dict, Any, Optional
from bs4 import BeautifulSoup
from .aip_base import AIPParser

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
        
        rv = []
        
        # Look for div elements with pattern {ICAO}-AD-2.[0-9]
        pattern = f"{icao}-AD-2\\.([0-9])"
        div_elements = soup.find_all('div', id=re.compile(pattern))
        
        logger.debug(f"Found {len(div_elements)} div elements for {icao}")
        
        # Map section numbers to section names
        section_mapping = {
            '2': 'admin',
            '3': 'operational', 
            '4': 'handling',
            '5': 'passenger'
        }
        
        for div in div_elements:
            # Extract section number from ID
            match = re.search(pattern, div.get('id', ''))
            if not match:
                continue
                
            section_num = match.group(1)
            section_name = section_mapping.get(section_num)
            
            if not section_name:
                continue
                
            logger.debug(f"Processing section {section_num} ({section_name}) for {icao}")
            
            # Find all tables in this div
            tables = div.find_all('table')
            
            for table in tables:
                table_data = self._parse_table(table, section_name, icao)
                rv.extend(table_data)
        
        return rv
    
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
        
        # Find all rows in the table
        rows = table.find_all('tr')
        
        for row in rows:
            # Find all cells in the row
            cells = row.find_all(['td', 'th'])
            
            if len(cells) < 3:
                continue
                
            # Extract text from cells, handling potential None values
            field_cell = cells[1] if len(cells) > 0 else None
            value_cell = cells[2] if len(cells) > 1 else None
            alt_value_cell = cells[3] if len(cells) > 3 else None
            
            # Extract text content
            field = self._extract_text(field_cell)
            value = self._extract_text(value_cell)
            alt_value = self._extract_text(alt_value_cell) if alt_value_cell else None
            
            # Skip empty rows
            if not field or not value:
                continue
                
            # Clean up the field and value
            field = field.strip()
            value = value.strip()
            
            # Skip header rows or empty content
            if not field or field.lower() in ['field', 'item', 'description']:
                continue
                
            # Create data structure
            data = {
                'ident': icao,
                'section': section,
                'field': field,
                'value': value,
                'alt_field': None,
                'alt_value': alt_value if alt_value else None
            }
            
            rv.append(data)
            
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