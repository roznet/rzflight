"""
Generic fuzzy matching utility for text similarity comparison.

This module provides fuzzy matching functionality that can be used
across different parts of the euro_aip library for matching text strings.
"""

import re
from difflib import SequenceMatcher
from typing import List, Tuple, Optional, Any, Set, Dict
from enum import Enum
import logging

logger = logging.getLogger(__name__)

class SimilarityMethod(Enum):
    """
    Available similarity calculation methods.
    
    Each method is optimized for different types of text variations:
    """
    SEQUENCE_MATCHER = "sequence_matcher"
    """Uses Python's difflib.SequenceMatcher for general-purpose similarity.
    Good for: typos, minor character differences, and overall string similarity.
    Fast and reliable for most use cases."""
    
    WORD_OVERLAP = "word_overlap"
    """Calculates Jaccard similarity based on word overlap.
    Good for: different word orders, extra/missing words, and semantic similarity.
    Ignores word order and focuses on shared vocabulary."""
    
    SUBSTRING = "substring"
    """Checks if one string is contained within another.
    Good for: partial matches, abbreviations, and hierarchical naming.
    Useful when one text is a subset of another."""
    
    LEVENSHTEIN = "levenshtein"
    """Uses edit distance (Levenshtein) to measure character-level differences.
    Good for: typos, character insertions/deletions, and minor spelling variations.
    More computationally intensive but very accurate for character-level changes."""
    
    NGRAM = "ngram"
    """Uses n-gram overlap (default n=2) to capture character-level patterns.
    Good for: word order variations, character-level similarities, and phonetic variations.
    Balances speed and accuracy for character-level matching."""
    
    PHONETIC = "phonetic"
    """Uses simple phonetic encoding to match similar-sounding words.
    Good for: phonetic variations, different spellings of same sound, and pronunciation differences.
    Removes vowels and applies common letter substitutions."""
    
    ACRONYM = "acronym"
    """Matches acronyms and abbreviations within text.
    Good for: airport codes, abbreviations, and institutional names.
    Extracts and compares uppercase words and single letters."""

