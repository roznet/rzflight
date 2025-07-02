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
                ("official_journal_2023", "https://eur-lex.europa.eu/legal-content/EN/TXT/HTML/?uri=CELEX:52023XC0609(06)"),
                ("official_journal_pdf", "https://eur-lex.europa.eu/legal-content/EN/TXT/PDF/?uri=CELEX:52023XC0609(06)")
            ]
        
        self.inputs = self._normalize_inputs(inputs)
        self.parser = BorderCrossingParser()
        
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
        # TODO: Implement model update logic
        # This would involve:
        # 1. Getting border crossing data
        # 2. Matching airport names to ICAO codes
        # 3. Adding border crossing information to airport objects
        pass 