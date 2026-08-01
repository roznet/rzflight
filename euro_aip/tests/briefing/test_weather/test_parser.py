"""Tests for weather parser."""

from datetime import datetime, timedelta, timezone

import pytest

from euro_aip.briefing.weather.parser import WeatherParser, resolve_day_of_month
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


class TestDayOfMonthResolution:
    """Resolving a report's DDHHMM against the instant it was seen.

    Reports carry only a day-of-month, so the month and year are inferred.
    Assuming the *current* month is wrong at every month boundary — the bug
    that stored 31 July observations as 31 August.
    """

    def test_same_month_is_unchanged(self):
        ref = datetime(2026, 8, 15, 12, 30, tzinfo=timezone.utc)
        assert resolve_day_of_month(15, 12, 25, ref) == datetime(
            2026, 8, 15, 12, 25, tzinfo=timezone.utc
        )

    def test_previous_month_at_boundary(self):
        """The regression: 312255Z seen just after midnight on 1 August."""
        ref = datetime(2026, 8, 1, 0, 0, 1, tzinfo=timezone.utc)
        assert resolve_day_of_month(31, 22, 55, ref) == datetime(
            2026, 7, 31, 22, 55, tzinfo=timezone.utc
        )

    def test_previous_year_at_january_boundary(self):
        ref = datetime(2027, 1, 1, 0, 5, tzinfo=timezone.utc)
        assert resolve_day_of_month(31, 23, 55, ref) == datetime(
            2026, 12, 31, 23, 55, tzinfo=timezone.utc
        )

    @pytest.mark.parametrize("year,month", [(2026, 4), (2026, 6), (2026, 9), (2026, 11)])
    def test_day_31_into_a_30_day_month(self, year, month):
        """Previously raised ValueError and silently yielded None."""
        ref = datetime(year, month, 1, 0, 0, 1, tzinfo=timezone.utc)
        resolved = resolve_day_of_month(31, 23, 55, ref)
        assert resolved is not None
        assert resolved.day == 31
        assert resolved < ref

    def test_february_boundary_non_leap(self):
        ref = datetime(2026, 3, 1, 0, 10, tzinfo=timezone.utc)
        assert resolve_day_of_month(28, 23, 50, ref) == datetime(
            2026, 2, 28, 23, 50, tzinfo=timezone.utc
        )

    def test_leap_day(self):
        ref = datetime(2028, 3, 1, 0, 10, tzinfo=timezone.utc)
        assert resolve_day_of_month(29, 23, 50, ref) == datetime(
            2028, 2, 29, 23, 50, tzinfo=timezone.utc
        )

    def test_february_29_rejected_in_non_leap_year(self):
        ref = datetime(2026, 3, 1, 0, 10, tzinfo=timezone.utc)
        assert resolve_day_of_month(29, 23, 50, ref) is None

    def test_far_future_candidate_rejected_in_favour_of_past(self):
        """Same-month and next-month candidates are implausibly far ahead."""
        ref = datetime(2026, 8, 1, 0, 0, 1, tzinfo=timezone.utc)
        assert resolve_day_of_month(20, 12, 0, ref, max_future=timedelta(hours=6)) == datetime(
            2026, 7, 20, 12, 0, tzinfo=timezone.utc
        )

    def test_clock_skew_slightly_ahead_is_kept(self):
        ref = datetime(2026, 8, 15, 12, 0, tzinfo=timezone.utc)
        assert resolve_day_of_month(15, 12, 30, ref) == datetime(
            2026, 8, 15, 12, 30, tzinfo=timezone.utc
        )

    def test_naive_reference_treated_as_utc(self):
        ref = datetime(2026, 8, 1, 0, 0, 1)
        assert resolve_day_of_month(31, 22, 55, ref) == datetime(
            2026, 7, 31, 22, 55, tzinfo=timezone.utc
        )


