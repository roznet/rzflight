import csv
import re
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any
import logging

from .fuzzy_matcher import FuzzyMatcher

logger = logging.getLogger(__name__)

class FieldMapper:
    """Maps AIP parsed fields to standard fields using fuzzy matching."""
    
    def __init__(self, csv_path: str = None):
        """
        Initialize the field mapper with standard field definitions.
        
        Args:
            csv_path: Path to the aip_fields.csv file
        """
        if csv_path is None:
            # Default to the example directory - go up from utils to euro_aip to project root
            csv_path = Path(__file__).parent / "aip_fields.csv"
        
        self.standard_fields = self._load_standard_fields(csv_path)
        self.field_cache = {}  # Cache for normalized field names
        self.fuzzy_matcher = FuzzyMatcher()  # Use the shared fuzzy matcher
    
    def _safe_int_convert(self, value) -> Optional[int]:
        """
        Convert value to int if possible, otherwise return None.
        
        Args:
            value: Value to convert
            
        Returns:
            Integer value or None if conversion fails
        """
        if value is None or value == '':
            return None
        try:
            return int(str(value).strip())
        except (ValueError, TypeError):
            return None
    
    def _load_standard_fields(self, csv_path: str) -> Dict[str, Dict]:
        """
        Load standard field definitions from CSV.
        
        Args:
            csv_path: Path to the CSV file
            
        Returns:
            Dictionary mapping section -> field_id -> field_info
        """
        standard_fields = {}
        
        try:
            # Use utf-8-sig to handle BOM automatically
            with open(csv_path, 'r', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f)
                
                for row in reader:
                    section = row['section']
                    field_id = self._safe_int_convert(row['field_id'])
                    field_aip_id = self._safe_int_convert(row['field_aip_id'])
                    field_name = row['field_name']
                    
                    standard_fields[field_id] = {
                        'field_id': field_id,
                        'field_aip_id': field_aip_id,
                        'field_name': field_name,
                        'section': section,
                    }
        except FileNotFoundError:
            logger.warning(f"Standard fields CSV not found at {csv_path}")
            standard_fields = {}
        except Exception as e:
            logger.error(f"Error loading CSV: {e}")
            standard_fields = {}
        
        return standard_fields
    
    def find_best_match(self, field_name: str, section: str = None, field_aip_id: str = None, 
                       threshold: float = 0.5) -> Optional[Tuple[str, str, float]]:
        """
        Find the best matching standard field for a given field name.
        
        Args:
            field_name: The field name from AIP parsing
            section: The section name (admin, operational, handling, passenger) or None to search all sections
            field_aip_id: Optional standard field ID if available (can be str or int)
            threshold: Minimum similarity score to consider a match
            
        Returns:
            Tuple of (field_id, field_name, similarity_score) or None if no match found
        """
        # Convert field_aip_id to int if it's a string
        field_aip_id_int = self._safe_int_convert(field_aip_id)
        
        # First, try exact match with field_aip_id if provided
        if field_aip_id_int is not None:
            for field_id, field_info in self.standard_fields.items():
                if field_info['field_aip_id'] == field_aip_id_int:
                    return (field_id, field_info['field_name'], 1.0)
        
        # Then try fuzzy matching with field names
        candidates = []
        for field_id, field_info in self.standard_fields.items():
            # Skip if section is specified and doesn't match
            if section is not None and field_info['section'] != section:
                continue
            candidates.append((field_id, field_info['field_name']))
        
        # Use the fuzzy matcher to find the best match
        result = self.fuzzy_matcher.find_best_match_with_id(field_name, candidates, threshold)
        
        if result:
            field_id, matched_field_name, score = result
            return (field_id, matched_field_name, score)
        
        return None
    
    def map_field(self, field_name: str, section: str = None, field_aip_id: str = None,
                  threshold: float = 0.6) -> Dict:
        """
        Map a field to standard field information.
        
        Args:
            field_name: The field name from AIP parsing
            section: The section name (admin, operational, handling, passenger) or None to search all sections
            field_aip_id: Optional standard field ID
            threshold: Minimum similarity score
            
        Returns:
            Dictionary with mapping information
        """
        match = self.find_best_match(field_name, section, field_aip_id, threshold)
        
        if match:
            field_id, mapped_field_name, score = match
            # Get the field info to find the section
            field_info = self.standard_fields[field_id]
            found_section = field_info['section']
            
            return {
                'original_field': field_name,
                'section': found_section,
                'mapped_field_id': field_id,
                'mapped_field_name': mapped_field_name,
                'similarity_score': score,
                'field_aip_id': field_info['field_aip_id'],
                'mapped': True
            }
        else:
            return {
                'original_field': field_name,
                'section': section,
                'mapped_field_id': None,
                'mapped_field_name': None,
                'similarity_score': 0.0,
                'field_aip_id': None,
                'mapped': False
            }
    
    def standardise_fields(self, records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Standardise a list of fields by mapping them to standard fields. Will only return a list of records that were mapped.
        """
        standardised_fields = []
        for record in records:
            mapped_record = self.map_field(record['field'])
            if mapped_record['mapped']:
                standardised_record = record.copy()
                standardised_record['field_id'] = mapped_record['mapped_field_id'] 
                standardised_record['field'] = mapped_record['mapped_field_name']
                standardised_record['section'] = mapped_record['section']
                standardised_fields.append(standardised_record)
        return standardised_fields

    def get_field_for_id(self, field_id: int) -> Optional[Dict[str, Any]]:
        """
        Get the field for a given standard field ID.
        
        Args:
            field_aip_id: The standard field ID to search for
            
        Returns:
            Field information dictionary or None if not found
        """
        for field_id, field_info in self.standard_fields.items():
            if field_info['field_id'] == field_id:
                return field_info
        return None