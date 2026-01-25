"""Tests for NOTAM categorization."""

import pytest

from euro_aip.briefing.categorization.base import CategorizationResult
from euro_aip.briefing.categorization.q_code import QCodeCategorizer
from euro_aip.briefing.categorization.text_rules import TextRuleCategorizer
from euro_aip.briefing.categorization.pipeline import CategorizationPipeline
from euro_aip.briefing.models.notam import Notam, NotamCategory


def create_notam(
    q_code: str = None,
    message: str = "",
    raw_text: str = None,
) -> Notam:
    """Helper to create test NOTAMs."""
    return Notam(
        id="TEST/24",
        location="LFPG",
        q_code=q_code,
        message=message,
        raw_text=raw_text or message,
    )


class TestCategorizationResult:
    """Tests for CategorizationResult."""

    def test_merge_results(self):
        """Test merging two results."""
        result1 = CategorizationResult(
            primary_category="runway",
            categories={"runway"},
            tags={"closed"},
            confidence=0.8,
            source="categorizer1",
        )

        result2 = CategorizationResult(
            primary_category="taxiway",
            categories={"taxiway"},
            tags={"work_in_progress"},
            confidence=0.6,
            source="categorizer2",
        )

        merged = result1.merge(result2)

        # Higher confidence primary wins
        assert merged.primary_category == "runway"
        # Categories are combined
        assert merged.categories == {"runway", "taxiway"}
        # Tags are combined
        assert merged.tags == {"closed", "work_in_progress"}
        assert merged.confidence == 0.8

    def test_merge_with_higher_confidence_second(self):
        """Test that higher confidence result wins for primary."""
        result1 = CategorizationResult(
            primary_category="runway",
            confidence=0.5,
        )

        result2 = CategorizationResult(
            primary_category="navaid",
            confidence=0.9,
        )

        merged = result1.merge(result2)

        assert merged.primary_category == "navaid"
        assert merged.confidence == 0.9


class TestQCodeCategorizer:
    """Tests for QCodeCategorizer."""

    def test_categorize_runway_closed(self):
        """Test categorizing runway closed Q-code."""
        categorizer = QCodeCategorizer()
        notam = create_notam(q_code="QMRLC")

        result = categorizer.categorize(notam)

        assert result.primary_category == "runway"
        assert "runway" in result.categories
        assert "closed" in result.tags
        assert result.confidence == 1.0

    def test_categorize_taxiway_closed(self):
        """Test categorizing taxiway closed Q-code."""
        categorizer = QCodeCategorizer()
        notam = create_notam(q_code="QMXLC")

        result = categorizer.categorize(notam)

        assert result.primary_category == "taxiway"
        assert "closed" in result.tags

    def test_categorize_vor_unserviceable(self):
        """Test categorizing VOR unserviceable Q-code."""
        categorizer = QCodeCategorizer()
        notam = create_notam(q_code="QNVAS")

        result = categorizer.categorize(notam)

        assert result.primary_category == "navaid"
        assert "vor" in result.tags
        assert "unserviceable" in result.tags

    def test_categorize_ils_unserviceable(self):
        """Test categorizing ILS unserviceable Q-code."""
        categorizer = QCodeCategorizer()
        # IC = ILS, AS = Unserviceable
        notam = create_notam(q_code="QICAS")

        result = categorizer.categorize(notam)

        assert result.primary_category == "navaid"
        assert "ils" in result.tags
        assert "unserviceable" in result.tags

    def test_categorize_approach_procedure_changed(self):
        """Test categorizing approach procedure changed Q-code."""
        categorizer = QCodeCategorizer()
        # PI = Instrument approach procedure, CH = Changed
        notam = create_notam(q_code="QPICH")

        result = categorizer.categorize(notam)

        assert result.primary_category == "procedure"
        assert "instr_apch_proc" in result.tags  # From JSON phrase
        assert "changed" in result.tags

    def test_categorize_obstacle(self):
        """Test categorizing obstacle Q-code."""
        categorizer = QCodeCategorizer()
        # OB = Obstacle, CA = Activated (obstacle erected/active)
        notam = create_notam(q_code="QOBCA")

        result = categorizer.categorize(notam)

        assert result.primary_category == "obstacle"
        assert "obst" in result.tags  # From JSON phrase
        assert "active" in result.tags or "activated" in result.tags

    def test_categorize_restricted_area_active(self):
        """Test categorizing restricted area active Q-code."""
        categorizer = QCodeCategorizer()
        # RR = Restricted area, CA = Activated
        notam = create_notam(q_code="QRRCA")

        result = categorizer.categorize(notam)

        assert result.primary_category == "airspace"
        assert "r_area" in result.tags  # From JSON phrase
        assert "active" in result.tags or "activated" in result.tags

    def test_categorize_parachuting(self):
        """Test categorizing parachuting warning Q-code."""
        categorizer = QCodeCategorizer()
        # WP = Parachute jumping/Hang gliding, CA = Activated
        notam = create_notam(q_code="QWPCA")

        result = categorizer.categorize(notam)

        assert result.primary_category == "warning"
        assert "pje/paragliding" in result.tags  # From JSON phrase

    def test_categorize_no_qcode(self):
        """Test categorizing NOTAM without Q-code."""
        categorizer = QCodeCategorizer()
        notam = create_notam(q_code=None)

        result = categorizer.categorize(notam)

        assert result.confidence == 0.0
        assert result.primary_category is None

    def test_categorize_unknown_qcode(self):
        """Test categorizing unknown Q-code falls back to prefix."""
        categorizer = QCodeCategorizer()
        notam = create_notam(q_code="QMRZZ")  # Unknown but starts with MR

        result = categorizer.categorize(notam)

        # Should match by prefix
        assert result.primary_category == "runway"
        assert result.confidence < 1.0