class FuzzyMatcher:
    """Generic fuzzy matching utility for text similarity comparison."""
    
    def __init__(self, enabled_methods: Optional[Set[SimilarityMethod]] = None):
        """
        Initialize the fuzzy matcher.
        
        Args:
            enabled_methods: Set of similarity methods to enable. 
                           If None, defaults to WORD_OVERLAP and LEVENSHTEIN.
        """
        if enabled_methods is None:
            enabled_methods = {SimilarityMethod.WORD_OVERLAP, SimilarityMethod.LEVENSHTEIN}
        
        self.enabled_methods = enabled_methods
        logger.debug(f"FuzzyMatcher initialized with methods: {[m.value for m in self.enabled_methods]}")
    
    def enable_method(self, method: SimilarityMethod) -> None:
        """Enable a specific similarity method."""
        self.enabled_methods.add(method)
        logger.debug(f"Enabled method: {method.value}")
    
    def disable_method(self, method: SimilarityMethod) -> None:
        """Disable a specific similarity method."""
        self.enabled_methods.discard(method)
        logger.debug(f"Disabled method: {method.value}")
    
    def get_enabled_methods(self) -> Set[SimilarityMethod]:
        """Get the currently enabled similarity methods."""
        return self.enabled_methods.copy()
    
    def set_enabled_methods(self, methods: Set[SimilarityMethod]) -> None:
        """Set the enabled similarity methods."""
        self.enabled_methods = methods.copy()
        logger.debug(f"Set enabled methods: {[m.value for m in self.enabled_methods]}")
    
    def is_method_enabled(self, method: SimilarityMethod) -> bool:
        """Check if a specific method is enabled."""
        return method in self.enabled_methods
    
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
    
    def _word_overlap_similarity(self, text1: str, text2: str) -> float:
        """
        Calculate similarity based on word overlap (Jaccard similarity).
        Args:
            text1: First text
            text2: Second text
        Returns:
            Similarity score between 0 and 1
        """
        words1 = set(text1.split())
        words2 = set(text2.split())
        if not words1 or not words2:
            return 0.0
        intersection = words1.intersection(words2)
        union = words1.union(words2)
        return len(intersection) / len(union) if union else 0.0

    def _substring_similarity(self, text1: str, text2: str) -> float:
        """
        Calculate similarity based on substring inclusion.
        Args:
            text1: First text
            text2: Second text
        Returns:
            Similarity score between 0 and 1
        """
        if len(text1) > 3 and len(text2) > 3:
            if text1 in text2 or text2 in text1:
                return min(len(text1), len(text2)) / max(len(text1), len(text2))
        return 0.0

    def calculate_similarity(self, text1: str, text2: str) -> float:
        """
        Calculate similarity between two texts using enabled fuzzy matching methods.
        
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
        
        scores = []

        # trivial case
        if norm1 == norm2:
            return 1.0
        
        # Method 1: Sequence matcher (good for typos and minor differences)
        if SimilarityMethod.SEQUENCE_MATCHER in self.enabled_methods:
            seq_similarity = SequenceMatcher(None, norm1, norm2).ratio()
            scores.append(seq_similarity)
            logger.debug(f"Sequence matcher similarity: {seq_similarity}")
        
        # Method 2: Word overlap (good for different word orders)
        if SimilarityMethod.WORD_OVERLAP in self.enabled_methods:
            word_similarity = self._word_overlap_similarity(norm1, norm2)
            scores.append(word_similarity)
            logger.debug(f"Word overlap similarity: {word_similarity}")
        
        # Method 3: Substring matching (good for partial matches)
        if SimilarityMethod.SUBSTRING in self.enabled_methods:
            substring_similarity = self._substring_similarity(norm1, norm2)
            scores.append(substring_similarity)
            logger.debug(f"Substring similarity: {substring_similarity}")
        
        # Method 4: Levenshtein distance (edit distance)
        if SimilarityMethod.LEVENSHTEIN in self.enabled_methods:
            levenshtein_similarity = self._levenshtein_similarity(norm1, norm2)
            scores.append(levenshtein_similarity)
            logger.debug(f"Levenshtein similarity: {levenshtein_similarity}")
        
        # Method 5: N-gram similarity (good for word order variations)
        if SimilarityMethod.NGRAM in self.enabled_methods:
            ngram_similarity = self._ngram_similarity(norm1, norm2, n=2)
            scores.append(ngram_similarity)
            logger.debug(f"N-gram similarity: {ngram_similarity}")
        
        # Method 6: Phonetic similarity (good for similar sounding words)
        if SimilarityMethod.PHONETIC in self.enabled_methods:
            phonetic_similarity = self._phonetic_similarity(norm1, norm2)
            scores.append(phonetic_similarity)
            logger.debug(f"Phonetic similarity: {phonetic_similarity}")
        
        # Method 7: Acronym matching (good for abbreviations)
        if SimilarityMethod.ACRONYM in self.enabled_methods:
            acronym_similarity = self._acronym_similarity(text1, text2)
            scores.append(acronym_similarity)
            logger.debug(f"Acronym similarity: {acronym_similarity}")
        
        # Return the best score from enabled methods
        if not scores:
            logger.warning("No similarity methods enabled, returning 0.0")
            return 0.0
        
        best_score = max(scores)
        logger.debug(f"Best similarity score: {best_score} from {len(scores)} enabled methods")
        return best_score
    
    def calculate_detailed_similarity(self, text1: str, text2: str) -> Dict[str, float]:
        """
        Calculate detailed similarity scores for all enabled methods.
        
        Args:
            text1: First text
            text2: Second text
            
        Returns:
            Dictionary mapping method names to similarity scores
        """
        if not text1 or not text2:
            return {method.value: 0.0 for method in self.enabled_methods}
        
        # Normalize both texts
        norm1 = self._normalize_text(text1)
        norm2 = self._normalize_text(text2)
        
        if not norm1 or not norm2:
            return {method.value: 0.0 for method in self.enabled_methods}
        
        results = {}
        
        # Method 1: Sequence matcher
        if SimilarityMethod.SEQUENCE_MATCHER in self.enabled_methods:
            results[SimilarityMethod.SEQUENCE_MATCHER.value] = SequenceMatcher(None, norm1, norm2).ratio()
        
        # Method 2: Word overlap
        if SimilarityMethod.WORD_OVERLAP in self.enabled_methods:
            results[SimilarityMethod.WORD_OVERLAP.value] = self._word_overlap_similarity(norm1, norm2)
        
        # Method 3: Substring matching
        if SimilarityMethod.SUBSTRING in self.enabled_methods:
            results[SimilarityMethod.SUBSTRING.value] = self._substring_similarity(norm1, norm2)
        
        # Method 4: Levenshtein distance
        if SimilarityMethod.LEVENSHTEIN in self.enabled_methods:
            results[SimilarityMethod.LEVENSHTEIN.value] = self._levenshtein_similarity(norm1, norm2)
        
        # Method 5: N-gram similarity
        if SimilarityMethod.NGRAM in self.enabled_methods:
            results[SimilarityMethod.NGRAM.value] = self._ngram_similarity(norm1, norm2, n=2)
        
        # Method 6: Phonetic similarity
        if SimilarityMethod.PHONETIC in self.enabled_methods:
            results[SimilarityMethod.PHONETIC.value] = self._phonetic_similarity(norm1, norm2)
        
        # Method 7: Acronym matching
        if SimilarityMethod.ACRONYM in self.enabled_methods:
            results[SimilarityMethod.ACRONYM.value] = self._acronym_similarity(text1, text2)
        
        return results
    
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
    
    @classmethod
    def create_with_all_methods(cls) -> 'FuzzyMatcher':
        """Create a FuzzyMatcher with all similarity methods enabled."""
        return cls(set(SimilarityMethod))
    
    @classmethod
    def create_with_fast_methods(cls) -> 'FuzzyMatcher':
        """Create a FuzzyMatcher with fast methods only (word overlap and sequence matcher)."""
        return cls({SimilarityMethod.WORD_OVERLAP, SimilarityMethod.SEQUENCE_MATCHER})
    
    @classmethod
    def create_with_edit_distance(cls) -> 'FuzzyMatcher':
        """Create a FuzzyMatcher with edit distance methods (levenshtein and sequence matcher)."""
        return cls({SimilarityMethod.LEVENSHTEIN, SimilarityMethod.SEQUENCE_MATCHER})
    
    @classmethod
    def create_with_phonetic(cls) -> 'FuzzyMatcher':
        """Create a FuzzyMatcher with phonetic similarity methods."""
        return cls({SimilarityMethod.PHONETIC, SimilarityMethod.WORD_OVERLAP}) 