"""
Source for parsing Points de Passage from Journal Officiel PDFs.

This source reads a PDF file containing Points de Passage information
and extracts airport ICAO codes that are designated as Points de Passage.

The source PDF can be downloaded from:
https://www.legifrance.gouv.fr/jorf/id/JORFTEXT000043547009

This is the official Journal Officiel de la République Française (JORF)
document that lists all designated Points de Passage airports in France.
"""

import re
import logging
from pathlib import Path
from typing import List, Set, Optional
from pdfminer.high_level import extract_text
from .database import DatabaseSource

logger = logging.getLogger(__name__)

class PointDePassageJournalOfficiel:
    """
    A source that parses Points de Passage information from Journal Officiel PDFs.
    
    This source reads a PDF file and extracts airport ICAO codes that are
    designated as Points de Passage. It uses a database source to validate
    the extracted airport codes.
    
    The source PDF should be downloaded from:
    https://www.legifrance.gouv.fr/jorf/id/JORFTEXT000043547009
    
    This is the official Journal Officiel de la République Française (JORF)
    document that lists all designated Points de Passage airports in France.
    The document contains a numbered list of airports, with each entry
    formatted as "(number) airport name, additional information".
    """
    
    def __init__(self, pdf_path: str, database_source: DatabaseSource):
        """
        Initialize the source.
        
        Args:
            pdf_path: Path to the Journal Officiel PDF file. The PDF should be
                     downloaded from https://www.legifrance.gouv.fr/jorf/id/JORFTEXT000043547009
            database_source: DatabaseSource instance for airport validation
        """
        self.pdf_path = Path(pdf_path)
        if not self.pdf_path.exists():
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")
            
        self.database = database_source
        self._airports: Set[str] = set()

    def _extract_text_from_pdf(self) -> str:
        """
        Extract text content from the PDF file using pdf2txt.
        
        Returns:
            str: Extracted text content
        """
        try:
            return extract_text(str(self.pdf_path))
        except Exception as e:
            logger.error(f"Error extracting text from PDF: {e}")
            raise

    def _find_airport_patterns(self, text: str) -> Set[str]:
        """
        Find airport patterns in the text.
        
        The pattern looks for text like "(1) name of airport, etc"
        and extracts the airport name. Processes the text line by line
        to better handle the document structure.
        
        Args:
            text: Text content to search in
            
        Returns:
            Set[str]: Set of found airport names
        """
        # Pattern to match airport entries
        pattern = r'\(\d+\)\s+([^,]+)'
        airports = set()
        
        # Process text line by line
        for line in text.split('\n'):
            line = line.strip()
            if not line:
                continue
                
            match = re.search(pattern, line)
            if match:
                airport_name = match.group(1).strip()
                if airport_name:
                    airports.add(airport_name)
                
        return airports

    def _validate_airports(self, airport_names: Set[str]) -> Set[str]:
        """
        Validate airport names against the database using fuzzy matching.
        
        Args:
            airport_names: Set of airport names to validate
            
        Returns:
            Set[str]: Set of valid ICAO codes
        """
        valid_icao_codes = set()
        
        # First, build a map of all French airports
        airport_map = {}
        with self.database.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT ident, name FROM airports WHERE ident LIKE 'LF%'")
            for row in cursor.fetchall():
                airport_map[row['name']] = {'ident': row['ident'], 'name': row['name']}

        def find_ident(name: str) -> Optional[dict]:
            # Direct match
            for k in airport_map:
                if name in k:
                    return airport_map[k]

            # Simplified match (remove spaces and hyphens)
            simplified = name.replace(' ', '').replace('-', '')
            for k in airport_map:
                simplifiedk = k.replace(' ', '').replace('-', '')
                if simplified in simplifiedk:
                    return airport_map[k]

            # Fuzzy match using word parts
            subs = [x for x in re.split('[- ]+', name) if len(x) > 3]
            maxfound = 0
            found = None
            for k in airport_map:
                count = 0
                for sub in subs:
                    if sub in k:
                        count += 1
                if count > maxfound:
                    found = airport_map[k]
                    maxfound = count

            return found

        # Process each airport name
        for name in airport_names:
            found = find_ident(name)
            if not found and 'Tavaux' in name:
                found = find_ident('Dole-Jura')
            if found:
                valid_icao_codes.add(found['ident'])
            else:
                logger.warning(f"Airport not found in database: {name}")
                    
        return valid_icao_codes

    def get_points_de_passage(self) -> List[str]:
        """
        Get the list of Points de Passage airports.
        
        Returns:
            List[str]: List of ICAO codes for Points de Passage airports
        """
        if not self._airports:
            # Extract text from PDF
            text = self._extract_text_from_pdf()
            
            # Find airport patterns
            airport_names = self._find_airport_patterns(text)
            
            # Validate against database
            self._airports = self._validate_airports(airport_names)
            
        return sorted(list(self._airports)) 