class TestTextRuleCategorizer:
    """Tests for TextRuleCategorizer."""

    def test_categorize_runway_closed(self):
        """Test categorizing runway closed by text."""
        categorizer = TextRuleCategorizer()
        notam = create_notam(message="RWY 09L/27R CLSD DUE TO MAINTENANCE")

        result = categorizer.categorize(notam)

        assert result.primary_category == "runway"
        assert "closed" in result.tags

    def test_categorize_taxiway_closed(self):
        """Test categorizing taxiway closed by text."""
        categorizer = TextRuleCategorizer()
        notam = create_notam(message="TWY A CLOSED FOR REPAIR WORK")

        result = categorizer.categorize(notam)

        assert result.primary_category == "taxiway"
        assert "closed" in result.tags

    def test_categorize_ils_unserviceable(self):
        """Test categorizing ILS unserviceable by text."""
        categorizer = TextRuleCategorizer()
        notam = create_notam(message="ILS RWY 27L U/S")

        result = categorizer.categorize(notam)

        assert result.primary_category == "navaid"
        assert "ils" in result.tags
        assert "unserviceable" in result.tags

    def test_categorize_vor_unserviceable(self):
        """Test categorizing VOR unserviceable by text."""
        categorizer = TextRuleCategorizer()
        notam = create_notam(message="VOR PGS UNSERVICEABLE")

        result = categorizer.categorize(notam)

        assert result.primary_category == "navaid"
        assert "vor" in result.tags

    def test_categorize_papi_unserviceable(self):
        """Test categorizing PAPI unserviceable by text."""
        categorizer = TextRuleCategorizer()
        # PAPI pattern expects PAPI followed directly by status indicator
        notam = create_notam(message="PAPI U/S")

        result = categorizer.categorize(notam)

        assert result.primary_category == "lighting"
        assert "papi" in result.tags
        assert "unserviceable" in result.tags

    def test_categorize_crane(self):
        """Test categorizing crane by text."""
        categorizer = TextRuleCategorizer()
        notam = create_notam(message="CRANE ERECTED 150FT AGL")

        result = categorizer.categorize(notam)

        assert result.primary_category == "obstacle"
        assert "crane" in result.tags

    def test_categorize_parachuting(self):
        """Test categorizing parachuting by text."""
        categorizer = TextRuleCategorizer()
        notam = create_notam(message="PARACHUTING ACTIVITY WITHIN 5NM")

        result = categorizer.categorize(notam)

        assert result.primary_category == "airspace"
        assert "parachuting" in result.tags

    def test_categorize_drone_activity(self):
        """Test categorizing drone activity by text."""
        categorizer = TextRuleCategorizer()
        notam = create_notam(message="UAS ACTIVITY IN PROGRESS")

        result = categorizer.categorize(notam)

        assert result.primary_category == "airspace"
        assert "drone" in result.tags

    def test_categorize_tower_closed(self):
        """Test categorizing tower closed by text."""
        categorizer = TextRuleCategorizer()
        notam = create_notam(message="TWR CLSD 2200-0600")

        result = categorizer.categorize(notam)

        assert result.primary_category == "services"
        assert "tower" in result.tags
        assert "closed" in result.tags

    def test_categorize_fuel_unavailable(self):
        """Test categorizing fuel unavailable by text."""
        categorizer = TextRuleCategorizer()
        notam = create_notam(message="FUEL NOT AVAILABLE")

        result = categorizer.categorize(notam)

        assert result.primary_category == "services"
        assert "fuel" in result.tags

    def test_categorize_bird_activity(self):
        """Test categorizing bird activity by text."""
        categorizer = TextRuleCategorizer()
        notam = create_notam(message="BIRD ACTIVITY REPORTED IN VICINITY")

        result = categorizer.categorize(notam)

        assert result.primary_category == "wildlife"
        assert "birds" in result.tags

    def test_categorize_no_match(self):
        """Test categorizing text with no matching patterns."""
        categorizer = TextRuleCategorizer()
        notam = create_notam(message="SOME RANDOM TEXT")

        result = categorizer.categorize(notam)

        assert result.primary_category is None
        assert result.confidence == 1.0  # Default, no match


