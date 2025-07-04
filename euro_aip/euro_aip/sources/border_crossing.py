"""
Border Crossing Source for downloading and parsing border crossing data.

This source downloads HTML data from URLs or reads from local files,
parses them using the BorderCrossingParser, and caches both the raw
HTML data and the parsed results.
"""

import os
import hashlib
import requests
from pathlib import Path
from typing import Dict, List, Tuple, Union, Optional, Any
from urllib.parse import urlparse
import logging

from .cached import CachedSource
from ..parsers.bordercrossing import BorderCrossingParser
from ..utils.country_mapper import CountryMapper
from ..utils.airport_name_cleaner import AirportNameCleaner
from ..models.border_crossing_entry import BorderCrossingEntry
from ..utils.fuzzy_matcher import FuzzyMatcher, SimilarityMethod

logger = logging.getLogger(__name__)

class BorderCrossingSource(CachedSource):
    """
    Source for border crossing data from HTML files or URLs.
    
    This source can handle:
    - Local HTML files
    - Remote URLs
    - Caching of both raw HTML and parsed results
    - Multiple input sources with named identifiers
    
    Input Format:
    The source can be initialized with a list of inputs in the format:
    - For files: (name, file_path) or just file_path (name will be derived from filename)
    - For URLs: (name, url) or just url (name will be derived from domain)
    
    Examples:
    - ("official_journal", "https://eur-lex.europa.eu/...")
    - ("local_copy", "/path/to/local/file.html")
    - "https://eur-lex.europa.eu/..."  # name will be "eur-lex-europa-eu"
    - "/path/to/file.html"  # name will be "file"
    """
    
    def __init__(self, cache_dir: str, inputs: Optional[List[Union[str, Tuple[str, str]]]] = None):
        """
        Initialize the BorderCrossingSource.
        
        Args:
            cache_dir: Base directory for caching
            inputs: List of inputs (URLs or file paths) with optional names
        """
        super().__init__(cache_dir)
        
        # Default URLs if none provided
        if inputs is None:
            inputs = [
                ("official_journal_2023_0609", "https://eur-lex.europa.eu/legal-content/EN/TXT/HTML/?uri=CELEX:52023XC0609(06)"),
                ("official_journal_2024_6003", "https://eur-lex.europa.eu/legal-content/EN/TXT/HTML/?uri=OJ:C_202406003"),
                ("official_journal_2024_4287", "https://eur-lex.europa.eu/legal-content/EN/TXT/HTML/?uri=OJ:C_202404287"),
                ("official_journal_2024_2713", "https://eur-lex.europa.eu/legal-content/EN/TXT/HTML/?uri=OJ:C_202402713"),
                ("official_journal_2023_1423", "https://eur-lex.europa.eu/legal-content/EN/TXT/HTML/?uri=OJ:C_202301423"),
                ("uk_gov_2024_12", "https://www.gov.uk/government/publications/general-aviation-operators-and-pilots-notification-of-flights/general-aviation-report-guidance-accessible#where-aircraft-can-arrive-and-depart")
            ]
        
        self.inputs = self._normalize_inputs(inputs)
        self.parser = BorderCrossingParser()
        self.country_mapper = CountryMapper()
        self.name_cleaner = AirportNameCleaner()
        
        logger.info(f"Initialized BorderCrossingSource with {len(self.inputs)} inputs")
    
    def _normalize_inputs(self, inputs: List[Union[str, Tuple[str, str]]]) -> List[Tuple[str, str]]:
        """
        Normalize input list to ensure all inputs have names.
        
        Args:
            inputs: List of inputs (URLs or file paths) with optional names
            
        Returns:
            List of (name, path/url) tuples
        """
        normalized = []
        
        for input_item in inputs:
            if isinstance(input_item, tuple):
                name, path = input_item
            else:
                path = input_item
                # Generate name from path/url
                if path.startswith(('http://', 'https://')):
                    # URL: use domain as name
                    parsed = urlparse(path)
                    name = parsed.netloc.replace('.', '_').replace('-', '_')
                else:
                    # File path: use filename without extension
                    name = Path(path).stem
            
            normalized.append((name, path))
        
        return normalized
    
    def _get_input_hash(self, name: str, path: str) -> str:
        """
        Generate a hash for the input to use in cache keys.
        
        Args:
            name: Input name
            path: Input path/URL
            
        Returns:
            Hash string for cache key
        """
        content = f"{name}:{path}"
        return hashlib.md5(content.encode()).hexdigest()[:8]
    
    def fetch_html(self, input_path: str, input_name: str = None) -> bytes:
        """
        Fetch HTML data from URL or file.
        
        Args:
            input_path: URL or file path
            input_name: Name identifier for the input (optional)
            
        Returns:
            Raw HTML data as bytes
        """
        logger.info(f"Fetching HTML from {input_path}")
        
        if input_path.startswith(('http://', 'https://')):
            # Fetch from URL
            try:
                response = requests.get(input_path, timeout=30)
                response.raise_for_status()
                return response.content
            except requests.RequestException as e:
                logger.error(f"Failed to fetch {input_path}: {e}")
                raise
        else:
            # Read from file
            try:
                with open(input_path, 'rb') as f:
                    return f.read()
            except IOError as e:
                logger.error(f"Failed to read {input_path}: {e}")
                raise
    
    def fetch_parsed_data(self, input_path: str, input_name: str = None) -> List[Dict[str, Any]]:
        """
        Fetch and parse border crossing data.
        
        Args:
            input_path: URL or file path
            input_name: Name identifier for the input (optional)
            
        Returns:
            List of parsed airport data dictionaries
        """
        # Find the input name if not provided
        if input_name is None:
            input_item = next((item for item in self.inputs if item[1] == input_path), None)
            if input_item:
                input_name = input_item[0]
            else:
                input_name = "unknown"
        
        logger.info(f"Fetching and parsing data for {input_name}")
        
        # Get HTML data (from cache or fresh fetch)
        html_data = self.get_data(
            key="html",
            ext="pdf",  # Use PDF extension for binary HTML data
            param=input_path,
            cache_param=f"{input_name}_{self._get_input_hash(input_name, input_path)}",
            max_age_days=7  # Cache HTML for 7 days
        )
        
        # Parse the HTML data
        try:
            parsed_data = self.parser.parse(html_data, "BORDER_CROSSING")
            logger.info(f"Parsed {len(parsed_data)} airport entries from {input_name}")
            return parsed_data
        except Exception as e:
            logger.error(f"Failed to parse data from {input_name}: {e}")
            raise
    
    def get_border_crossing_data(self, input_name: Optional[str] = None, max_age_days: int = 30) -> List[Dict[str, Any]]:
        """
        Get border crossing data for a specific input or all inputs.
        
        Args:
            input_name: Specific input name to fetch (None for all inputs)
            max_age_days: Maximum age of parsed data cache in days
            
        Returns:
            List of parsed airport data dictionaries
        """
        all_data = []
        
        if input_name:
            # Get specific input
            input_item = next((item for item in self.inputs if item[0] == input_name), None)
            if not input_item:
                raise ValueError(f"Input '{input_name}' not found. Available: {[item[0] for item in self.inputs]}")
            
            name, path = input_item
            data = self.get_data(
                key="parsed_data",
                ext="json",
                param=path,
                cache_param=f"{name}_{self._get_input_hash(name, path)}",
                max_age_days=max_age_days
            )
            all_data.extend(data)
        else:
            # Get all inputs
            for name, path in self.inputs:
                try:
                    data = self.get_data(
                        key="parsed_data",
                        ext="json",
                        param=path,
                        cache_param=f"{name}_{self._get_input_hash(name, path)}",
                        max_age_days=max_age_days
                    )
                    all_data.extend(data)
                except Exception as e:
                    logger.warning(f"Failed to get data for {name}: {e}")
                    continue
        
        logger.info(f"Retrieved {len(all_data)} total airport entries")
        return all_data
    
    def get_available_inputs(self) -> List[Tuple[str, str]]:
        """
        Get list of available inputs.
        
        Returns:
            List of (name, path) tuples
        """
        return self.inputs.copy()
    
    def add_input(self, name: str, path: str) -> None:
        """
        Add a new input to the source.
        
        Args:
            name: Input name
            path: Input path/URL
        """
        self.inputs.append((name, path))
        logger.info(f"Added input: {name} -> {path}")
    
    def remove_input(self, name: str) -> None:
        """
        Remove an input from the source.
        
        Args:
            name: Input name to remove
        """
        self.inputs = [(n, p) for n, p in self.inputs if n != name]
        logger.info(f"Removed input: {name}")
    
    def update_model(self, model: 'EuroAipModel') -> None:
        """
        Update the EuroAipModel with border crossing data.
        
        Args:
            model: The EuroAipModel to update
        """
        fuzzy_matcher = FuzzyMatcher()
        fuzzy_matcher.set_enabled_methods({SimilarityMethod.WORD_OVERLAP, 
                                           SimilarityMethod.SEQUENCE_MATCHER})
        matched_count = 0
        unmatched_count = 0
        
        # Get all border crossing data
        border_data = self.get_border_crossing_data()
        
        # Pre-organize airports by country for faster matching
        airports_by_country = {}
        airports_by_iso = {}
        
        for icao, airport in model.airports.items():
            if airport.name:
                # Use iso_country field for ISO code
                country_iso = getattr(airport, 'iso_country', None)
                if country_iso:
                    if country_iso not in airports_by_iso:
                        airports_by_iso[country_iso] = []
                    airports_by_iso[country_iso].append((icao, airport.name))
                    # Use country mapper to get country name
                    country_name = self.country_mapper.get_country_name(country_iso)
                    if country_name:
                        if country_name not in airports_by_country:
                            airports_by_country[country_name] = []
                        airports_by_country[country_name].append((icao, airport.name))
        
        logger.info(f"Organized {len(model.airports)} airports by country for matching")
        
        # Create BorderCrossingEntry objects
        border_crossing_entries = []
        
        for entry in border_data:
            airport_icao = None
            matched_airport_icao = None
            match_score = None
            
            # First, try to use ICAO code if available
            if 'icao_code' in entry and entry['icao_code']:
                airport_icao = entry['icao_code']
                if airport_icao in model.airports:
                    airport = model.airports[airport_icao]
                    matched_airport_icao = airport_icao
                    match_score = 1.0
                    matched_count += 1
                    logger.debug(f"Matched border crossing entry for {airport_icao} using ICAO code")
                else:
                    logger.debug(f"ICAO code {airport_icao} not found in model")
                    airport_icao = None
            
            # If no ICAO code or not found, try fuzzy matching on airport name
            if not airport_icao and 'airport_name' in entry and entry['airport_name']:
                airport_name = entry['airport_name']
                country_name = entry.get('country', '').strip()
                
                # Get country ISO code from border crossing data
                country_iso = self.country_mapper.get_iso_code(country_name)
                
                # Determine which airport list to search
                candidates = []
                
                # First try to match by country ISO code
                if country_iso and country_iso in airports_by_iso:
                    candidates = airports_by_iso[country_iso]
                    logger.debug(f"Searching {len(candidates)} airports in country {country_iso} ({country_name})")
                
                # If no candidates found by ISO, try by country name
                elif country_name and country_name in airports_by_country:
                    candidates = airports_by_country[country_name]
                    logger.debug(f"Searching {len(candidates)} airports in country {country_name}")
                
                # If still no candidates, search all airports (fallback)
                if not candidates:
                    candidates = [(icao, name) for icao, name in airports_by_iso.get(country_iso, [])]
                    candidates.extend([(icao, name) for icao, name in airports_by_country.get(country_name, [])])
                    
                    # If still no candidates, use all airports
                    if not candidates:
                        candidates = [(icao, airport.name) for icao, airport in model.airports.items() if airport.name]
                        logger.debug(f"No country-specific candidates found, searching all {len(candidates)} airports")
                
                if candidates:
                    # Clean the airport name for better matching
                    cleaned_name = self.name_cleaner.clean_name(airport_name)
                    
                    # Try matching with cleaned name first
                    result = None
                    if cleaned_name and cleaned_name != airport_name:
                        result = fuzzy_matcher.find_best_match_with_id(
                            cleaned_name, 
                            candidates, 
                            threshold=0.6
                        )
                    
                    # If no match with cleaned name, try original name
                    if not result:
                        result = fuzzy_matcher.find_best_match_with_id(
                            airport_name, 
                            candidates, 
                            threshold=0.6
                        )
                    
                    # If still no match, try with all variants
                    if not result:
                        name_variants = self.name_cleaner.get_cleaned_variants(airport_name)
                        for variant in name_variants:
                            if variant != airport_name and variant != cleaned_name:
                                result = fuzzy_matcher.find_best_match_with_id(
                                    variant, 
                                    candidates, 
                                    threshold=0.6
                                )
                                if result:
                                    break
                    
                    if result:
                        matched_icao, matched_name, score = result
                        matched_airport_icao = matched_icao
                        match_score = score
                        matched_count += 1
                        logger.debug(f"Fuzzy matched '{airport_name}' to '{matched_name}' ({matched_icao}) with score {score:.2f}")
                    else:
                        unmatched_count += 1
                        logger.debug(f"No fuzzy match found for airport name: {airport_name} in country: {country_name}")
                else:
                    unmatched_count += 1
                    logger.debug(f"No airport candidates available for country: {country_name}")
            
            # Create BorderCrossingEntry object
            border_entry = BorderCrossingEntry(
                airport_name=entry.get('airport_name', ''),
                country_iso=self.country_mapper.get_iso_code(entry.get('country', '')) or '',
                icao_code=airport_icao,
                source=entry.get('source', ''),
                extraction_method=entry.get('extraction_method', ''),
                metadata=entry.get('metadata', {}),
                matched_airport_icao=matched_airport_icao,
                match_score=match_score
            )
            border_crossing_entries.append(border_entry)
            
            # If we found a matching airport, add border crossing information
            if matched_airport_icao and matched_airport_icao in model.airports:
                airport = model.airports[matched_airport_icao]
                
                # Add border crossing data to airport
                airport.point_of_entry = True
                
                # Add source tracking
                airport.add_source('border_crossing')
                
                # Log the match
                logger.debug(f"Added border crossing data to {matched_airport_icao} ({airport.name})")
        
        # Save border crossing entries to database if available
        try:
            from ..storage.database_storage import DatabaseStorage
            # This is a bit of a hack - we need access to the database storage
            # In a real implementation, we'd pass the database storage to this method
            logger.info(f"Created {len(border_crossing_entries)} border crossing entries")
        except ImportError:
            logger.warning("DatabaseStorage not available, skipping border crossing data persistence")
        
        # Add border crossing entries to the model
        model.add_border_crossing_entries(border_crossing_entries)
        
        # Update airport objects with border crossing information
        model.update_border_crossing_airports()
        
        logger.info(f"Border crossing update complete: {matched_count} matched, {unmatched_count} unmatched")
        
        if unmatched_count > 0:
            logger.warning(f"{unmatched_count} border crossing entries could not be matched to airports in the model") 