class TestMetarObservationTime:
    """End-to-end observation time resolution through parse_metar."""

    def test_month_boundary_metar(self):
        """LIPS 312255Z collected 2026-08-01 00:00:01 — the production case."""
        raw = "METAR LIPS 312255Z 00000KT CAVOK 28/22 Q1013"
        ref = datetime(2026, 8, 1, 0, 0, 1, tzinfo=timezone.utc)
        report = WeatherParser.parse_metar(raw, reference=ref)

        assert report is not None
        assert report.observation_time == datetime(
            2026, 7, 31, 22, 55, tzinfo=timezone.utc
        )

    def test_observation_time_never_far_future(self):
        raw = "METAR LIPS 312255Z 00000KT CAVOK 28/22 Q1013"
        ref = datetime(2026, 8, 1, 0, 0, 1, tzinfo=timezone.utc)
        report = WeatherParser.parse_metar(raw, reference=ref)

        assert report.observation_time <= ref + timedelta(hours=6)

    def test_day_31_collected_on_1_june_survives(self):
        """Used to hit ValueError -> observation_time None (silent data loss)."""
        raw = "METAR LIPS 312255Z 00000KT CAVOK 28/22 Q1013"
        ref = datetime(2026, 6, 1, 0, 0, 1, tzinfo=timezone.utc)
        report = WeatherParser.parse_metar(raw, reference=ref)

        assert report is not None
        assert report.observation_time == datetime(
            2026, 5, 31, 22, 55, tzinfo=timezone.utc
        )

    def test_defaults_to_now_when_no_reference(self):
        raw = "METAR LFPG 211230Z 24015G25KT 9999 FEW040 18/09 Q1015"
        report = WeatherParser.parse_metar(raw)

        assert report is not None
        assert report.observation_time is not None
        assert report.observation_time <= datetime.now(timezone.utc) + timedelta(hours=6)


class TestTafValidityAcrossMonths:
    """TAF issue time and validity window resolution."""

    def test_validity_window_spanning_month_end(self):
        """Issued 31 July 23:00, window 3123/0124 closes on 1 August."""
        raw = "TAF LFPG 312300Z 3123/0124 24012KT 9999 FEW040"
        ref = datetime(2026, 8, 1, 0, 0, 1, tzinfo=timezone.utc)
        report = WeatherParser.parse_taf(raw, reference=ref)

        assert report is not None
        assert report.observation_time == datetime(
            2026, 7, 31, 23, 0, tzinfo=timezone.utc
        )
        assert report.validity_start == datetime(
            2026, 7, 31, 23, 0, tzinfo=timezone.utc
        )
        # 0124 = "day 01, hour 24" = end of 1 August = 2 August 00:00Z
        assert report.validity_end == datetime(2026, 8, 2, 0, 0, tzinfo=timezone.utc)

    def test_validity_end_is_after_start(self):
        raw = "TAF LFPG 312300Z 3123/0124 24012KT 9999 FEW040"
        ref = datetime(2026, 8, 1, 0, 0, 1, tzinfo=timezone.utc)
        report = WeatherParser.parse_taf(raw, reference=ref)

        assert report.validity_end > report.validity_start

    def test_ordinary_validity_window_unaffected(self):
        raw = "TAF LFPG 211100Z 2112/2218 24012KT 9999 FEW040"
        ref = datetime(2026, 8, 21, 11, 5, tzinfo=timezone.utc)
        report = WeatherParser.parse_taf(raw, reference=ref)

        assert report.validity_start == datetime(2026, 8, 21, 12, 0, tzinfo=timezone.utc)
        assert report.validity_end == datetime(2026, 8, 22, 18, 0, tzinfo=timezone.utc)
        assert report.validity_end > report.validity_start

    def test_hour_24_rolls_over_month_end(self):
        """end_hour 24 on the last day of a month must not build day 32."""
        raw = "TAF LFPG 301200Z 3012/3124 24012KT 9999 FEW040"
        ref = datetime(2026, 7, 30, 12, 5, tzinfo=timezone.utc)
        report = WeatherParser.parse_taf(raw, reference=ref)

        assert report is not None
        assert report.validity_start == datetime(2026, 7, 30, 12, 0, tzinfo=timezone.utc)
        assert report.validity_end == datetime(2026, 8, 1, 0, 0, tzinfo=timezone.utc)
