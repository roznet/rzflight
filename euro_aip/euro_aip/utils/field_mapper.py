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
        Calculate similarity between two texts using multiple fuzzy matching methods.
        
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
        
        # Method 4: Levenshtein distance (edit distance)
        levenshtein_similarity = self._levenshtein_similarity(norm1, norm2)
        
        # Method 5: N-gram similarity (good for word order variations)
        ngram_similarity = self._ngram_similarity(norm1, norm2, n=2)
        
        # Method 6: Phonetic similarity (good for similar sounding words)
        phonetic_similarity = self._phonetic_similarity(norm1, norm2)
        
        # Method 7: Acronym matching (good for abbreviations)
        acronym_similarity = self._acronym_similarity(text1, text2)
        
        combined_score = max(seq_similarity,word_similarity,substring_similarity,levenshtein_similarity,ngram_similarity,acronym_similarity)
        return combined_score
    
    def _levenshtein_similarity(self, text1: str, text2: str) -> float:
        """
        Calculate similarity using Levenshtein distance (edit distance).
        
        Args:
            text1: First text
            text2: Second text
            
        Returns:
            Similarity score between 0 and 1
        """
        if not text1 or not text2:
            return 0.0
        
        # Calculate Levenshtein distance
        distance = self._levenshtein_distance(text1, text2)
        max_len = max(len(text1), len(text2))
        
        if max_len == 0:
            return 1.0
        
        # Convert distance to similarity (1 - normalized_distance)
        return 1.0 - (distance / max_len)
    
    def _levenshtein_distance(self, text1: str, text2: str) -> int:
        """
        Calculate Levenshtein distance between two strings.
        
        Args:
            text1: First string
            text2: Second string
            
        Returns:
            Levenshtein distance
        """
        if len(text1) < len(text2):
            return self._levenshtein_distance(text2, text1)
        
        if len(text2) == 0:
            return len(text1)
        
        previous_row = list(range(len(text2) + 1))
        for i, c1 in enumerate(text1):
            current_row = [i + 1]
            for j, c2 in enumerate(text2):
                insertions = previous_row[j + 1] + 1
                deletions = current_row[j] + 1
                substitutions = previous_row[j] + (c1 != c2)
                current_row.append(min(insertions, deletions, substitutions))
            previous_row = current_row
        
        return previous_row[-1]
    
    def _ngram_similarity(self, text1: str, text2: str, n: int = 2) -> float:
        """
        Calculate similarity using n-gram overlap.
        
        Args:
            text1: First text
            text2: Second text
            n: Size of n-grams
            
        Returns:
            Similarity score between 0 and 1
        """
        if not text1 or not text2:
            return 0.0
        
        # Generate n-grams
        ngrams1 = set()
        ngrams2 = set()
        
        for i in range(len(text1) - n + 1):
            ngrams1.add(text1[i:i+n])
        
        for i in range(len(text2) - n + 1):
            ngrams2.add(text2[i:i+n])
        
        if not ngrams1 or not ngrams2:
            return 0.0
        
        # Calculate Jaccard similarity
        intersection = ngrams1.intersection(ngrams2)
        union = ngrams1.union(ngrams2)
        
        return len(intersection) / len(union) if union else 0.0
    
    def _phonetic_similarity(self, text1: str, text2: str) -> float:
        """
        Calculate phonetic similarity using simple phonetic encoding.
        
        Args:
            text1: First text
            text2: Second text
            
        Returns:
            Similarity score between 0 and 1
        """
        if not text1 or not text2:
            return 0.0
        
        # Simple phonetic encoding (remove vowels and common letter substitutions)
        def phonetic_encode(text):
            # Remove vowels except at the beginning
            if len(text) > 1:
                text = text[0] + ''.join(c for c in text[1:] if c not in 'aeiou')
            
            # Common letter substitutions
            substitutions = {
                'c': 'k', 'q': 'k', 'x': 'ks',
                'ph': 'f', 'gh': 'g', 'th': 't',
                'ck': 'k', 'ch': 'k', 'sh': 's'
            }
            
            for old, new in substitutions.items():
                text = text.replace(old, new)
            
            return text
        
        phonetic1 = phonetic_encode(text1)
        phonetic2 = phonetic_encode(text2)
        
        # Use sequence matcher on phonetic encodings
        return SequenceMatcher(None, phonetic1, phonetic2).ratio()
    
    def _acronym_similarity(self, text1: str, text2: str) -> float:
        """
        Calculate similarity based on acronym matching.
        
        Args:
            text1: First text
            text2: Second text
            
        Returns:
            Similarity score between 0 and 1
        """
        if not text1 or not text2:
            return 0.0
        
        # Extract acronyms (words with all caps or single letters)
        def extract_acronyms(text):
            words = text.split()
            acronyms = []
            
            for word in words:
                # All caps words
                if word.isupper() and len(word) > 1:
                    acronyms.append(word)
                # Single letter words (likely abbreviations)
                elif len(word) == 1 and word.isalpha():
                    acronyms.append(word.upper())
                # Words with mixed case that might be acronyms
                elif word.isupper() and len(word) <= 4:
                    acronyms.append(word)
            
            return acronyms
        
        acronyms1 = extract_acronyms(text1)
        acronyms2 = extract_acronyms(text2)
        
        if not acronyms1 or not acronyms2:
            return 0.0
        
        # Check for exact acronym matches
        common_acronyms = set(acronyms1).intersection(set(acronyms2))
        
        if common_acronyms:
            return len(common_acronyms) / max(len(acronyms1), len(acronyms2))
        
        return 0.0
    
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
        best_match = None
        best_score = 0.0
        
        # Convert field_aip_id to int if it's a string
        field_aip_id_int = self._safe_int_convert(field_aip_id)
        
        # First, try exact match with field_aip_id if provided
        if field_aip_id_int is not None:
            for field_id, field_info in self.standard_fields.items():
                if field_info['field_aip_id'] == field_aip_id_int:
                    return (field_id, field_info['field_name'], 1.0)
        
        # Then try fuzzy matching with field names
        for field_id, field_info in self.standard_fields.items():
            # Skip if section is specified and doesn't match
            if section is not None and field_info['section'] != section:
                continue
                
            # Try matching against the field name
            score = self._calculate_similarity(field_name, field_info['field_name'])
            
            if score > best_score and score >= threshold:
                best_score = score
                best_match = (field_id, field_info['field_name'], score)
        
        return best_match
    
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