"""Tests for NOTAM parser."""

import pytest
from datetime import datetime

from euro_aip.briefing.parsers.notam_parser import NotamParser
from euro_aip.briefing.models.notam import NotamCategory


class TestNotamParser:
    """Tests for NotamParser."""

    def test_parse_full_notam(self):
        """Test parsing a complete ICAO format NOTAM."""
        text = """
        A1234/24 NOTAMN
        Q) LFFF/QMRLC/IV/NBO/A/000/999/4901N00225E005
        A) LFPG B) 2401150800 C) 2401152000
        E) RWY 09L/27R CLSD DUE TO MAINTENANCE
        """

        notam = NotamParser.parse(text)

        assert notam is not None
        assert notam.id == "A1234/24"
        assert notam.series == "A"
        assert notam.number == 1234
        assert notam.year == 24
        assert notam.location == "LFPG"
        assert notam.fir == "LFFF"
        assert notam.q_code == "QMRLC"
        assert notam.traffic_type == "IV"
        assert notam.purpose == "NBO"
        assert notam.scope == "A"
        assert "RWY 09L/27R CLSD" in notam.message
        assert notam.category == NotamCategory.RUNWAY

    def test_parse_notam_coordinates(self):
        """Test coordinate parsing from Q-line."""
        text = """
        B5678/24 NOTAMN
        Q) EGTT/QWPLW/IV/BO/W/000/050/5130N00030W010
        A) EGTT B) 2401200900 C) 2401201700
        E) PARACHUTING ACTIVITY
        """

        notam = NotamParser.parse(text)

        assert notam is not None
        assert notam.coordinates is not None
        lat, lon = notam.coordinates
        assert 51.4 < lat < 51.6  # 5130N
        assert -0.6 < lon < -0.4  # 00030W

    def test_parse_permanent_notam(self):
        """Test parsing a permanent NOTAM."""
        text = """
        C9999/24 NOTAMN
        Q) LFFF/QOBCE/IV/M/AW/000/100/4850N00220E005
        A) LFPG B) 2401010000 C) PERM
        E) CRANE ERECTED 150FT AGL
        """

        notam = NotamParser.parse(text)

        assert notam is not None
        assert notam.is_permanent is True
        assert notam.effective_to is None

    def test_parse_effective_times(self):
        """Test parsing B and C line times."""
        text = """
        D1111/24 NOTAMN
        Q) EGTT/QMXLC/IV/NBO/A/000/999/5128N00027W003
        A) EGLL B) 2403150600 C) 2403151800
        E) TWY A CLSD
        """

        notam = NotamParser.parse(text)

        assert notam is not None
        assert notam.effective_from is not None
        assert notam.effective_from.year == 2024
        assert notam.effective_from.month == 3
        assert notam.effective_from.day == 15
        assert notam.effective_from.hour == 6

        assert notam.effective_to is not None
        assert notam.effective_to.hour == 18

    def test_parse_notam_without_qline(self):
        """Test parsing NOTAM without Q-line."""
        text = """
        E2222/24 NOTAMN
        A) EHAM B) 2402010000 C) 2402282359
        E) ILS RWY 18R U/S
        """

        notam = NotamParser.parse(text)

        assert notam is not None
        assert notam.location == "EHAM"
        assert "ILS RWY 18R U/S" in notam.message

    def test_parse_many_notams(self):
        """Test parsing multiple NOTAMs from a block."""
        text = """
        A0001/24 NOTAMN
        Q) LFFF/QMRLC/IV/NBO/A/000/999/4901N00225E005
        A) LFPG B) 2401010000 C) 2401011200
        E) RWY 08L/26R CLSD

        A0002/24 NOTAMN
        Q) LFFF/QMXLC/IV/NBO/A/000/999/4901N00225E003
        A) LFPG B) 2401010000 C) 2401011200
        E) TWY B CLSD

        A0003/24 NOTAMN
        Q) LFFF/QNVAS/IV/BO/A/000/999/4900N00224E010
        A) LFPG B) 2401020000 C) 2401030000
        E) VOR PGS U/S
        """

        notams = NotamParser.parse_many(text)

        assert len(notams) == 3
        assert notams[0].id == "A0001/24"
        assert notams[1].id == "A0002/24"
        assert notams[2].id == "A0003/24"

        # Check categories
        assert notams[0].category == NotamCategory.RUNWAY
        assert notams[1].category == NotamCategory.MOVEMENT_AREA
        assert notams[2].category == NotamCategory.NAVIGATION

    def test_parse_q_code(self):
        """Test Q-code decoding."""
        result = NotamParser.parse_q_code("QMRLC")

        assert result['code'] == "MRLC"
        assert result['prefix'] == "MR"
        assert result['suffix'] == "LC"
        assert result['category'] == NotamCategory.RUNWAY
        assert result['suffix_meaning'] == "closed"

    def test_parse_category_from_qcode(self):
        """Test category determination from various Q-codes."""
        test_cases = [
            ("QMRLC", NotamCategory.RUNWAY),
            ("QMXLC", NotamCategory.MOVEMENT_AREA),
            ("QLRAS", NotamCategory.LIGHTING),
            ("QNVAS", NotamCategory.NAVIGATION),
            ("QNIAS", NotamCategory.NAVIGATION),
            ("QOBCE", NotamCategory.OBSTACLE),
            ("QPICH", NotamCategory.PROCEDURE),
            ("QARAU", NotamCategory.AIRSPACE),
            ("QWPLW", NotamCategory.WARNING),
        ]

        for q_code, expected_category in test_cases:
            text = f"""
            X0000/24 NOTAMN
            Q) LFFF/{q_code}/IV/NBO/A/000/999/4901N00225E005
            A) LFPG B) 2401010000 C) 2401010100
            E) TEST
            """
            notam = NotamParser.parse(text)
            assert notam.category == expected_category, f"Failed for {q_code}"

    def test_parse_altitude_limits(self):
        """Test altitude limit parsing from Q-line."""
        text = """
        F1111/24 NOTAMN
        Q) EGTT/QARAU/IV/BO/W/050/150/5130N00030W020
        A) EGTT B) 2401200900 C) 2401201700
        E) RESTRICTED AREA ACTIVE FL050-FL150
        """

        notam = NotamParser.parse(text)

        assert notam is not None
        assert notam.lower_limit == 5000  # FL050 = 5000ft
        assert notam.upper_limit == 15000  # FL150 = 15000ft

    def test_parse_abbreviated_format(self):
        """Test parsing abbreviated NOTAM format often found in briefings."""
        text = """
        G2345/24
        LFPG RWY 09R/27L CLSD 0600-1400 DUE MAINTENANCE
        """

        notam = NotamParser.parse(text)

        assert notam is not None
        assert "G2345/24" in notam.id
        assert "RWY 09R/27L CLSD" in notam.message or "RWY 09R/27L CLSD" in notam.raw_text

    def test_parse_fdc_notam(self):
        """Test parsing FDC-style NOTAM."""
        text = """
        FDC 4/1234 NOTAMN
        A) KORD B) 2401150000 C) 2401160000
        E) ILS RWY 10L, AMDT 5, CHANGE DA TO 2500
        """

        notam = NotamParser.parse(text)

        assert notam is not None
        assert notam.location == "KORD"
        assert "ILS RWY 10L" in notam.message

    def test_parse_empty_text(self):
        """Test parsing empty text returns None."""
        assert NotamParser.parse("") is None
        assert NotamParser.parse("   ") is None
        assert NotamParser.parse_many("") == []

    def test_source_attribution(self):
        """Test that source is properly attributed."""
        text = """
        A1234/24 NOTAMN
        A) LFPG B) 2401010000 C) 2401010100
        E) TEST
        """

        notam = NotamParser.parse(text, source="test_source")

        assert notam is not None
        assert notam.source == "test_source"
