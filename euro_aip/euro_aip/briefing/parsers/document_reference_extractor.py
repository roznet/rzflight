"""
Document reference extractor for NOTAM text.

Extracts references to AIP supplements and other documents based on
configurable patterns. Configuration is loaded from document_references.json.
"""

import re
import json
import logging
from pathlib import Path
from typing import List, Optional, Dict, Any
from functools import lru_cache

from euro_aip.briefing.models.document_reference import DocumentReference

logger = logging.getLogger(__name__)


class DocumentReferenceExtractor:
    """
    Extract document references from NOTAM text using configurable providers.

    Providers are defined in document_references.json and specify:
    - Trigger patterns to detect when the provider applies
    - Reference patterns to extract document identifiers (e.g., SUP numbers)
    - URL templates to generate direct document links

    Example:
        extractor = DocumentReferenceExtractor()
        refs = extractor.extract(notam_text)
        for ref in refs:
            print(f"{ref.identifier}: {ref.document_urls}")
    """

    def __init__(self, config_path: Optional[Path] = None):
        """
        Initialize extractor with configuration.

        Args:
            config_path: Path to document_references.json.
                        If None, uses default location in data/ directory.
        """
        if config_path is None:
            # Default path relative to this file
            config_path = Path(__file__).parent.parent.parent.parent / 'data' / 'document_references.json'

        self.config_path = config_path
        self._providers: List[Dict[str, Any]] = []
        self._load_config()

    def _load_config(self) -> None:
        """Load provider configuration from JSON file."""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
                self._providers = config.get('providers', [])
                logger.debug(f"Loaded {len(self._providers)} document reference providers")
        except FileNotFoundError:
            logger.warning(f"Document reference config not found: {self.config_path}")
            self._providers = []
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in document reference config: {e}")
            self._providers = []

    def extract(self, text: str) -> List[DocumentReference]:
        """
        Extract document references from text.

        Args:
            text: NOTAM text to search

        Returns:
            List of DocumentReference objects found in text
        """
        if not text:
            return []

        text_upper = text.upper()
        references = []
        seen_identifiers = set()

        for provider in self._providers:
            # Check if any trigger pattern matches
            if not self._matches_trigger(text_upper, provider):
                continue

            # Extract references using this provider
            provider_refs = self._extract_with_provider(text_upper, provider)

            # Deduplicate
            for ref in provider_refs:
                key = (ref.provider, ref.identifier)
                if key not in seen_identifiers:
                    seen_identifiers.add(key)
                    references.append(ref)

        return references

    def _matches_trigger(self, text: str, provider: Dict[str, Any]) -> bool:
        """Check if text contains any trigger pattern for this provider."""
        trigger_patterns = provider.get('trigger_patterns', [])
        return any(pattern.upper() in text for pattern in trigger_patterns)

    def _extract_with_provider(
        self,
        text: str,
        provider: Dict[str, Any]
    ) -> List[DocumentReference]:
        """Extract all references matching this provider's pattern."""
        references = []

        pattern_str = provider.get('reference_pattern')
        if not pattern_str:
            return references

        try:
            pattern = re.compile(pattern_str, re.IGNORECASE)
        except re.error as e:
            logger.error(f"Invalid regex pattern for {provider.get('id')}: {e}")
            return references

        for match in pattern.finditer(text):
            # Extract number and year from match groups
            if match.lastindex and match.lastindex >= 2:
                number_str = match.group(1)
                year_str = match.group(2)

                # Normalize year to 4 digits
                year = self._normalize_year(year_str)

                # Pad number if needed
                number_padding = provider.get('number_padding', 3)
                number = number_str.zfill(number_padding)

                # Build identifier
                identifier = f"SUP {number}/{year}"

                # Generate URLs
                search_url = provider.get('search_url')
                document_urls = self._generate_document_urls(
                    provider, year, number
                )

                ref = DocumentReference(
                    type='aip_supplement',
                    identifier=identifier,
                    provider=provider.get('id', 'unknown'),
                    provider_name=provider.get('name', 'Unknown'),
                    search_url=search_url,
                    document_urls=document_urls,
                )
                references.append(ref)

        return references

    def _normalize_year(self, year_str: str) -> str:
        """Normalize year to 4 digits."""
        if len(year_str) == 2:
            # Assume 20xx for 2-digit years
            year_int = int(year_str)
            if year_int > 50:
                return f"19{year_str}"
            else:
                return f"20{year_str}"
        return year_str

    def _generate_document_urls(
        self,
        provider: Dict[str, Any],
        year: str,
        number: str
    ) -> List[str]:
        """Generate document URLs from templates."""
        templates = provider.get('document_url_templates', [])
        urls = []

        for template in templates:
            try:
                url = template.format(year=year, number=number)
                urls.append(url)
            except KeyError as e:
                logger.warning(f"Missing template variable {e} in {template}")

        return urls


# Module-level singleton for convenience
_default_extractor: Optional[DocumentReferenceExtractor] = None


def get_extractor() -> DocumentReferenceExtractor:
    """Get the default document reference extractor."""
    global _default_extractor
    if _default_extractor is None:
        _default_extractor = DocumentReferenceExtractor()
    return _default_extractor


def extract_document_references(text: str) -> List[DocumentReference]:
    """
    Convenience function to extract document references.

    Args:
        text: NOTAM text to search

    Returns:
        List of DocumentReference objects
    """
    return get_extractor().extract(text)
