"""
Border Crossing Parser for extracting airport names from HTML tables.

This parser is designed to extract airport names from HTML documents that contain
numbered lists in the format "(number) airport name" in table format. It handles unicode and special characters.

Source 
https://eur-lex.europa.eu/legal-content/EN/TXT/HTML/?uri=CELEX:52023XC0609(06)
or
https://eur-lex.europa.eu/legal-content/EN/TXT/PDF/?uri=CELEX:52023XC0609(06)
"""

import re
import logging
from typing import Dict, List, Any, Set
from bs4 import BeautifulSoup
from .aip_base import AIPParser

logger = logging.getLogger(__name__)

class BorderCrossingParser(AIPParser):
    """
    Parser for extracting border crossing/immigration airport names from HTML tables.
    
    This parser looks for tables with rows containing numbered entries in the format
    "(number) Airport Name" and extracts the airport names. It's designed to handle
    unicode characters and special characters from various languages.
    """
    
    def __init__(self):
        """Initialize the BorderCrossingParser."""
        super().__init__()
        
        # Regex pattern to match numbered entries: (number) followed by text
        # This pattern handles:
        # - Numbers in parentheses: (1), (2), (123), etc.
        # - Unicode word characters: letters, numbers, spaces, hyphens, apostrophes
        # - Special characters common in airport names
        self.pattern = re.compile(
            r'\(\d+\)',
            re.UNICODE | re.MULTILINE
        )
        
        # Alternative patterns for different formats
        self.alternative_patterns = [
            # Pattern for "number) text" (without opening parenthesis)
            re.compile(r'\d+\)', re.UNICODE | re.MULTILINE),
            # Pattern for "number. text" (period instead of parenthesis)
            re.compile(r'\d+\.', re.UNICODE | re.MULTILINE),
            # Pattern for "number - text" (dash separator)
            re.compile(r'\d+\s*-\s*', re.UNICODE | re.MULTILINE),
        ]

    def _extract_names_from_text(self, text: str) -> Set[str]:
        """
        Extract airport names from text using regex patterns.
        
        Args:
            text: Text content to search in
            
        Returns:
            Set of extracted airport names
        """
        names = set()
        
        # Try the main pattern first
        matches = self.pattern.findall(text)
        for match in matches:
            name = match.strip()
            if name and len(name) > 2:  # Filter out very short matches
                names.add(name)
        
        # Try alternative patterns if main pattern didn't find much
        if len(names) < 5:  # If we found very few matches, try alternatives
            for pattern in self.alternative_patterns:
                matches = pattern.findall(text)
                for match in matches:
                    name = match.strip()
                    if name and len(name) > 2:
                        names.add(name)
        
        return names

    def _extract_names_from_table_row(self, row) -> Set[str]:
        """
        Extract airport names from a single table row.
        
        Args:
            row: BeautifulSoup row element
            
        Returns:
            Set of extracted airport names
        """
        names = set()
        
        # Get all cells in the row
        cells = row.find_all(['td', 'th'])
        
        # Check if this row has exactly 2 columns
        if len(cells) == 2:
            first_cell_text = cells[0].get_text(strip=True)
            second_cell_text = cells[1].get_text(strip=True)
            
            # Check if first column contains a number in parentheses
            if self.pattern.match(first_cell_text) or any(pattern.match(first_cell_text) for pattern in self.alternative_patterns):
                # Extract name from second column
                name = second_cell_text.strip()
                if name and len(name) > 2:
                    names.add(name)
                    logger.debug(f"Found airport name: {name}")
        
        return names

    def _extract_names_from_table(self, table) -> Set[str]:
        """
        Extract airport names from a single table.
        
        Args:
            table: BeautifulSoup table element
            
        Returns:
            Set of extracted airport names
        """
        names = set()
        
        # Get all rows in the table
        rows = table.find_all('tr')
        
        for row in rows:
            row_names = self._extract_names_from_table_row(row)
            names.update(row_names)
        
        return names

    def parse(self, html_data: bytes, icao: str) -> List[Dict[str, Any]]:
        """
        Parse HTML data to extract border crossing airport names.
        
        Args:
            html_data: Raw HTML data
            icao: ICAO airport code (not used in this parser)
            
        Returns:
            List of dictionaries containing extracted airport names
        """
        logger.info(f"Parsing border crossing data for {icao}")
        
        # Parse HTML with BeautifulSoup
        soup = BeautifulSoup(html_data, 'html.parser')
        
        # Find all tables in the HTML
        tables = soup.find_all('table')
        
        if not tables:
            logger.warning("No tables found in HTML")
            # Fallback to text extraction if no tables found
            text = soup.get_text()
            names = self._extract_names_from_text(text)
        else:
            # Extract names from all tables
            names = set()
            for i, table in enumerate(tables):
                logger.debug(f"Processing table {i+1}/{len(tables)}")
                table_names = self._extract_names_from_table(table)
                names.update(table_names)
                logger.debug(f"Found {len(table_names)} names in table {i+1}")
        
        # Convert to list and sort for consistent output
        airport_names = sorted(list(names))
        
        logger.info(f"Extracted {len(airport_names)} airport names")
        
        # Return as list of dictionaries for consistency with other parsers
        result = []
        for name in airport_names:
            result.append({
                'airport_name': name,
                'source': 'border_crossing_parser',
                'icao': icao,  # The ICAO code this was parsed for
                'extraction_method': 'html_table_parsing'
            })
        
        return result

    def get_supported_authorities(self) -> List[str]:
        """
        Get list of supported authority codes.
        
        This parser is designed for border crossing documents from various authorities.
        
        Returns:
            List of authority codes
        """
        return ['BORDER_CROSSING', 'IMMIGRATION', 'CUSTOMS']

    def extract_airport_names_only(self, html_data: bytes) -> List[str]:
        """
        Extract only the airport names as a simple list.
        
        This is a convenience method for when you only need the names.
        
        Args:
            html_data: Raw HTML data
            
        Returns:
            List of airport names
        """
        parsed_data = self.parse(html_data, "UNKNOWN")
        return [item['airport_name'] for item in parsed_data]

    def extract_airport_names_with_metadata(self, html_data: bytes, icao: str) -> Dict[str, Any]:
        """
        Extract airport names with additional metadata.
        
        Args:
            html_data: Raw HTML data
            icao: ICAO airport code
            
        Returns:
            Dictionary containing names and metadata
        """
        parsed_data = self.parse(html_data, icao)
        
        return {
            'icao': icao,
            'airport_names': [item['airport_name'] for item in parsed_data],
            'total_count': len(parsed_data),
            'source': 'border_crossing_parser',
            'raw_data': parsed_data
        } 