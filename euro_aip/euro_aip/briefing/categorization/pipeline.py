"""Categorization pipeline for combining multiple categorizers."""

from typing import List, Optional

from euro_aip.briefing.categorization.base import NotamCategorizer, CategorizationResult
from euro_aip.briefing.categorization.q_code import QCodeCategorizer
from euro_aip.briefing.categorization.text_rules import TextRuleCategorizer
from euro_aip.briefing.models.notam import Notam


class CategorizationPipeline:
    """
    Chain multiple categorizers together.

    Categorizers are run in order, with results merged.
    Higher confidence results take precedence for primary category.
    All categories and tags are combined.

    Example:
        # Use default categorizers (Q-code + text rules)
        pipeline = CategorizationPipeline()

        # Categorize all NOTAMs
        pipeline.categorize_all(briefing.notams)

        # Now NOTAMs have custom_categories and custom_tags
        for notam in briefing.notams:
            print(f"{notam.id}: {notam.primary_category} - {notam.custom_tags}")

        # Add custom categorizer
        pipeline.add_categorizer(MyCustomCategorizer())
    """

    def __init__(self, categorizers: Optional[List[NotamCategorizer]] = None):
        """
        Initialize pipeline with categorizers.

        Args:
            categorizers: List of categorizers to use.
                         If None, uses default (QCodeCategorizer + TextRuleCategorizer).
        """
        if categorizers is None:
            self.categorizers: List[NotamCategorizer] = [
                QCodeCategorizer(),
                TextRuleCategorizer(),
            ]
        else:
            self.categorizers = list(categorizers)

    def categorize(self, notam: Notam) -> CategorizationResult:
        """
        Run all categorizers and merge results.

        Higher confidence results take precedence for primary category.
        All categories and tags are merged.

        Args:
            notam: NOTAM to categorize

        Returns:
            Merged CategorizationResult
        """
        final = CategorizationResult()

        for categorizer in self.categorizers:
            result = categorizer.categorize(notam)
            final = final.merge(result)

        return final

    def categorize_all(self, notams: List[Notam]) -> List[Notam]:
        """
        Categorize all NOTAMs and attach results.

        Modifies NOTAMs in place, adding:
        - primary_category
        - custom_categories
        - custom_tags

        Args:
            notams: List of NOTAMs to categorize

        Returns:
            Same list of NOTAMs (modified in place)
        """
        for notam in notams:
            result = self.categorize(notam)
            notam.primary_category = result.primary_category
            notam.custom_categories = result.categories
            notam.custom_tags = result.tags

        return notams

    def add_categorizer(self, categorizer: NotamCategorizer) -> 'CategorizationPipeline':
        """
        Add a categorizer to the pipeline.

        Args:
            categorizer: Categorizer to add

        Returns:
            Self for chaining
        """
        self.categorizers.append(categorizer)
        return self

    def insert_categorizer(
        self,
        index: int,
        categorizer: NotamCategorizer
    ) -> 'CategorizationPipeline':
        """
        Insert a categorizer at a specific position.

        Args:
            index: Position to insert at
            categorizer: Categorizer to insert

        Returns:
            Self for chaining
        """
        self.categorizers.insert(index, categorizer)
        return self

    def remove_categorizer(self, name: str) -> 'CategorizationPipeline':
        """
        Remove a categorizer by name.

        Args:
            name: Name of categorizer to remove

        Returns:
            Self for chaining
        """
        self.categorizers = [c for c in self.categorizers if c.name != name]
        return self

    def get_categorizer_names(self) -> List[str]:
        """Get list of categorizer names in pipeline."""
        return [c.name for c in self.categorizers]
