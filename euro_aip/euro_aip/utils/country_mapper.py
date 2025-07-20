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
        'ICELAND': 'IS',
        # Additional European countries
        'MOLDOVA': 'MD',
        'NORTH MACEDONIA': 'MK',
        'MONTENEGRO': 'ME',
        'SERBIA': 'RS',
        'SAN MARINO': 'SM',
        'TURKEY': 'TR',
        'UKRAINE': 'UA',
        'BELARUS': 'BY',
        'BOSNIA AND HERZEGOVINA': 'BA',
        # More European countries
        'ALBANIA': 'AL',
        'RUSSIA': 'RU',
        'FAROE ISLANDS': 'FO',
        'GEORGIA': 'GE',
        'GUERNSEY': 'GG',
        'GIBRALTAR': 'GI',
        # Final European countries
        'ISLE OF MAN': 'IM',
        'JERSEY': 'JE',
        'KAZAKHSTAN': 'KZ',
        'KOSOVO': 'XK',
    }
    
    # Priority mapping for sorting (lower numbers = higher priority)
    COUNTRY_PRIORITY = {
        # UK and Crown Dependencies (highest priority)
        'GB': 1,  # United Kingdom
        'GG': 2,  # Guernsey
        'JE': 3,  # Jersey
        'IM': 4,  # Isle of Man
        'GI': 5,  # Gibraltar
        
        # Major EU countries (high priority)
        'DE': 10,  # Germany
        'FR': 11,  # France
        'IT': 12,  # Italy
        'ES': 13,  # Spain
        'NL': 14,  # Netherlands
        'BE': 15,  # Belgium
        'AT': 16,  # Austria
        'DK': 17,  # Denmark
        'SE': 18,  # Sweden
        'FI': 19,  # Finland
        'PT': 20,  # Portugal
        'IE': 21,  # Ireland
        'LU': 22,  # Luxembourg
        
        # Other EU countries
        'PL': 30,  # Poland
        'CZ': 31,  # Czech Republic
        'SK': 32,  # Slovakia
        'HU': 33,  # Hungary
        'RO': 34,  # Romania
        'BG': 35,  # Bulgaria
        'GR': 36,  # Greece
        'SI': 37,  # Slovenia
        'HR': 38,  # Croatia
        'LV': 39,  # Latvia
        'LT': 40,  # Lithuania
        'EE': 41,  # Estonia
        'MT': 42,  # Malta
        'CY': 43,  # Cyprus
        
        # Non-EU European countries
        'CH': 50,  # Switzerland
        'NO': 51,  # Norway
        'IS': 52,  # Iceland
        'TR': 53,  # Turkey
        'UA': 54,  # Ukraine
        'BY': 55,  # Belarus
        'MD': 56,  # Moldova
        'MK': 57,  # North Macedonia
        'ME': 58,  # Montenegro
        'RS': 59,  # Serbia
        'BA': 60,  # Bosnia and Herzegovina
        'AL': 61,  # Albania
        'SM': 62,  # San Marino
        'FO': 63,  # Faroe Islands
        'GE': 64,  # Georgia
        'XK': 65,  # Kosovo
        
        # Non-European countries (lowest priority)
        'RU': 100,  # Russia
        'KZ': 101,  # Kazakhstan
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
    
    def get_country_priority(self, iso_code: str) -> int:
        """
        Get priority/order for a country ISO code.
        
        Args:
            iso_code: ISO 3166-1 alpha-2 code
            
        Returns:
            Priority number (lower = higher priority) or 999 if not found
        """
        if not iso_code:
            return 999
        
        return self.COUNTRY_PRIORITY.get(iso_code.upper(), 999)
    
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