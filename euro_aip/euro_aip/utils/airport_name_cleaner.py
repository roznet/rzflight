"""
Airport name cleaning utility.

This module provides functionality to clean airport names by removing
common words like "Airport", "airfield", etc. to improve fuzzy matching.
"""

import re
import logging
from typing import List

logger = logging.getLogger(__name__)

class AirportNameCleaner:
    """Utility for cleaning airport names."""
    
    # Words to remove from airport names (case insensitive)
    WORDS_TO_REMOVE = {
        'airport', 'airfield', 'aerodrome', 'airstrip', 'airbase',
        'international', 'intl', 'domestic', 'regional', 'municipal',
        'civil', 'military', 'private', 'public'
    }
    
    # Common abbreviations to expand
    ABBREVIATIONS = {
        'intl': 'international',
        'int': 'international',
        'dom': 'domestic',
        'reg': 'regional',
        'mun': 'municipal',
        'civ': 'civil',
        'mil': 'military',
        'priv': 'private',
        'pub': 'public'
    }
    
    def __init__(self):
        """Initialize the airport name cleaner."""
        # Create regex pattern for words to remove
        self.remove_pattern = re.compile(
            r'\b(' + '|'.join(re.escape(word) for word in self.WORDS_TO_REMOVE) + r')\b',
            re.IGNORECASE
        )
    
    def clean_name(self, airport_name: str) -> str:
        """
        Clean an airport name by removing common words.
        
        Args:
            airport_name: Raw airport name
            
        Returns:
            Cleaned airport name
        """
        if not airport_name:
            return ""
        
        # Convert to string and strip whitespace
        name = str(airport_name).strip()
        
        # Remove common words
        cleaned = self.remove_pattern.sub('', name)
        
        # Clean up extra whitespace
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        
        # Remove leading/trailing punctuation
        cleaned = re.sub(r'^[^\w\s]+|[^\w\s]+$', '', cleaned).strip()
        
        return cleaned
    
    def clean_name_aggressive(self, airport_name: str) -> str:
        """
        More aggressive cleaning that also removes common abbreviations.
        
        Args:
            airport_name: Raw airport name
            
        Returns:
            Aggressively cleaned airport name
        """
        if not airport_name:
            return ""
        
        # First do basic cleaning
        cleaned = self.clean_name(airport_name)
        
        # Remove common abbreviations
        for abbrev, full in self.ABBREVIATIONS.items():
            # Replace abbreviation with full word, then remove the full word
            cleaned = re.sub(r'\b' + re.escape(abbrev) + r'\b', full, cleaned, flags=re.IGNORECASE)
        
        # Remove the full words that were expanded
        cleaned = self.remove_pattern.sub('', cleaned)
        
        # Clean up extra whitespace again
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        
        return cleaned
    
    def get_cleaned_variants(self, airport_name: str) -> List[str]:
        """
        Get multiple cleaned variants of an airport name.
        
        Args:
            airport_name: Raw airport name
            
        Returns:
            List of cleaned variants
        """
        variants = []
        
        if not airport_name:
            return variants
        
        # Original name
        variants.append(airport_name.strip())
        
        # Basic cleaning
        basic_cleaned = self.clean_name(airport_name)
        if basic_cleaned and basic_cleaned != airport_name.strip():
            variants.append(basic_cleaned)
        
        # Aggressive cleaning
        aggressive_cleaned = self.clean_name_aggressive(airport_name)
        if aggressive_cleaned and aggressive_cleaned not in variants:
            variants.append(aggressive_cleaned)
        
        return variants 