"""Tests for the SigmetReport model and AWC parser."""

from datetime import datetime, timezone

from euro_aip.briefing.weather.sigmet import (
    SigmetReport,
    _parse_coords,
    _parse_level,
    _parse_time,
)


def sample_awc_entry(**overrides):
    """A realistic post-Sept-2025 AWC isigmet JSON object."""
    entry = {
        "icaoId": "EGTT",
        "firId": "EGTT",
        "firName": "LONDON",
        "seriesId": "A",
        "receiptTime": "2026-05-20 10:05:00",
        "validTimeFrom": "2026-05-20 10:00:00",
        "validTimeTo": "2026-05-20 14:00:00",
        "dir": "NE",
        "spd": 15,
        "hazard": "TURB",
        "severity": 2,
        "qualifier": "SEV",
        "base": 10000,
        "top": 24000,
        "geom": "AREA",
        "coords": [
            {"lat": 51.0, "lon": -2.0},
            {"lat": 52.0, "lon": -2.0},
            {"lat": 52.0, "lon": 0.0},
            {"lat": 51.0, "lon": 0.0},
            {"lat": 51.0, "lon": -2.0},
        ],
        "rawSigmet": "EGTT SIGMET 01 VALID 201000/201400 SEV TURB FCST",
    }
    entry.update(overrides)
    return entry


class TestParseLevel:
    def test_int_feet(self):
        assert _parse_level(24000) == 24000

    def test_float_feet(self):
        assert _parse_level(10000.0) == 10000

    def test_numeric_string(self):
        assert _parse_level("18000") == 18000

    def test_surface(self):
        assert _parse_level("SFC") == 0
        assert _parse_level("GND") == 0

    def test_flight_level(self):
        assert _parse_level("FL340") == 34000

    def test_with_ft_suffix(self):
        assert _parse_level("10000FT") == 10000

    def test_none(self):
        assert _parse_level(None) is None

    def test_garbage(self):
        assert _parse_level("not-a-level") is None

    def test_bool_rejected(self):
        assert _parse_level(True) is None


class TestParseTime:
    def test_space_separated(self):
        dt = _parse_time("2026-05-20 10:00:00")
        assert dt == datetime(2026, 5, 20, 10, 0, tzinfo=timezone.utc)

    def test_iso_with_t_and_z(self):
        dt = _parse_time("2026-05-20T10:00:00Z")
        assert dt == datetime(2026, 5, 20, 10, 0, tzinfo=timezone.utc)

    def test_epoch_seconds_int(self):
        dt = _parse_time(1747735200)
        assert dt.tzinfo is not None
        assert dt == datetime.fromtimestamp(1747735200, tz=timezone.utc)

    def test_epoch_seconds_string(self):
        dt = _parse_time("1747735200")
        assert dt == datetime.fromtimestamp(1747735200, tz=timezone.utc)

    def test_none_and_empty(self):
        assert _parse_time(None) is None
        assert _parse_time("") is None

    def test_garbage(self):
        assert _parse_time("nonsense") is None

    def test_result_is_aware_utc(self):
        dt = _parse_time("2026-05-20 10:00:00")
        assert dt.utcoffset() == timezone.utc.utcoffset(None)


class TestParseCoords:
    def test_dict_lat_lon(self):
        coords = _parse_coords([{"lat": 51.0, "lon": -2.0}, {"lat": 52.0, "lon": 0.0}])
        assert coords == [(-2.0, 51.0), (0.0, 52.0)]

    def test_pair_assumed_lon_lat(self):
        coords = _parse_coords([[-2.0, 51.0]])
        assert coords == [(-2.0, 51.0)]

    def test_skips_malformed(self):
        coords = _parse_coords([{"lat": 51.0}, {"lat": 52.0, "lon": 0.0}])
        assert coords == [(0.0, 52.0)]

    def test_empty(self):
        assert _parse_coords(None) == []
        assert _parse_coords([]) == []


class TestFromAwc:
    def test_core_fields(self):
        s = SigmetReport.from_awc(sample_awc_entry())
        assert s.fir_id == "EGTT"
        assert s.fir_name == "LONDON"
        assert s.hazard == "TURB"
        assert s.qualifier == "SEV"
        assert s.base_ft == 10000
        assert s.top_ft == 24000
        assert s.direction == "NE"
        assert s.speed_kt == 15
        assert s.source == "avwx"
        assert s.raw_text.startswith("EGTT SIGMET")

    def test_times_are_aware(self):
        s = SigmetReport.from_awc(sample_awc_entry())
        assert s.valid_from == datetime(2026, 5, 20, 10, 0, tzinfo=timezone.utc)
        assert s.valid_to == datetime(2026, 5, 20, 14, 0, tzinfo=timezone.utc)

    def test_coords_lon_lat_order(self):
        s = SigmetReport.from_awc(sample_awc_entry())
        assert s.coords[0] == (-2.0, 51.0)
        assert len(s.coords) == 5

    def test_hazard_uppercased(self):
        s = SigmetReport.from_awc(sample_awc_entry(hazard="ice"))
        assert s.hazard == "ICE"

    def test_stationary_direction_normalised_to_none(self):
        # AWC sends "-" for a stationary/unknown system; the docstring promises None.
        assert SigmetReport.from_awc(sample_awc_entry(dir="-")).direction is None
        assert SigmetReport.from_awc(sample_awc_entry(dir="")).direction is None

    def test_missing_fields_tolerated(self):
        s = SigmetReport.from_awc({"firId": "LFFF"})
        assert s.fir_id == "LFFF"
        assert s.base_ft is None
        assert s.coords == []
        assert s.valid_from is None

    def test_flight_level_base_top(self):
        s = SigmetReport.from_awc(sample_awc_entry(base="FL100", top="FL340"))
        assert s.base_ft == 10000
        assert s.top_ft == 34000

    def test_epoch_times(self):
        s = SigmetReport.from_awc(sample_awc_entry(
            validTimeFrom=1747735200, validTimeTo=1747749600,
        ))
        assert s.valid_from.tzinfo is not None
        assert s.valid_to > s.valid_from


