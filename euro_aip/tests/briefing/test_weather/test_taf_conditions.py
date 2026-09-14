"""Tests for WeatherAnalyzer.taf_conditions_at / taf_covers.

The fixtures are real TAFs from a 2026-09-13 briefing where the old
"last matching group wins" selection went wrong.
"""

from datetime import datetime, timezone

from euro_aip.briefing.weather import FlightCategory, WeatherAnalyzer, WeatherReport


def _utc(day, hour, month=9, year=2026):
    return datetime(year, month, day, hour, tzinfo=timezone.utc)


def _taf(raw, issued):
    return WeatherReport.from_taf(raw, reference=issued)


class TestTafCovers:

    def test_expired_taf_does_not_cover(self):
        """A TAF from two days earlier is not a forecast for today."""
        taf = _taf("TAF EGSC 111404Z 1115/1117 29006KT 9999 SCT035", _utc(11, 14))
        assert WeatherAnalyzer.taf_covers(taf, _utc(11, 16))
        assert not WeatherAnalyzer.taf_covers(taf, _utc(13, 13))
        assert WeatherAnalyzer.taf_conditions_at(taf, _utc(13, 13)) is None

    def test_validity_bounds_are_inclusive(self):
        taf = _taf("TAF EGSC 111404Z 1115/1117 29006KT 9999 SCT035", _utc(11, 14))
        assert WeatherAnalyzer.taf_covers(taf, _utc(11, 15))
        assert WeatherAnalyzer.taf_covers(taf, _utc(11, 17))
        assert not WeatherAnalyzer.taf_covers(taf, _utc(11, 18))

    def test_unknown_validity_does_not_cover(self):
        assert not WeatherAnalyzer.taf_covers(WeatherReport(), _utc(13, 13))

    def test_month_crossing_validity(self):
        taf = _taf("TAF LFPG 301700Z 3018/0124 24012KT 9999 FEW040", _utc(30, 17))
        assert WeatherAnalyzer.taf_covers(taf, _utc(1, 6, month=10))


class TestPrevailing:

    def test_completed_becmg_is_applied(self):
        """EBLG: BECMG 1307/1309 lowers the cloud; at 13Z it is the prevailing state."""
        taf = _taf(
            "TAF EBLG 130500Z 1306/1412 23007KT 9999 SCT020 BKN040 "
            "BECMG 1307/1309 SCT009 BKN014",
            _utc(13, 5),
        )
        cond = WeatherAnalyzer.taf_conditions_at(taf, _utc(13, 13))
        assert cond.prevailing.ceiling_ft == 1400
        assert cond.prevailing.flight_category == FlightCategory.MVFR
        assert cond.prevailing_change.trend_type == "BECMG"

    def test_wind_only_becmg_keeps_cloud_and_category(self):
        """LFRK: wind-only BECMG groups used to blank the category."""
        taf = _taf(
            "TAF LFRK 130800Z 1309/1318 VRB05KT 9999 SCT040 "
            "TEMPO 1309/1310 BKN010 BECMG 1310/1312 27010KT BECMG 1312/1315 33010KT",
            _utc(13, 8),
        )
        cond = WeatherAnalyzer.taf_conditions_at(taf, _utc(13, 12))
        assert cond.prevailing.flight_category == FlightCategory.VFR
        assert cond.prevailing.wind_speed == 10
        assert cond.flight_category == FlightCategory.VFR
        assert cond.temporary == []

    def test_becmg_in_progress_takes_the_worse_state(self):
        taf = _taf(
            "TAF EGSS 130459Z 1306/1412 23008KT 9999 SCT030 BECMG 1310/1313 BKN008",
            _utc(13, 5),
        )
        during = WeatherAnalyzer.taf_conditions_at(taf, _utc(13, 11))
        assert during.prevailing.ceiling_ft == 800
        assert during.prevailing.flight_category == FlightCategory.IFR

    def test_becmg_improvement_in_progress_is_not_credited_yet(self):
        taf = _taf(
            "TAF EGSS 130459Z 1306/1412 23008KT 9999 BKN008 BECMG 1310/1313 SCT020",
            _utc(13, 5),
        )
        during = WeatherAnalyzer.taf_conditions_at(taf, _utc(13, 11))
        assert during.prevailing.flight_category == FlightCategory.IFR
        after = WeatherAnalyzer.taf_conditions_at(taf, _utc(13, 13))
        assert after.prevailing.flight_category == FlightCategory.VFR

    def test_becmg_nsc_clears_the_ceiling(self):
        taf = _taf(
            "TAF EHBK 130521Z 1306/1412 26007KT 9999 BKN014 BECMG 1310/1312 NSC",
            _utc(13, 5),
        )
        cond = WeatherAnalyzer.taf_conditions_at(taf, _utc(13, 12))
        assert cond.prevailing.ceiling_ft is None
        assert cond.prevailing.flight_category == FlightCategory.VFR

    def test_fm_replaces_prevailing(self):
        taf = _taf(
            "TAF LFPG 130500Z 1306/1412 24012KT 4000 BR OVC005 FM131200 27015G25KT CAVOK",
            _utc(13, 5),
        )
        before = WeatherAnalyzer.taf_conditions_at(taf, _utc(13, 11))
        assert before.prevailing.flight_category == FlightCategory.IFR
        after = WeatherAnalyzer.taf_conditions_at(taf, _utc(13, 13))
        assert after.prevailing.flight_category == FlightCategory.VFR
        assert after.prevailing.weather_conditions == []
        assert after.prevailing.wind_gust == 25
        assert after.prevailing_change.trend_type == "FM"


