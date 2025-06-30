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
from .base import SourceInterface
from ..models.euro_aip_model import EuroAipModel

logger = logging.getLogger(__name__)

class PointDePassageJournalOfficielSource(SourceInterface):
    """
    A source that parses Points de Passage information from Journal Officiel PDFs.
    
    This source reads a PDF file and extracts airport names that are
    designated as Points de Passage. It then matches these names against
    existing airports in the model to set the point_of_entry flag.
    
    The source PDF should be downloaded from:
    https://www.legifrance.gouv.fr/jorf/id/JORFTEXT000043547009
    
    This is the official Journal Officiel de la République Française (JORF)
    document that lists all designated Points de Passage airports in France.
    The document contains a numbered list of airports, with each entry
    formatted as "(number) airport name, additional information".
    """
    
    def __init__(self, pdf_path: str):
        """
        Initialize the source.
        
        Args:
            pdf_path: Path to the Journal Officiel PDF file. The PDF should be
                     downloaded from https://www.legifrance.gouv.fr/jorf/id/JORFTEXT000043547009
        """
        self.pdf_path = Path(pdf_path)
        if not self.pdf_path.exists():
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")
            
        self._points_de_passage_names: Set[str] = set()
        self._processed = False

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

    def _extract_points_de_passage_names(self) -> Set[str]:
        """
        Extract Points de Passage airport names from the PDF.
        
        Returns:
            Set[str]: Set of airport names from the PDF
        """
        if not self._processed:
            # Extract text from PDF
            text = self._extract_text_from_pdf()
            
            # Find airport patterns
            self._points_de_passage_names = self._find_airport_patterns(text)
            self._processed = True
            
        return self._points_de_passage_names

    def _is_airport_match(self, pdf_name: str, airport_name: str) -> bool:
        """
        Check if an airport name from the PDF matches an airport in the model.
        
        Uses fuzzy matching to handle variations in naming.
        
        Args:
            pdf_name: Airport name from the PDF
            airport_name: Airport name from the model
            
        Returns:
            bool: True if the names match
        """
        # Direct match
        if pdf_name.lower() == airport_name.lower():
            return True
            
        # Check if PDF name is contained in airport name
        if pdf_name.lower() in airport_name.lower():
            return True
            
        # Check if airport name is contained in PDF name
        if airport_name.lower() in pdf_name.lower():
            return True
            
        # Simplified match (remove spaces and hyphens)
        simplified_pdf = pdf_name.replace(' ', '').replace('-', '').lower()
        simplified_airport = airport_name.replace(' ', '').replace('-', '').lower()
        
        if simplified_pdf in simplified_airport or simplified_airport in simplified_pdf:
            return True
            
        # Fuzzy match using word parts
        pdf_words = [x for x in re.split('[- ]+', pdf_name) if len(x) > 3]
        airport_words = [x for x in re.split('[- ]+', airport_name) if len(x) > 3]
        
        # Count matching words
        matches = 0
        for pdf_word in pdf_words:
            for airport_word in airport_words:
                if pdf_word.lower() in airport_word.lower() or airport_word.lower() in pdf_word.lower():
                    matches += 1
                    break
        
        # If more than half the words match, consider it a match
        if matches > 0 and matches >= min(len(pdf_words), len(airport_words)) / 2:
            return True
            
        # Special cases
        if 'Tavaux' in pdf_name and 'Dole' in airport_name:
            return True
            
        return False

    def update_model(self, model: EuroAipModel, airports: Optional[List[str]] = None) -> None:
        """
        Update the EuroAipModel with Points de Passage data.
        
        This method:
        1. Extracts airport names from the PDF
        2. Matches them against existing airports in the model
        3. Sets the point_of_entry flag to True for matching airports
        
        Args:
            model: The EuroAipModel to update
            airports: Optional list of specific airports to process. If None, 
                     processes all airports in the model.
        """
        logger.info(f"Updating model with Points de Passage data from {self.pdf_path}")
        
        # Extract Points de Passage names from PDF
        pdf_airport_names = self._extract_points_de_passage_names()
        logger.info(f"Found {len(pdf_airport_names)} Points de Passage airports in PDF")
        
        # Determine which airports to process
        airports_to_process = airports if airports is not None else list(model.airports.keys())
        
        # Track matches for logging
        matches_found = 0
        
        # Process each airport in the model
        for icao in airports_to_process:
            if icao not in model.airports:
                continue
                
            airport = model.airports[icao]
            
            # Check if this airport matches any name from the PDF
            for pdf_name in pdf_airport_names:
                if self._is_airport_match(pdf_name, airport.name or ''):
                    # Set point_of_entry flag
                    airport.point_of_entry = True
                    airport.add_source(self.get_source_name())
                    matches_found += 1
                    logger.debug(f"Matched '{pdf_name}' to airport {icao} ({airport.name})")
                    break
        
        logger.info(f"Updated {matches_found} airports with Points de Passage designation")
        
        # Log unmatched PDF names for debugging
        unmatched = []
        for pdf_name in pdf_airport_names:
            matched = False
            for icao in airports_to_process:
                if icao in model.airports:
                    airport = model.airports[icao]
                    if self._is_airport_match(pdf_name, airport.name or ''):
                        matched = True
                        break
            if not matched:
                unmatched.append(pdf_name)
        
        if unmatched:
            logger.warning(f"Could not match {len(unmatched)} Points de Passage airports: {unmatched[:10]}...")

    def find_available_airports(self) -> List[str]:
        """
        Find all available airports that this source can process.
        
        Since this source only sets flags on existing airports, it doesn't
        discover new airports, so it returns an empty list.
        
        Returns:
            Empty list (this source doesn't discover airports)
        """
        return []

    def get_points_de_passage(self) -> List[str]:
        """
        Get the list of Points de Passage airport names from the PDF.
        
        This method is kept for backward compatibility.
        
        Returns:
            List[str]: List of airport names from the PDF
        """
        return sorted(list(self._extract_points_de_passage_names())) 