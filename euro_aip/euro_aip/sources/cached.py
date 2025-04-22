from abc import ABC, abstractmethod
import os
import json
import pandas as pd
from datetime import datetime
from typing import Any, Dict, List, Optional, Union, Tuple
from pathlib import Path

class CachedSource(ABC):
    """
    Base class for sources that implement caching.
    
    This class provides a caching mechanism for data sources. It handles:
    - Caching data to disk in various formats (JSON, CSV, PDF)
    - Checking cache validity based on age
    - Automatically fetching and caching new data when needed
    
    Key Format:
    The cache key should follow the format: `{base_key}_{parameter}`
    where:
    - `base_key`: The type of data being cached (e.g., 'airport', 'procedures')
    - `parameter`: Optional parameter for the data (e.g., ICAO code)
    
    Examples:
    - `airport_LFPO`: Airport data for LFPO
    - `procedures_EGLL`: Procedures for EGLL
    - `document_12345`: Document with ID 12345
    
    The base_key must correspond to a fetch method in the implementing class.
    For example, if the key is 'airport_LFPO', the class must implement
    a method named 'fetch_airport' that takes the parameter 'LFPO'.
    """
    
    def __init__(self, cache_dir: str):
        """
        Initialize the cached source.
        
        Args:
            cache_dir: Base directory for caching
        """
        self.cache_dir = Path(cache_dir)
        self.source_name = self.__class__.__name__.lower()
        self.cache_path = self.cache_dir / self.source_name
        self.cache_path.mkdir(parents=True, exist_ok=True)

    def _get_cache_file(self, key: str, ext: str) -> Path:
        """Get the cache file path for a given key and extension."""
        return self.cache_path / f"{key}.{ext}"

    def _is_cache_valid(self, cache_file: Path, max_age_days: Optional[int] = None) -> bool:
        """Check if the cache file is valid (exists and not too old)."""
        if not cache_file.exists():
            return False
        if max_age_days is None:
            return True
        file_age = datetime.now() - datetime.fromtimestamp(cache_file.stat().st_mtime)
        return file_age.days <= max_age_days

    def _save_to_cache(self, data: Any, key: str, ext: str) -> None:
        """Save data to cache with the specified extension."""
        cache_file = self._get_cache_file(key, ext)
        if ext == 'json':
            with open(cache_file, 'w') as f:
                json.dump(data, f)
        elif ext == 'csv':
            if isinstance(data, pd.DataFrame):
                data.to_csv(cache_file, index=False)
            else:
                pd.DataFrame(data).to_csv(cache_file, index=False)
        elif ext == 'pdf':
            with open(cache_file, 'wb') as f:
                f.write(data)
        else:
            raise ValueError(f"Unsupported file extension: {ext}")

    def _load_from_cache(self, key: str, ext: str) -> Any:
        """Load data from cache with the specified extension."""
        cache_file = self._get_cache_file(key, ext)
        if ext == 'json':
            with open(cache_file, 'r') as f:
                return json.load(f)
        elif ext == 'csv':
            return pd.read_csv(cache_file)
        elif ext == 'pdf':
            with open(cache_file, 'rb') as f:
                return f.read()
        else:
            raise ValueError(f"Unsupported file extension: {ext}")

    def _split_key(self, key: str) -> Tuple[str, str]:
        """
        Split a cache key into base key and parameter.
        
        Args:
            key: Full cache key (e.g., 'airport_LFPO')
            
        Returns:
            Tuple of (base_key, parameter)
        """
        parts = key.split('_', 1)
        if len(parts) == 1:
            return parts[0], ''
        return parts[0], parts[1]

    def _validate_fetch_method(self, base_key: str) -> None:
        """
        Validate that the fetch method exists for the given base key.
        
        Args:
            base_key: The base key to validate
            
        Raises:
            NotImplementedError: If the fetch method doesn't exist
        """
        method_name = f"fetch_{base_key}"
        if not hasattr(self, method_name):
            raise NotImplementedError(
                f"No fetch method found for key '{base_key}'. "
                f"Class {self.__class__.__name__} must implement a method named '{method_name}'."
            )

    def get_data(self, key: str, ext: str, param: str, cache_param: Optional[str] = None, max_age_days: Optional[int] = None, **kwargs) -> Any:
        """
        Get data from cache or fetch it if not available.
        
        Args:
            key: Base key for the data type (e.g., 'airport', 'procedures')
            ext: File extension (json, csv, or pdf)
            param: Parameter to pass to the fetch method
            cache_param: Optional parameter to use in the cache key (if None, uses param)
            max_age_days: Maximum age of cache in days (None for no limit)
            **kwargs: Additional arguments to pass to the fetch method
            
        Returns:
            The requested data
            
        Raises:
            NotImplementedError: If the fetch method doesn't exist
            ValueError: If the file extension is not supported
        """
        # Construct cache key using cache_param if provided, otherwise use param
        cache_key = f"{key}_{cache_param if cache_param is not None else param}"
        cache_file = self._get_cache_file(cache_key, ext)
        
        if self._is_cache_valid(cache_file, max_age_days):
            return self._load_from_cache(cache_key, ext)
            
        # Validate that the fetch method exists
        self._validate_fetch_method(key)
        
        # Get the fetch method
        fetch_method = getattr(self, f"fetch_{key}")
        
        # Call the fetch method with the parameter and any additional kwargs
        data = fetch_method(param, **kwargs)
        
        # Save to cache
        self._save_to_cache(data, cache_key, ext)
        
        return data

    @abstractmethod
    def fetch_airport(self, icao: str) -> Dict[str, Any]:
        """Fetch airport data from the source."""
        pass

    @abstractmethod
    def fetch_procedures(self, icao: str) -> List[Dict[str, Any]]:
        """Fetch procedures data from the source."""
        pass 