class TestTemporary:

    EGSS = (
        "TAF EGSS 130459Z 1306/1412 23008KT 9999 BKN008\n"
        "TEMPO 1306/1310 6000 -DZ BKN004\n"
        "BECMG 1310/1313 SCT020\n"
        "TEMPO 1310/1314 4000 SHRA -RADZ\n"
        "PROB30\n"
        "TEMPO 1310/1314 +SHRA"
    )

    def test_worst_temporary_is_not_the_last_listed(self):
        """EGSS: the IFR TEMPO must win over the later PROB30 TEMPO with no category."""
        taf = _taf(self.EGSS, _utc(13, 5))
        cond = WeatherAnalyzer.taf_conditions_at(taf, _utc(13, 13))
        # BECMG 1310/1313 has completed by 13Z → prevailing SCT020.
        assert cond.prevailing.flight_category == FlightCategory.VFR
        assert len(cond.temporary) == 2
        assert cond.worst_temporary.flight_category == FlightCategory.IFR
        assert cond.worst_temporary.visibility_meters == 4000
        assert cond.temporary_is_worse
        assert cond.flight_category == FlightCategory.IFR

    def test_temporary_group_inherits_prevailing_fields(self):
        """A TEMPO giving only weather still has a category, from the prevailing cloud."""
        taf = _taf(self.EGSS, _utc(13, 5))
        cond = WeatherAnalyzer.taf_conditions_at(taf, _utc(13, 13))
        prob30 = [t for t in cond.temporary if t.probability == 30][0]
        assert prob30.flight_category is not None
        assert prob30.weather_conditions == ["+SHRA"]
        assert WeatherAnalyzer.trend_label(prob30) == "PROB30 TEMPO"

    def test_temporary_is_worse_only_when_strictly_worse(self):
        taf = _taf(
            "TAF EGKA 130756Z 1308/1315 25007KT 9999 BKN016 TEMPO 1310/1315 4000 SHRA BKN009",
            _utc(13, 7),
        )
        cond = WeatherAnalyzer.taf_conditions_at(taf, _utc(13, 13))
        assert cond.prevailing.flight_category == FlightCategory.MVFR
        assert cond.worst_temporary.flight_category == FlightCategory.IFR
        assert cond.temporary_is_worse
        assert cond.flight_category == FlightCategory.IFR

    def test_temporary_outside_time_ignored(self):
        taf = _taf(
            "TAF EGKA 130756Z 1308/1318 25007KT 9999 BKN030 TEMPO 1315/1318 4000 SHRA BKN009",
            _utc(13, 7),
        )
        cond = WeatherAnalyzer.taf_conditions_at(taf, _utc(13, 13))
        assert cond.temporary == []
        assert not cond.temporary_is_worse
        assert cond.flight_category == FlightCategory.MVFR


class TestSignificantWeather:

    def test_cb_in_temporary_group(self):
        taf = _taf(
            "TAF EDDK 130500Z 1306/1412 17004KT 9999 BKN030 "
            "TEMPO 1311/1318 3000 SHRA BKN008CB",
            _utc(13, 5),
        )
        cond = WeatherAnalyzer.taf_conditions_at(taf, _utc(13, 13))
        assert cond.significant_weather == ["CB"]

    def test_ts_and_fog_and_cb_collected_once(self):
        taf = _taf(
            "TAF LFPG 130500Z 1306/1412 24012KT 4000 BR OVC005 "
            "TEMPO 1312/1316 TSRA BKN015CB PROB40 1312/1316 0700 FG VV001",
            _utc(13, 5),
        )
        cond = WeatherAnalyzer.taf_conditions_at(taf, _utc(13, 13))
        assert cond.significant_weather == ["TSRA", "FG", "CB"]

    def test_rain_and_mist_are_not_significant(self):
        taf = _taf(
            "TAF EGLL 130459Z 1306/1412 23008KT 6000 -RA BR BKN012",
            _utc(13, 4),
        )
        cond = WeatherAnalyzer.taf_conditions_at(taf, _utc(13, 13))
        assert cond.significant_weather == []
