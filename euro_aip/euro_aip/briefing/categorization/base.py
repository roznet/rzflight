"""Base interface for NOTAM categorizers."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional, Set, Dict, Any

from euro_aip.briefing.models.notam import Notam


@dataclass
class CategorizationResult:
    """
    Result of NOTAM categorization.

    Attributes:
        primary_category: Most relevant category
        categories: All applicable categories
        tags: Granular tags (e.g., "crane", "closed")
        relevance_hints: Additional hints for relevance scoring
        confidence: Confidence score (0-1)
        source: Which categorizer produced this result
    """
    primary_category: Optional[str] = None
    categories: Set[str] = field(default_factory=set)
    tags: Set[str] = field(default_factory=set)
    relevance_hints: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 1.0
    source: Optional[str] = None

    def merge(self, other: 'CategorizationResult') -> 'CategorizationResult':
        """
        Merge another result into this one.

        Higher confidence primary_category wins.
        All categories and tags are combined.
        """
        # Merge categories and tags
        merged_categories = self.categories | other.categories
        merged_tags = self.tags | other.tags
        merged_hints = {**self.relevance_hints, **other.relevance_hints}

        # Determine primary category and confidence
        # Rules:
        # 1. If only one has primary_category, use that one
        # 2. If both have primary_category, use higher confidence
        # 3. If confidence is equal, use the first one
        if self.primary_category and not other.primary_category:
            primary = self.primary_category
            confidence = self.confidence
        elif other.primary_category and not self.primary_category:
            primary = other.primary_category
            confidence = other.confidence
        elif other.confidence > self.confidence and other.primary_category:
            primary = other.primary_category
            confidence = other.confidence
        else:
            primary = self.primary_category
            confidence = self.confidence

        return CategorizationResult(
            primary_category=primary,
            categories=merged_categories,
            tags=merged_tags,
            relevance_hints=merged_hints,
            confidence=confidence,
            source=f"{self.source}+{other.source}" if self.source and other.source else self.source or other.source,
        )


class NotamCategorizer(ABC):
    """
    Base interface for NOTAM categorizers.

    Categorizers analyze NOTAM text and assign categories/tags.
    Multiple categorizers can be chained in a pipeline.

    Example:
        class MyCustomCategorizer(NotamCategorizer):
            @property
            def name(self) -> str:
                return "my_custom"

            def categorize(self, notam: Notam) -> CategorizationResult:
                result = CategorizationResult(source=self.name)
                # Custom logic here
                return result
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """
        Categorizer name for tracking.

        Returns:
            String identifier for this categorizer
        """
        pass

    @abstractmethod
    def categorize(self, notam: Notam) -> CategorizationResult:
        """
        Analyze a NOTAM and return categorization.

        Args:
            notam: NOTAM to categorize

        Returns:
            CategorizationResult with categories and tags
        """
        pass
