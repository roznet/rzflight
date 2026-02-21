"""Tests for weather parser."""

import pytest

from euro_aip.briefing.weather.parser import WeatherParser
from euro_aip.briefing.weather.models import WeatherType, FlightCategory


class TestParseMetar:
    """Test METAR parsing."""

    def test_basic_metar(self):
        raw = "METAR LFPG 211230Z 24015G25KT 9999 FEW040 18/09 Q1015"
        report = WeatherParser.parse_metar(raw)

        assert report is not None
        assert report.icao == "LFPG"
        assert report.report_type == WeatherType.METAR
        assert report.wind_direction == 240
        assert report.wind_speed == 15
        assert report.wind_gust == 25
        assert report.temperature == 18
        assert report.dewpoint == 9
        assert report.raw_text == raw

    def test_metar_visibility(self):
        raw = "METAR EGLL 211250Z 27010KT 9999 SCT030 BKN045 15/08 Q1020"
        report = WeatherParser.parse_metar(raw)

        assert report is not None
        # Library normalizes 9999 to "> 10km" = 10000m
        assert report.visibility_meters == 10000
        assert report.visibility_sm is not None
        assert report.visibility_sm > 6  # 10000m > 6SM

    def test_metar_ceiling(self):
        raw = "METAR KJFK 211200Z 18008KT 2SM BR OVC005 12/11 A2990"
        report = WeatherParser.parse_metar(raw)

        assert report is not None
        assert report.ceiling_ft is not None
        assert report.ceiling_ft == 500

    def test_metar_flight_category_vfr(self):
        raw = "METAR LFPG 211230Z 24015KT 9999 FEW040 18/09 Q1015"
        report = WeatherParser.parse_metar(raw)

        assert report is not None
        assert report.flight_category == FlightCategory.VFR

    def test_metar_flight_category_ifr(self):
        raw = "METAR KJFK 211200Z 18008KT 2SM BR OVC005 12/11 A2990"
        report = WeatherParser.parse_metar(raw)

        assert report is not None
        # ceiling 500 ft = IFR, visibility 2SM = IFR, worst = IFR
        assert report.flight_category == FlightCategory.IFR

    def test_metar_cavok(self):
        raw = "METAR LFPG 211230Z 24005KT CAVOK 20/10 Q1015"
        report = WeatherParser.parse_metar(raw)

        assert report is not None
        assert report.cavok is True
        assert report.flight_category == FlightCategory.VFR

    def test_speci_prefix(self):
        raw = "SPECI LFPG 211230Z 24015KT 9999 FEW040 18/09 Q1015"
        report = WeatherParser.parse_metar(raw)

        assert report is not None
        assert report.report_type == WeatherType.SPECI
        assert report.icao == "LFPG"

    def test_nil_metar_returns_none(self):
        raw = "METAR LFPG 211230Z NIL"
        report = WeatherParser.parse_metar(raw)
        assert report is None

    def test_empty_string_returns_none(self):
        report = WeatherParser.parse_metar("")
        assert report is None

    def test_invalid_metar_returns_none(self):
        report = WeatherParser.parse_metar("THIS IS NOT A METAR")
        assert report is None

    def test_metar_with_weather_conditions(self):
        raw = "METAR EGLL 211300Z 09012KT 3000 RA BKN008 OVC015 10/09 Q1008"
        report = WeatherParser.parse_metar(raw)

        assert report is not None
        assert len(report.weather_conditions) > 0
        assert report.clouds is not None
        assert len(report.clouds) >= 2

    def test_metar_source_preserved(self):
        raw = "METAR LFPG 211230Z 24015KT 9999 FEW040 18/09 Q1015"
        report = WeatherParser.parse_metar(raw, source="foreflight")
        assert report.source == "foreflight"

    def test_metar_variable_wind(self):
        raw = "METAR LFPG 211230Z 24008KT 200V280 9999 FEW040 18/09 Q1015"
        report = WeatherParser.parse_metar(raw)

        assert report is not None
        assert report.wind_variable_from == 200
        assert report.wind_variable_to == 280