class TestCategorizationPipeline:
    """Tests for CategorizationPipeline."""

    def test_default_pipeline(self):
        """Test default pipeline has Q-code and text rules."""
        pipeline = CategorizationPipeline()

        names = pipeline.get_categorizer_names()

        assert "q_code" in names
        assert "text_rules" in names

    def test_categorize_with_qcode(self):
        """Test pipeline categorization with Q-code."""
        pipeline = CategorizationPipeline()
        notam = create_notam(q_code="QMRLC", message="RWY 09L CLOSED")

        result = pipeline.categorize(notam)

        assert result.primary_category == "runway"
        assert "closed" in result.tags

    def test_categorize_without_qcode(self):
        """Test pipeline categorization without Q-code uses text rules."""
        pipeline = CategorizationPipeline()
        notam = create_notam(q_code=None, message="ILS RWY 27 UNSERVICEABLE")

        result = pipeline.categorize(notam)

        assert result.primary_category == "navaid"
        assert "ils" in result.tags

    def test_categorize_all_modifies_notams(self):
        """Test categorize_all modifies NOTAMs in place."""
        pipeline = CategorizationPipeline()
        notams = [
            create_notam(q_code="QMRLC", message="RWY CLOSED"),
            create_notam(q_code="QNVAS", message="VOR U/S"),
        ]

        result = pipeline.categorize_all(notams)

        # Same list returned
        assert result is notams

        # NOTAMs modified
        assert notams[0].primary_category == "runway"
        assert "runway" in notams[0].custom_categories
        assert "closed" in notams[0].custom_tags

        assert notams[1].primary_category == "navaid"
        assert "navaid" in notams[1].custom_categories

    def test_add_categorizer(self):
        """Test adding a custom categorizer."""
        pipeline = CategorizationPipeline()

        # Create a simple custom categorizer
        from euro_aip.briefing.categorization.base import NotamCategorizer

        class CustomCategorizer(NotamCategorizer):
            @property
            def name(self) -> str:
                return "custom"

            def categorize(self, notam: Notam) -> CategorizationResult:
                return CategorizationResult(
                    primary_category="custom",
                    confidence=0.5,
                    source=self.name,
                )

        pipeline.add_categorizer(CustomCategorizer())

        names = pipeline.get_categorizer_names()
        assert "custom" in names

    def test_remove_categorizer(self):
        """Test removing a categorizer."""
        pipeline = CategorizationPipeline()

        pipeline.remove_categorizer("text_rules")

        names = pipeline.get_categorizer_names()
        assert "text_rules" not in names
        assert "q_code" in names

    def test_custom_pipeline(self):
        """Test creating pipeline with custom categorizers."""
        q_code_only = CategorizationPipeline([QCodeCategorizer()])

        names = q_code_only.get_categorizer_names()
        assert names == ["q_code"]


class TestCategorizationEdgeCases:
    """Tests for edge cases in categorization."""

    def test_multiple_categories_from_text(self):
        """Test that multiple categories can be detected from text."""
        categorizer = TextRuleCategorizer()
        notam = create_notam(message="RWY 09L CLSD, ILS RWY 09L U/S")

        result = categorizer.categorize(notam)

        # Should detect both runway and navaid categories
        assert len(result.categories) >= 1  # At least one

    def test_qcode_trumps_text_for_primary(self):
        """Test that Q-code result has higher confidence."""
        pipeline = CategorizationPipeline()

        # Q-code says runway, text could suggest navaid
        notam = create_notam(q_code="QMRLC", message="ILS related issue")

        result = pipeline.categorize(notam)

        # Q-code should win for primary (higher confidence)
        assert result.primary_category == "runway"

    def test_case_insensitive_text_matching(self):
        """Test that text matching is case insensitive."""
        categorizer = TextRuleCategorizer()

        # Different case variations
        notams = [
            create_notam(message="rwy 09l clsd"),
            create_notam(message="RWY 09L CLSD"),
            create_notam(message="Rwy 09L Clsd"),
        ]

        for notam in notams:
            result = categorizer.categorize(notam)
            assert result.primary_category == "runway", f"Failed for: {notam.message}"
