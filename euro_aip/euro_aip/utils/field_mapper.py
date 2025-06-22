import csv
import re
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any
from difflib import SequenceMatcher
import logging

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
                    field_id = row['field_id']
                    field_std_id = self._safe_int_convert(row['field_std_id'])
                    description = row['description']
                    
                    if section not in standard_fields:
                        standard_fields[section] = {}
                    
                    standard_fields[section][field_id] = {
                        'field_std_id': field_std_id,
                        'description': description,
                        'normalized_description': self._normalize_text(description)
                    }
        except FileNotFoundError:
            logger.warning(f"Standard fields CSV not found at {csv_path}")
            standard_fields = {}
        except Exception as e:
            logger.error(f"Error loading CSV: {e}")
            standard_fields = {}
        
        return standard_fields
    
    def _normalize_text(self, text: str) -> str:
        """
        Normalize text for comparison by removing special characters, 
        converting to lowercase, and standardizing whitespace.
        
        Args:
            text: Text to normalize
            
        Returns:
            Normalized text
        """
        if not text:
            return ""
        
        # Convert to lowercase
        text = text.lower()
        
        # Replace common separators with spaces
        text = re.sub(r'[/\-_]+', ' ', text)
        
        # Remove special characters but keep alphanumeric and spaces
        text = re.sub(r'[^\w\s]', ' ', text)
        
        # Normalize whitespace (multiple spaces to single space)
        text = re.sub(r'\s+', ' ', text)
        
        # Strip leading/trailing whitespace
        text = text.strip()
        
        return text
    
    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """
        Calculate similarity between two texts using multiple methods.
        
        Args:
            text1: First text
            text2: Second text
            
        Returns:
            Similarity score between 0 and 1
        """
        if not text1 or not text2:
            return 0.0
        
        # Normalize both texts
        norm1 = self._normalize_text(text1)
        norm2 = self._normalize_text(text2)
        
        if not norm1 or not norm2:
            return 0.0
        
        # Method 1: Sequence matcher (good for typos and minor differences)
        seq_similarity = SequenceMatcher(None, norm1, norm2).ratio()
        
        # Method 2: Word overlap (good for different word orders)
        words1 = set(norm1.split())
        words2 = set(norm2.split())
        
        if not words1 or not words2:
            word_similarity = 0.0
        else:
            intersection = words1.intersection(words2)
            union = words1.union(words2)
            word_similarity = len(intersection) / len(union) if union else 0.0
        
        # Method 3: Substring matching (good for partial matches)
        substring_similarity = 0.0
        if len(norm1) > 3 and len(norm2) > 3:
            if norm1 in norm2 or norm2 in norm1:
                substring_similarity = min(len(norm1), len(norm2)) / max(len(norm1), len(norm2))
        
        # Combine scores (weighted average)
        combined_score = (seq_similarity * 0.4 + word_similarity * 0.4 + substring_similarity * 0.2)
        
        return combined_score
    
    def find_best_match(self, field_name: str, section: str = None, field_std_id: str = None, 
                       threshold: float = 0.6) -> Optional[Tuple[str, str, float]]:
        """
        Find the best matching standard field for a given field name.
        
        Args:
            field_name: The field name from AIP parsing
            section: The section name (admin, operational, handling, passenger) or None to search all sections
            field_std_id: Optional standard field ID if available (can be str or int)
            threshold: Minimum similarity score to consider a match
            
        Returns:
            Tuple of (field_id, description, similarity_score) or None if no match found
        """
        best_match = None
        best_score = 0.0
        
        # Convert field_std_id to int if it's a string
        field_std_id_int = self._safe_int_convert(field_std_id)
        
        # Determine which sections to search
        sections_to_search = [section] if section is not None else list(self.standard_fields.keys())
        
        # First, try exact match with field_std_id if provided
        if field_std_id_int is not None:
            for search_section in sections_to_search:
                if search_section not in self.standard_fields:
                    continue
                    
                for field_id, field_info in self.standard_fields[search_section].items():
                    if field_info['field_std_id'] == field_std_id_int:
                        return (field_id, field_info['description'], 1.0)
        
        # Then try fuzzy matching with descriptions
        for search_section in sections_to_search:
            if search_section not in self.standard_fields:
                continue
                
            for field_id, field_info in self.standard_fields[search_section].items():
                # Try matching against the description
                score = self._calculate_similarity(field_name, field_info['description'])
                
                # Also try matching against the field_id itself
                score_id = self._calculate_similarity(field_name, field_id)
                
                # Take the better score
                score = max(score, score_id)
                
                if score > best_score and score >= threshold:
                    best_score = score
                    best_match = (field_id, field_info['description'], score)
        
        return best_match
    
    def map_field(self, field_name: str, section: str = None, field_std_id: str = None,
                  threshold: float = 0.6) -> Dict:
        """
        Map a field to standard field information.
        
        Args:
            field_name: The field name from AIP parsing
            section: The section name (admin, operational, handling, passenger) or None to search all sections
            field_std_id: Optional standard field ID
            threshold: Minimum similarity score
            
        Returns:
            Dictionary with mapping information
        """
        match = self.find_best_match(field_name, section, field_std_id, threshold)
        
        if match:
            field_id, description, score = match
            # Find which section this field belongs to
            found_section = None
            for search_section, fields in self.standard_fields.items():
                if field_id in fields:
                    found_section = search_section
                    break
            
            return {
                'original_field': field_name,
                'section': found_section,
                'mapped_field_id': field_id,
                'mapped_description': description,
                'similarity_score': score,
                'field_std_id': self.standard_fields[found_section][field_id]['field_std_id'],
                'mapped': True
            }
        else:
            return {
                'original_field': field_name,
                'section': section,
                'mapped_field_id': None,
                'mapped_description': None,
                'similarity_score': 0.0,
                'field_std_id': None,
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
                standardised_record['field_std_id'] = mapped_record['field_std_id'] 
                standardised_record['field'] = mapped_record['mapped_field_name']
                standardised_record['section'] = mapped_record['section']
                standardised_record['mapped_description'] = mapped_record['mapped_description']
                standardised_fields.append(standardised_record)
        return standardised_fields

    def get_field_for_std_id(self, field_std_id: int) -> Optional[Dict[str, Any]]:
        """
        Get the field for a given standard field ID.
        
        Args:
            field_std_id: The standard field ID to search for
            
        Returns:
            Field information dictionary or None if not found
        """
        for section, fields in self.standard_fields.items():
            for field_id, field_info in fields.items():
                if field_info['field_std_id'] == field_std_id:
                    return field_info
        return None