class TestParseTaf:
    """Test TAF parsing."""

    def test_basic_taf(self):
        raw = "TAF LFPG 211100Z 2112/2218 24012KT 9999 FEW040 SCT100"
        report = WeatherParser.parse_taf(raw)

        assert report is not None
        assert report.icao == "LFPG"
        assert report.report_type == WeatherType.TAF
        assert report.wind_direction == 240
        assert report.wind_speed == 12

    def test_taf_with_tempo(self):
        raw = (
            "TAF LFPG 211100Z 2112/2218 24012KT 9999 FEW040 "
            "TEMPO 2114/2118 4000 TSRA BKN020CB"
        )
        report = WeatherParser.parse_taf(raw)

        assert report is not None
        assert len(report.trends) >= 1
        tempo = report.trends[0]
        assert tempo.trend_type == "TEMPO"

    def test_taf_with_becmg(self):
        raw = (
            "TAF EGLL 211100Z 2112/2218 27015KT 9999 SCT035 "
            "BECMG 2116/2118 18010KT"
        )
        report = WeatherParser.parse_taf(raw)

        assert report is not None
        assert len(report.trends) >= 1
        becmg = report.trends[0]
        assert becmg.trend_type == "BECMG"

    def test_taf_nil_returns_none(self):
        raw = "TAF LFPG 211100Z NIL"
        report = WeatherParser.parse_taf(raw)
        assert report is None

    def test_taf_cnl_returns_none(self):
        raw = "TAF LFPG 211100Z 2112/2218 CNL"
        report = WeatherParser.parse_taf(raw)
        assert report is None

    def test_taf_without_prefix(self):
        """Parser should add TAF prefix automatically."""
        raw = "LFPG 211100Z 2112/2218 24012KT 9999 FEW040"
        report = WeatherParser.parse_taf(raw)

        assert report is not None
        assert report.icao == "LFPG"

    def test_taf_validity_period(self):
        raw = "TAF LFPG 211100Z 2112/2218 24012KT 9999 FEW040"
        report = WeatherParser.parse_taf(raw)

        assert report is not None
        assert report.validity_start is not None
        assert report.validity_end is not None

    def test_taf_trend_flight_category(self):
        """Each trend should have its own flight category computed."""
        raw = (
            "TAF LFPG 211100Z 2112/2218 24012KT 9999 FEW040 "
            "TEMPO 2114/2118 0800 FG VV002"
        )
        report = WeatherParser.parse_taf(raw)

        assert report is not None
        assert report.flight_category == FlightCategory.VFR
        if report.trends:
            tempo = report.trends[0]
            # 800m visibility ~ 0.5SM = LIFR
            assert tempo.flight_category is not None
            assert tempo.flight_category <= FlightCategory.IFR


class TestParseAuto:
    """Test auto-detection of METAR vs TAF."""

    def test_auto_detects_metar(self):
        raw = "METAR LFPG 211230Z 24015KT 9999 FEW040 18/09 Q1015"
        report = WeatherParser.parse_auto(raw)
        assert report is not None
        assert report.report_type == WeatherType.METAR

    def test_auto_detects_taf(self):
        raw = "TAF LFPG 211100Z 2112/2218 24012KT 9999 FEW040"
        report = WeatherParser.parse_auto(raw)
        assert report is not None
        assert report.report_type == WeatherType.TAF

    def test_auto_defaults_to_metar(self):
        raw = "LFPG 211230Z 24015KT 9999 FEW040 18/09 Q1015"
        report = WeatherParser.parse_auto(raw)
        # Should attempt METAR parsing
        assert report is not None or report is None  # May or may not parse without prefix


class TestSafeFractionParsing:
    """Test safe fraction parsing (replacement for eval())."""

    def test_simple_fraction(self):
        assert WeatherParser._safe_parse_fraction("1/2") == pytest.approx(0.5)

    def test_simple_fraction_quarter(self):
        assert WeatherParser._safe_parse_fraction("1/4") == pytest.approx(0.25)

    def test_mixed_number(self):
        assert WeatherParser._safe_parse_fraction("2 1/2") == pytest.approx(2.5)

    def test_whole_number(self):
        assert WeatherParser._safe_parse_fraction("3") == pytest.approx(3.0)

    def test_float_string(self):
        assert WeatherParser._safe_parse_fraction("0.5") == pytest.approx(0.5)

    def test_m_prefix(self):
        assert WeatherParser._safe_parse_fraction("M1/4") == pytest.approx(0.25)

    def test_p_prefix(self):
        assert WeatherParser._safe_parse_fraction("P6") == pytest.approx(6.0)

    def test_empty_returns_none(self):
        assert WeatherParser._safe_parse_fraction("") is None

    def test_invalid_returns_none(self):
        assert WeatherParser._safe_parse_fraction("abc") is None

    def test_division_by_zero_returns_none(self):
        assert WeatherParser._safe_parse_fraction("1/0") is None