class TestGeometry:
    def test_polygons_shape(self):
        s = SigmetReport.from_awc(sample_awc_entry())
        polys = s.polygons
        assert len(polys) == 1          # one polygon
        assert len(polys[0]) == 1       # one ring
        assert polys[0][0][0] == (-2.0, 51.0)

    def test_polygons_empty_when_too_few_points(self):
        s = SigmetReport.from_awc(sample_awc_entry(coords=[{"lat": 1.0, "lon": 1.0}]))
        assert s.polygons == []

    def test_bbox(self):
        s = SigmetReport.from_awc(sample_awc_entry())
        assert s.bbox == (-2.0, 51.0, 0.0, 52.0)

    def test_contains_point_inside(self):
        s = SigmetReport.from_awc(sample_awc_entry())
        assert s.contains_point(-1.0, 51.5) is True

    def test_contains_point_outside(self):
        s = SigmetReport.from_awc(sample_awc_entry())
        assert s.contains_point(5.0, 51.5) is False


class TestAltitudeOverlap:
    def test_band_within_layer(self):
        s = SigmetReport(base_ft=10000, top_ft=24000)
        assert s.overlaps_altitude(12000, 18000) is True

    def test_band_below_layer(self):
        s = SigmetReport(base_ft=10000, top_ft=24000)
        assert s.overlaps_altitude(0, 5000) is False

    def test_band_above_layer(self):
        s = SigmetReport(base_ft=10000, top_ft=24000)
        assert s.overlaps_altitude(30000, 40000) is False

    def test_partial_overlap(self):
        s = SigmetReport(base_ft=10000, top_ft=24000)
        assert s.overlaps_altitude(20000, 35000) is True

    def test_unknown_layer_always_overlaps(self):
        s = SigmetReport(base_ft=None, top_ft=None)
        assert s.overlaps_altitude(0, 5000) is True

    def test_open_band_always_overlaps(self):
        s = SigmetReport(base_ft=30000, top_ft=40000)
        assert s.overlaps_altitude(None, None) is True


class TestValidity:
    def test_within_window(self):
        s = SigmetReport(
            valid_from=datetime(2026, 5, 20, 10, tzinfo=timezone.utc),
            valid_to=datetime(2026, 5, 20, 14, tzinfo=timezone.utc),
        )
        assert s.is_valid_at(datetime(2026, 5, 20, 12, tzinfo=timezone.utc)) is True

    def test_before_window(self):
        s = SigmetReport(
            valid_from=datetime(2026, 5, 20, 10, tzinfo=timezone.utc),
            valid_to=datetime(2026, 5, 20, 14, tzinfo=timezone.utc),
        )
        assert s.is_valid_at(datetime(2026, 5, 20, 9, tzinfo=timezone.utc)) is False


class TestOverlapsTime:
    def _sigmet(self):
        return SigmetReport(
            valid_from=datetime(2026, 5, 20, 10, tzinfo=timezone.utc),
            valid_to=datetime(2026, 5, 20, 14, tzinfo=timezone.utc),
        )

    def _dt(self, hour):
        return datetime(2026, 5, 20, hour, tzinfo=timezone.utc)

    def test_window_overlapping_start(self):
        assert self._sigmet().overlaps_time(self._dt(8), self._dt(11)) is True

    def test_window_fully_inside(self):
        assert self._sigmet().overlaps_time(self._dt(11), self._dt(13)) is True

    def test_window_entirely_before(self):
        assert self._sigmet().overlaps_time(self._dt(6), self._dt(9)) is False

    def test_window_entirely_after(self):
        assert self._sigmet().overlaps_time(self._dt(15), self._dt(18)) is False

    def test_open_query_always_overlaps(self):
        assert self._sigmet().overlaps_time(None, None) is True

    def test_only_lower_bound(self):
        # period starts at 13:00 with no end -> overlaps a SIGMET valid until 14:00
        assert self._sigmet().overlaps_time(self._dt(13), None) is True
        assert self._sigmet().overlaps_time(self._dt(15), None) is False

    def test_sigmet_with_no_window_always_overlaps(self):
        assert SigmetReport().overlaps_time(self._dt(10), self._dt(11)) is True

    def test_naive_query_assumed_utc(self):
        assert self._sigmet().overlaps_time(datetime(2026, 5, 20, 11), datetime(2026, 5, 20, 13)) is True


class TestRoundTrip:
    def test_to_from_dict(self):
        s = SigmetReport.from_awc(sample_awc_entry())
        restored = SigmetReport.from_dict(s.to_dict())
        assert restored.fir_id == s.fir_id
        assert restored.hazard == s.hazard
        assert restored.base_ft == s.base_ft
        assert restored.top_ft == s.top_ft
        assert restored.valid_from == s.valid_from
        assert restored.valid_to == s.valid_to
        assert restored.coords == s.coords
        assert restored.speed_kt == s.speed_kt

    def test_to_dict_json_serialisable(self):
        import json
        s = SigmetReport.from_awc(sample_awc_entry())
        json.dumps(s.to_dict())  # should not raise
