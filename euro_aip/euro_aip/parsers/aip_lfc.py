from typing import List, Dict, Any, Optional
import re
import logging
from bs4 import BeautifulSoup
from .aip_default import DefaultAIPParser
from .aip_base import AIPParser
from .procedure_factory import ProcedureParserFactory

class LFCAIPParser(DefaultAIPParser):
    """Parser for France (LFC) AIP documents."""
    
    PREFERRED_PARSER = 'camelot_lattice'  # Use pdfplumber for better table extraction
    
    # Custom table settings for France AIP documents
    TABLE_SETTINGS = {
        'vertical_strategy': 'lines',  # Use lines for vertical detection
        'horizontal_strategy': 'lines',  # Use lines for horizontal detection
        'snap_tolerance': 5,  # More lenient line snapping
        'join_tolerance': 3,  # Standard text joining
        'edge_min_length': 2,  # Consider shorter lines
        'min_words_vertical': 2,  # Fewer words needed for vertical lines
        'min_words_horizontal': 1  # Standard horizontal word requirement
    }

    FIELD_INDEX = 1
    VALUE_INDEX = 2
    ALT_VALUE_INDEX = 3
    FIELD_SEPARATOR = r' / |\n'

    def get_supported_authorities(self) -> List[str]:
        """Get list of supported authority codes."""
        return ['LFC']
    
    def parse(self, pdf_data: bytes, icao: str) -> List[Dict[str, Any]]:
        """
        Parse Belgium AIP document data.
        
        Args:
            pdf_data: Raw PDF data
            icao: ICAO airport code
            
        Returns:
            List of dictionaries containing parsed data
        """
        # Use the default parser's implementation
        return super().parse(pdf_data, icao) 


logger = logging.getLogger(__name__)


class LFCHTMLParser(AIPParser):
    """HTML parser for France (LFC) eAIP documents."""

    def get_supported_authorities(self) -> List[str]:
        return ['LFC']

    def parse(self, html_data: bytes, icao: str) -> List[Dict[str, Any]]:
        """
        Parse France AIP HTML document data into standardized field rows.

        Focuses on AD 2 sections 2..5 mapped to admin/operational/handling/passenger.
        """
        html_content = html_data.decode('utf-8', errors='ignore')
        soup = BeautifulSoup(html_content, 'html.parser')

        section_mapping = {
            '2': 'admin',
            '3': 'operational',
            '4': 'handling',
            '5': 'passenger',
        }

        tables = self._extract_tables_from_sections(soup, icao, section_mapping)

        results: List[Dict[str, Any]] = []
        for item in tables:
            table = item['table']
            section = item['section']
            results.extend(self._parse_table(table, section, icao))

        return results

    def _extract_tables_from_sections(self, soup: BeautifulSoup, icao: str, section_mapping: Dict[str, str]) -> List[Dict[str, Any]]:
        tables = []
        # France HTML commonly uses div ids like "LFAQ-AD-2.2", "LFAQ-AD-2.3", etc.
        for section_num in section_mapping.keys():
            pattern = f"{icao}-AD-2\\.{section_num}"
            div_elements = soup.find_all('div', id=re.compile(pattern))
            logger.debug(f"[LFC HTML] Found {len(div_elements)} divs for {icao} section {section_num}")
            for div in div_elements:
                div_tables = div.find_all('table')
                for table in div_tables:
                    tables.append({'table': table, 'section': section_mapping[section_num]})
        return tables

    def _parse_table(self, table, section: str, icao: str) -> List[Dict[str, Any]]:
        rows = table.find_all('tr')
        out: List[Dict[str, Any]] = []
        
        # Map section names to numbers for std_field_id construction
        section_number_map = {
            'admin': '2',
            'operational': '3', 
            'handling': '4',
            'passenger': '5'
        }
        section_num = section_number_map.get(section, '2')
        
        for row in rows:
            cells = row.find_all(['td', 'th'])
            if len(cells) < 2:
                continue

            # France tables structure:
            # - col0: field number (for std_field_id construction)
            # - col1: field (FR/EN label, may contain <span class="foreign">)
            # - col2+: value(s) (FR and/or EN)
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

            # Extract field text and check for foreign language spans
            field = self._extract_text(field_cell)
            alt_field = self._extract_foreign_text(field_cell)
            
            # Clean up field text by removing alt_field content
            if alt_field:
                # Remove "/ {alt_field}" pattern if present
                if f"/ {alt_field}" in field:
                    field = field.replace(f"/ {alt_field}", "").rstrip()
                # Remove alt_field if it appears at the end of field
                elif field.endswith(alt_field):
                    field = field[:-len(alt_field)].rstrip()
            
            value = self._extract_text(value_cell)
            alt_value = self._extract_text(alt_value_cell) if alt_value_cell else None

            if not field or (not value and not alt_value):
                continue

            # Skip generic header-like rows
            lowered = field.lower()
            if lowered in ['field', 'item', 'description']:
                continue

            out.append({
                'ident': icao,
                'section': section,
                'std_field_id': std_field_id,
                'field': field.strip(),
                'value': value.strip() if value else None,
                'alt_field': alt_field.strip() if alt_field else None,
                'alt_value': alt_value.strip() if alt_value else None,
            })

        return out

    def _extract_text(self, element) -> str:
        if element is None:
            return ""
        text = element.get_text(separator=' ', strip=True)
        text = re.sub(r'\s+', ' ', text)
        return text.strip()

    def _extract_foreign_text(self, element) -> Optional[str]:
        """Extract text from <span class="foreign"> elements within the given element."""
        if element is None:
            return None
        
        foreign_spans = element.find_all('span', class_='foreign')
        if not foreign_spans:
            return None
            
        # Extract text from all foreign spans and join them
        foreign_texts = []
        for span in foreign_spans:
            text = span.get_text(separator=' ', strip=True)
            if text:
                foreign_texts.append(text)
        
        if foreign_texts:
            combined_text = ' '.join(foreign_texts)
            combined_text = re.sub(r'\s+', ' ', combined_text)
            return combined_text.strip()
        
        return None

    def extract_procedures(self, html_data: bytes, icao: str) -> List[Dict[str, Any]]:
        """
        Extract procedures from France AIP HTML document data.

        Strategy: find links to procedure PDFs in the Cartes section for the ICAO
        and parse their link text via the LFC procedure parser.
        """
        html_content = html_data.decode('utf-8', errors='ignore')
        soup = BeautifulSoup(html_content, 'html.parser')

        parser = ProcedureParserFactory.get_parser('LFC')
        results: List[Dict[str, Any]] = []

        # Find chart links referencing this ICAO (relative paths like "Cartes/LFAQ/..." )
        candidates = []
        for a in soup.find_all('a'):
            href = a.get('href')
            if not href:
                continue
            if f"Cartes/{icao}" in href:
                candidates.append(a)

        logger.debug(f"[LFC HTML] Found {len(candidates)} candidate chart links for {icao}")

        for a in candidates:
            heading = self._extract_text(a)
            if not heading:
                # fallback to filename stem without extension
                href = a.get('href') or ''
                heading = href.split('/')[-1].rsplit('.', 1)[0]
            if not heading:
                continue
            # Focus on instrument approach charts (IAC) or approach chart identifiers
            if 'IAC' not in heading and 'APPROACH' not in heading:
                continue
            parsed = parser.parse(heading, icao)
            if parsed:
                results.append(parsed)

        return results