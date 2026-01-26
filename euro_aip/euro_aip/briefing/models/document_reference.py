"""
Document reference model for AIP supplements and other linked documents.

Extracted from NOTAM text when references to external documents are detected.
"""

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class DocumentReference:
    """
    Reference to an external document found in NOTAM text.

    Examples:
        - AIP Supplement: "SUP 059/2025" from UK NATS
        - AIP Supplement: "SUP 009/26" from France SIA

    Attributes:
        type: Document type (e.g., "aip_supplement")
        identifier: Original reference string (e.g., "SUP 059/2025")
        provider: Provider ID that matched (e.g., "uk_nats", "france_sia")
        provider_name: Human-readable provider name
        search_url: URL to search/browse page for this document type
        document_urls: Direct URLs to the document(s)
    """
    type: str
    identifier: str
    provider: str
    provider_name: str
    search_url: Optional[str] = None
    document_urls: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            'type': self.type,
            'identifier': self.identifier,
            'provider': self.provider,
            'provider_name': self.provider_name,
            'search_url': self.search_url,
            'document_urls': self.document_urls,
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'DocumentReference':
        """Create from dictionary."""
        return cls(
            type=data.get('type', 'unknown'),
            identifier=data.get('identifier', ''),
            provider=data.get('provider', ''),
            provider_name=data.get('provider_name', ''),
            search_url=data.get('search_url'),
            document_urls=data.get('document_urls', []),
        )
