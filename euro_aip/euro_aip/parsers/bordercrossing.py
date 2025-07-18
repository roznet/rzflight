"""
Border Crossing Parser for extracting airport names from HTML tables.

This parser is designed to extract airport names from HTML documents that contain
numbered lists in the format "(number) airport name" in table format. It handles unicode and special characters.

The parser tracks country sections, paragraph metadata, and maintains context
for each airport entry including country, paragraph styles, and formatting.

Source 
https://eur-lex.europa.eu/legal-content/EN/TXT/HTML/?uri=CELEX:52023XC0609(06)
or
https://eur-lex.europa.eu/legal-content/EN/TXT/PDF/?uri=CELEX:52023XC0609(06)
"""

import re
import logging
from typing import Dict, List, Any, Set, Optional
from bs4 import BeautifulSoup, Tag
from .aip_base import AIPParser

logger = logging.getLogger(__name__)

class BorderCrossingParser(AIPParser):
    """
    Parser for extracting border crossing/immigration airport names from HTML tables.
    
    This parser looks for tables with rows containing numbered entries in the format
    "(number) Airport Name" and extracts the airport names. It tracks country sections,
    paragraph metadata, and maintains context for each airport entry.
    """
    
    def __init__(self):
        """Initialize the BorderCrossingParser."""
        super().__init__()
        
        # Regex pattern to match numbered entries: (number)
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
        
        # Pattern to detect country names (all uppercase words)
        self.country_pattern = re.compile(r'^[A-Z\s]+$', re.UNICODE)
        
        # Common country names to validate
        self.known_countries = {
            'GERMANY', 'FRANCE', 'ITALY', 'SPAIN', 'NETHERLANDS', 'BELGIUM', 'AUSTRIA',
            'SWITZERLAND', 'DENMARK', 'SWEDEN', 'NORWAY', 'FINLAND', 'POLAND',
            'CZECH REPUBLIC', 'SLOVAKIA', 'HUNGARY', 'ROMANIA', 'BULGARIA',
            'GREECE', 'PORTUGAL', 'IRELAND', 'LUXEMBOURG', 'SLOVENIA', 'CROATIA',
            'LATVIA', 'LITHUANIA', 'ESTONIA', 'MALTA', 'CYPRUS'
        }

    def _is_country_name(self, text: str) -> bool:
        """
        Check if text represents a country name.
        
        Args:
            text: Text to check
            
        Returns:
            True if text is a country name
        """
        text = text.strip()
        
        logger.debug(f"Checking if '{text}' is a country name")
        
        # Check if it matches the pattern for all uppercase
        if not self.country_pattern.match(text):
            logger.debug(f"  - Does not match uppercase pattern")
            return False
        
        # Check if it's a known country
        if text in self.known_countries:
            logger.debug(f"  - Found in known countries list")
            return True
        
        
        return False

    def _extract_paragraph_metadata(self, element: Tag) -> Dict[str, Any]:
        """
        Extract metadata from a paragraph element.
        
        Args:
            element: BeautifulSoup element
            
        Returns:
            Dictionary containing paragraph metadata
        """
        text = element.get_text(strip=True)
        
        # Get classes from the main element
        element_classes = element.get('class', [])
        
        # Find all nested span elements and collect their classes
        span_classes = []
        for span in element.find_all('span'):
            span_class = span.get('class', [])
            if span_class:
                span_classes.extend(span_class)
        
        # Combine all classes (element + spans)
        all_classes = element_classes + span_classes
        
        metadata = {
            'text': text,
            'is_uppercase': text.isupper() if text else False,
            'is_lowercase': text.islower() if text else False,
            'is_title_case': text.istitle() if text else False,
            'tag_name': element.name,
            'classes': all_classes,  # All classes from element and nested spans
            'element_classes': element_classes,  # Classes from the main element only
            'span_classes': span_classes,  # Classes from nested spans only
            'id': element.get('id'),
        }
        
        return metadata

    def _extract_names_from_table_row(self, row: Tag, current_country: str, 
                                    current_metadata: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Extract airport names from a single table row.
        
        Args:
            row: BeautifulSoup row element
            current_country: Currently active country
            current_metadata: Current paragraph metadata
            
        Returns:
            List of dictionaries containing airport data
        """
        results = []
        
        # Get all cells in the row
        cells = row.find_all(['td', 'th'])
        
        # Check if this row has exactly 2 columns
        if len(cells) == 2:
            # Get text from first cell (number)
            first_cell = cells[0]
            first_cell_text = first_cell.get_text(strip=True)
            
            # Get text from second cell (airport name)
            second_cell = cells[1]
            second_cell_text = second_cell.get_text(strip=True)
            
            logger.debug(f"Processing row: '{first_cell_text}' -> '{second_cell_text}'")
            
            # Check if first column contains a number in parentheses
            if (self.pattern.match(first_cell_text) or 
                any(pattern.match(first_cell_text) for pattern in self.alternative_patterns)):
                
                # Extract the number from the first column
                number_match = re.search(r'\d+', first_cell_text)
                number = number_match.group() if number_match else first_cell_text
                
                # Extract name from second column
                name = second_cell_text.strip()
                if name and len(name) > 2:
                    # Check 1: Extract content in parentheses at the end of the name
                    comment = ""
                    # Pattern to match content in parentheses at the end of the string
                    parenthesis_pattern = r'^(.*?)\s*\(([^)]+)\)\s*$'
                    match = re.match(parenthesis_pattern, name)
                    
                    if match:
                        # Extract the name without parentheses and the comment
                        name = match.group(1).strip()
                        comment = match.group(2).strip()
                        logger.debug(f"Extracted comment from parentheses: '{comment}' for name: '{name}'")

                    # remove punctuation at the end of name
                    name = re.sub(r'[^\w\s]$', '', name)
                    
                    # Check 2: Look for airport/airfield/air border references in metadata
                    is_airport = False
                    airport_keywords = ['airport', 'airfield', 'air border']
                    
                    # Check in current metadata values
                    for key, value in current_metadata.items():
                        if isinstance(value, str):
                            value_lower = value.lower()
                            if any(keyword in value_lower for keyword in airport_keywords):
                                is_airport = True
                                logger.debug(f"Found airport reference in metadata '{key}': '{value}'")
                                break

                    metadata = {}
                    for key, value in current_metadata.items():
                        if not value.startswith('Replacement of'):
                            metadata[key] = value
                    metadata['is_airport'] = is_airport
                    metadata['comment'] = comment
                    
                    # Create result with enhanced metadata
                    result = {
                        'airport_name': name,
                        'country': current_country,
                        'number': number,
                        'source': 'border_crossing_parser',
                        'extraction_method': 'html_table_parsing',
                        'is_airport': is_airport,
                        'metadata': metadata,  # Copy current metadata
                        'row_data': {
                            'first_column': first_cell_text,
                            'second_column': second_cell_text
                        }
                    }
                    
                    # Add comment to metadata if it exists
                    if comment:
                        result['metadata']['comment'] = comment
                    else:
                        result['metadata']['comment'] = ""
                    
                    results.append(result)
                    logger.debug(f"Found airport: {name} in {current_country} (#{number}, is_airport: {is_airport}, comment: '{comment}')")
        
        return results

    def _extract_names_from_table(self, table: Tag, current_country: str, 
                                current_metadata: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Extract airport names from a single table.
        
        Args:
            table: BeautifulSoup table element
            current_country: Currently active country
            current_metadata: Current paragraph metadata
            
        Returns:
            List of dictionaries containing airport data
        """
        results = []
        
        # Get all rows in the table
        rows = table.find_all('tr')
        
        for row in rows:
            row_results = self._extract_names_from_table_row(row, current_country, current_metadata)
            results.extend(row_results)
        
        return results

    def parse(self, html_data: bytes, icao: str) -> List[Dict[str, Any]]:
        """
        Parse HTML data to extract border crossing airport names.
        
        Args:
            html_data: Raw HTML data
            icao: ICAO airport code (not used in this parser)
            
        Returns:
            List of dictionaries containing extracted airport names with metadata
        """
        logger.info(f"Parsing border crossing data for {icao}")
        
        # Parse HTML with BeautifulSoup
        soup = BeautifulSoup(html_data, 'html.parser')
        
        # Check if this is a UK govuk-template format
        if soup.find(class_='govuk-template'):
            logger.info("Detected UK govuk-template format, using UK parser")
            return self.parse_uk(html_data, icao)
        
        # Continue with existing EU format parsing
        logger.info("Using EU format parser")
        
        # Initialize tracking variables
        current_country = None
        current_metadata = {}
        current_metadata_keys = {}
        results = []
        
        # Find all elements in the document
        all_elements = soup.find_all(['p', 'table'])
        
        
        logger.info(f"Found {len(all_elements)} elements to process")
        
        for element in all_elements:
            try:
                # Check if this is a country name paragraph
                if element.name == 'p':
                    if element.find_parent('table'):
                        continue
                    text = element.get_text(strip=True)
                    logger.debug(f"Processing paragraph: '{text[:50]}...'")
                    
                    # Check if this is a country name
                    if self._is_country_name(text):
                        current_country = text
                        current_metadata = {}
                        current_metadata_keys = {}
                        logger.info(f"Found country section: {current_country}")
                        continue
                    
                    # Extract metadata for this paragraph
                    metadata = self._extract_paragraph_metadata(element)
                    
                    # Update current metadata based on style
                    class_key = "_".join(metadata['classes'])
                    style_key = f"{metadata['tag_name']}_{metadata['is_uppercase']}_{class_key}"
                    if style_key not in current_metadata_keys:
                        current_metadata_keys[style_key] = len(current_metadata_keys)
                    current_metadata[f'{current_metadata_keys[style_key]}'] = metadata['text']
                
                # Check if this is a table
                elif element.name == 'table':
                    if current_country:
                        logger.debug(f"Processing table in country: {current_country}")
                        table_results = self._extract_names_from_table(element, current_country, current_metadata)
                        results.extend(table_results)
                        logger.debug(f"Found {len(table_results)} airports in this table")
                    else:
                        logger.debug("Skipping table - no country context")
                
            except Exception as e:
                logger.warning(f"Error processing element {getattr(element, 'name', 'unknown')}: {e}")
                continue
        
        logger.info(f"Extracted {len(results)} airport names from {current_country or 'unknown'} countries")
        
        return results

    def parse_uk(self, html_data: bytes, icao: str) -> List[Dict[str, Any]]:
        """
        Parse UK format HTML data to extract border crossing airport names.
        
        Args:
            html_data: Raw HTML data
            icao: ICAO airport code (not used in this parser)
            
        Returns:
            List of dictionaries containing extracted airport names with metadata
        """
        logger.info(f"Parsing UK border crossing data for {icao}")
        
        # Parse HTML with BeautifulSoup
        soup = BeautifulSoup(html_data, 'html.parser')
        
        results = []
        
        # Find all tables
        tables = soup.find_all('table')
        logger.info(f"Found {len(tables)} tables to process")
        
        for table in tables:
            try:
                # Check if this table has 5 columns and first column header is "Airports"
                rows = table.find_all('tr')
                if len(rows) < 2:  # Need at least header and one data row
                    continue
                
                # Get header row
                header_row = rows[0]
                header_cells = header_row.find_all(['th', 'td'])
                
                # Check if we have 5 columns and first header is "Airports"
                if len(header_cells) != 5:
                    continue
                
                first_header = header_cells[0].get_text(strip=True)
                if first_header != "Airport":
                    continue
                
                logger.info(f"Found UK format table with 5 columns, first header: {first_header}")
                
                # Extract column headers (skip first one as it's "Airports")
                column_headers = []
                for i in range(1, len(header_cells)):
                    header_text = header_cells[i].get_text(strip=True)
                    column_headers.append(header_text)
                
                logger.info(f"Column headers: {column_headers}")
                
                # Process data rows (skip header row)
                for row in rows[1:]:
                    try:
                        cells = row.find_all(['td', 'th'])
                        if len(cells) != 5:
                            continue
                        
                        # Get airport name from first column
                        airport_cell = cells[0]
                        airport_text = airport_cell.get_text(strip=True)
                        
                        # Check if airport name contains ICAO code pattern
                        # Pattern: "some name - EG[A-Z0-9][A-Z0-9]"
                        import re
                        icao_pattern = r'(.+?)\s*-\s*(E[A-Z][A-Z0-9][A-Z0-9])'
                        match = re.search(icao_pattern, airport_text)
                        
                        if not match:
                            logger.debug(f"Skipping row with no ICAO code: {airport_text}")
                            continue
                        
                        airport_name = match.group(1).strip()
                        icao_code = match.group(2)
                        
                        logger.debug(f"Found airport: {airport_name} (ICAO: {icao_code})")
                        
                        # Collect metadata from other columns
                        metadata = {}
                        for i in range(1, len(cells)):
                            if i-1 < len(column_headers):
                                header_key = column_headers[i-1]
                                cell_value = cells[i].get_text(strip=True)
                                if cell_value:  # Only add non-empty values
                                    metadata[header_key] = cell_value

                        metadata['is_airport'] = True
                        metadata['comment'] = ""
                        
                        # Create result entry matching the format of the EU parser
                        result = {
                            'airport_name': airport_name,
                            'icao_code': icao_code,
                            'matched_airport_icao': icao_code,
                            'country': 'UNITED KINGDOM',
                            'source': 'border_crossing_parser_uk',
                            'extraction_method': 'uk_html_table_parsing',
                            'metadata': metadata,
                            'is_airport': True,
                            'row_data': {
                                'full_airport_text': airport_text,
                                'column_headers': column_headers,
                                'all_cell_values': [cell.get_text(strip=True) for cell in cells]
                            }
                        }
                        
                        results.append(result)
                        logger.debug(f"Added airport: {airport_name} ({icao_code})")
                        
                    except Exception as e:
                        logger.warning(f"Error processing row: {e}")
                        continue
                
            except Exception as e:
                logger.warning(f"Error processing table: {e}")
                continue
        
        logger.info(f"Extracted {len(results)} UK airport entries")
        return results

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