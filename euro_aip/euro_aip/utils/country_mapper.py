"""
Simple country mapping utility for border crossing data.

This module provides functionality to map between country names and ISO codes,
specifically focused on the countries that appear in border crossing documents.
"""

import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)

class CountryMapper:
    """Simple utility for mapping between country names and ISO codes."""
    
    # Single source of truth: countries we care about with their ISO codes
    COUNTRIES = {
        'GERMANY': 'DE',
        'FRANCE': 'FR', 
        'ITALY': 'IT',
        'SPAIN': 'ES',
        'NETHERLANDS': 'NL',
        'BELGIUM': 'BE',
        'AUSTRIA': 'AT',
        'SWITZERLAND': 'CH',
        'DENMARK': 'DK',
        'SWEDEN': 'SE',
        'NORWAY': 'NO',
        'FINLAND': 'FI',
        'POLAND': 'PL',
        'CZECH REPUBLIC': 'CZ',
        'SLOVAKIA': 'SK',
        'HUNGARY': 'HU',
        'ROMANIA': 'RO',
        'BULGARIA': 'BG',
        'GREECE': 'GR',
        'PORTUGAL': 'PT',
        'IRELAND': 'IE',
        'LUXEMBOURG': 'LU',
        'SLOVENIA': 'SI',
        'CROATIA': 'HR',
        'LATVIA': 'LV',
        'LITHUANIA': 'LT',
        'ESTONIA': 'EE',
        'MALTA': 'MT',
        'CYPRUS': 'CY',
        'UNITED KINGDOM': 'GB',
    }
    
    def __init__(self):
        """Initialize the country mapper."""
        # Create reverse mapping (ISO to name)
        self.iso_to_name = {iso: name for name, iso in self.COUNTRIES.items()}
        
        # Create case-insensitive mapping for lookup
        self.name_to_iso = {name.upper(): iso for name, iso in self.COUNTRIES.items()}
    
    def get_iso_code(self, country_name: str) -> Optional[str]:
        """
        Get ISO code for a country name.
        
        Args:
            country_name: Country name (case insensitive)
            
        Returns:
            ISO 3166-1 alpha-2 code or None if not found
        """
        if not country_name:
            return None
        
        # Normalize to uppercase for lookup
        normalized = country_name.upper().strip()
        
        # Direct lookup
        if normalized in self.name_to_iso:
            return self.name_to_iso[normalized]
        
        # Try partial match for common variations
        for name, iso in self.COUNTRIES.items():
            if normalized in name or name in normalized:
                return iso
        
        logger.debug(f"Could not find ISO code for country: {country_name}")
        return None
    
    def get_country_name(self, iso_code: str) -> Optional[str]:
        """
        Get full country name for an ISO code.
        
        Args:
            iso_code: ISO 3166-1 alpha-2 code
            
        Returns:
            Full country name or None if not found
        """
        if not iso_code:
            return None
        
        return self.iso_to_name.get(iso_code.upper())
    
    def get_all_countries(self) -> Dict[str, str]:
        """
        Get all country mappings.
        
        Returns:
            Dictionary of country names to ISO codes
        """
        return self.COUNTRIES.copy()
    
    def get_all_iso_codes(self) -> list:
        """
        Get list of all available ISO codes.
        
        Returns:
            List of ISO 3166-1 alpha-2 codes
        """
        return list(self.COUNTRIES.values())
    
    def get_all_countries_names(self) -> list:
        """
        Get list of all available country names.
        
        Returns:
            List of country names
        """
        return list(self.COUNTRIES.keys())
    
    def is_valid_country(self, country_name: str) -> bool:
        """
        Check if a country name is valid.
        
        Args:
            country_name: Country name to check
            
        Returns:
            True if valid, False otherwise
        """
        return self.get_iso_code(country_name) is not None 