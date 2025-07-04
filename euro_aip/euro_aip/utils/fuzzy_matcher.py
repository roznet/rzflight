"""
Generic fuzzy matching utility for text similarity comparison.

This module provides fuzzy matching functionality that can be used
across different parts of the euro_aip library for matching text strings.
"""

import re
from difflib import SequenceMatcher
from typing import List, Tuple, Optional, Any
import logging

logger = logging.getLogger(__name__)

class FuzzyMatcher:
    """Generic fuzzy matching utility for text similarity comparison."""
    
    def __init__(self):
        """Initialize the fuzzy matcher."""
        pass
    
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
    
    def calculate_similarity(self, text1: str, text2: str) -> float:
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
        
        # Return the best score from all methods
        combined_score = max(
            seq_similarity, word_similarity, substring_similarity,
            levenshtein_similarity, ngram_similarity, phonetic_similarity, acronym_similarity
        )
        return combined_score
    
    def find_best_match(self, query: str, candidates: List[str], 
                       threshold: float = 0.5) -> Optional[Tuple[str, float]]:
        """
        Find the best matching candidate for a query string.
        
        Args:
            query: The query string to match
            candidates: List of candidate strings to match against
            threshold: Minimum similarity score to consider a match
            
        Returns:
            Tuple of (best_match, similarity_score) or None if no match found
        """
        best_match = None
        best_score = 0.0
        
        for candidate in candidates:
            score = self.calculate_similarity(query, candidate)
            
            if score > best_score and score >= threshold:
                best_score = score
                best_match = candidate
        
        if best_match:
            return (best_match, best_score)
        return None
    
    def find_best_match_with_id(self, query: str, candidates: List[Tuple[Any, str]], 
                               threshold: float = 0.5) -> Optional[Tuple[Any, str, float]]:
        """
        Find the best matching candidate for a query string, returning the ID and match.
        
        Args:
            query: The query string to match
            candidates: List of (id, candidate_string) tuples to match against
            threshold: Minimum similarity score to consider a match
            
        Returns:
            Tuple of (id, best_match, similarity_score) or None if no match found
        """
        best_match = None
        best_score = 0.0
        best_id = None
        
        for candidate_id, candidate in candidates:
            score = self.calculate_similarity(query, candidate)
            
            if score > best_score and score >= threshold:
                best_score = score
                best_match = candidate
                best_id = candidate_id
        
        if best_match:
            return (best_id, best_match, best_score)
        return None 