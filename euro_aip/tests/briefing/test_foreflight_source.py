"""Tests for ForeFlight source."""

import pytest
from datetime import datetime

from euro_aip.briefing.sources.foreflight import ForeFlightSource
from euro_aip.briefing.models.briefing import Briefing


class TestForeFlightSource:
    """Tests for ForeFlightSource."""

    def test_parse_text_simple(self):
        """Test parsing text with simple NOTAM."""
        source = ForeFlightSource()

        text = """
        Route: LFPG EGLL

        LFPG NOTAMs:

        A1234/24 NOTAMN
        Q) LFFF/QMRLC/IV/NBO/A/000/999/4901N00225E005
        A) LFPG B) 2401150800 C) 2401152000
        E) RWY 09L/27R CLSD DUE TO MAINTENANCE
        """

        briefing = source.parse_text(text)

        assert briefing is not None
        assert briefing.source == "foreflight"
        assert briefing.route is not None
        assert briefing.route.departure == "LFPG"
        assert briefing.route.destination == "EGLL"
        assert len(briefing.notams) >= 1

    def test_parse_text_multiple_notams(self):
        """Test parsing text with multiple NOTAMs."""
        source = ForeFlightSource()

        text = """
        LFPG NOTAMs:

        A0001/24 NOTAMN
        Q) LFFF/QMRLC/IV/NBO/A/000/999/4901N00225E005
        A) LFPG B) 2401010000 C) 2401011200
        E) RWY 08L/26R CLSD

        A0002/24 NOTAMN
        Q) LFFF/QNVAS/IV/BO/A/000/999/4900N00224E010
        A) LFPG B) 2401020000 C) 2401030000
        E) VOR PGS U/S
        """

        briefing = source.parse_text(text)

        assert len(briefing.notams) == 2
        assert briefing.notams[0].id == "A0001/24"
        assert briefing.notams[1].id == "A0002/24"

    def test_parse_text_with_route_extraction(self):
        """Test route extraction from briefing text."""
        source = ForeFlightSource()

        text = """
        From: EHAM To: LEMD
        Alternate: LEBL

        EHAM NOTAMs:
        A1111/24 NOTAMN
        A) EHAM B) 2401010000 C) 2401010100
        E) TEST
        """

        briefing = source.parse_text(text)

        assert briefing.route is not None
        assert briefing.route.departure == "EHAM"
        assert briefing.route.destination == "LEMD"
        # Alternates extracted
        assert "LEBL" in briefing.route.alternates

    def test_briefing_notams_query(self):
        """Test that briefing provides queryable collection."""
        source = ForeFlightSource()

        text = """
        A0001/24 NOTAMN
        Q) LFFF/QMRLC/IV/NBO/A/000/999/4901N00225E005
        A) LFPG B) 2401010000 C) 2401010100
        E) RWY 09L CLSD

        A0002/24 NOTAMN
        Q) LFFF/QNVAS/IV/BO/A/000/999/4900N00224E010
        A) EGLL B) 2401020000 C) 2401030000
        E) VOR LON U/S
        """

        briefing = source.parse_text(text)

        # Test queryable collection
        lfpg_notams = briefing.notams_query.for_airport("LFPG").all()
        assert len(lfpg_notams) == 1
        assert lfpg_notams[0].location == "LFPG"

    def test_supported_formats(self):
        """Test that source reports supported formats."""
        source = ForeFlightSource()
        assert "pdf" in source.get_supported_formats()

    def test_empty_text(self):
        """Test handling of empty text."""
        source = ForeFlightSource()
        briefing = source.parse_text("")

        assert briefing is not None
        assert len(briefing.notams) == 0


class TestForeFlightIntegration:
    """Integration tests for ForeFlight source with categorization."""

    def test_full_pipeline(self):
        """Test full parsing and categorization pipeline."""
        from euro_aip.briefing.categorization.pipeline import CategorizationPipeline

        source = ForeFlightSource()
        pipeline = CategorizationPipeline()

        text = """
        Route: LFPG EGLL

        A1234/24 NOTAMN
        Q) LFFF/QMRLC/IV/NBO/A/000/999/4901N00225E005
        A) LFPG B) 2401150800 C) 2401152000
        E) RWY 09L/27R CLSD DUE TO MAINTENANCE

        B5678/24 NOTAMN
        Q) EGTT/QNIAS/IV/BO/A/000/999/5128N00027W005
        A) EGLL B) 2401150800 C) 2401152000
        E) ILS RWY 27L U/S
        """

        # Parse
        briefing = source.parse_text(text)

        # Categorize
        pipeline.categorize_all(briefing.notams)

        # Verify categorization
        runway_notams = briefing.notams_query.runway_related().all()
        navaid_notams = briefing.notams_query.navigation_related().all()

        assert len(runway_notams) >= 1
        assert len(navaid_notams) >= 1

        # Check primary categories were set
        for notam in briefing.notams:
            assert notam.primary_category is not None

    def test_briefing_serialization(self):
        """Test briefing can be serialized to JSON and back."""
        source = ForeFlightSource()

        text = """
        A1234/24 NOTAMN
        Q) LFFF/QMRLC/IV/NBO/A/000/999/4901N00225E005
        A) LFPG B) 2401150800 C) 2401152000
        E) RWY 09L/27R CLSD
        """

        briefing = source.parse_text(text)

        # Serialize
        json_str = briefing.to_json()

        # Deserialize
        restored = Briefing.from_json(json_str)

        assert restored.source == briefing.source
        assert len(restored.notams) == len(briefing.notams)
        assert restored.notams[0].id == briefing.notams[0].id
        assert restored.notams[0].location == briefing.notams[0].location
