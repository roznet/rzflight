"""Tests for solar position and twilight helpers."""

from datetime import date, datetime, timezone

from euro_aip.utils.solar import (
    CIVIL_TWILIGHT_DEG,
    solar_azimuth,
    solar_elevation,
    solar_position,
    sun_events,
)

# London, 2024-06-21 (summer solstice). Published local times are BST (UTC+1):
# sunrise 04:43 BST = 03:43 UTC, sunset 21:21 BST = 20:21 UTC. London sits at
# ~0 deg longitude so solar noon is ~12:02 UTC regardless of the civil zone.
LONDON_LAT = 51.5074
LONDON_LON = -0.1278


class TestSunEvents:
    def test_known_sunrise_within_two_minutes(self):
        events = sun_events(LONDON_LAT, LONDON_LON, date(2024, 6, 21))
        sunrise = events["sunrise"]
        assert sunrise is not None
        # Published London sunrise on the solstice: 04:43 BST = 03:43 UTC.
        expected = datetime(2024, 6, 21, 3, 43, tzinfo=timezone.utc)
        delta_min = abs((sunrise - expected).total_seconds()) / 60.0
        assert delta_min <= 2.0, f"sunrise off by {delta_min:.1f} min"

    def test_known_sunset_within_two_minutes(self):
        events = sun_events(LONDON_LAT, LONDON_LON, date(2024, 6, 21))
        sunset = events["sunset"]
        assert sunset is not None
        expected = datetime(2024, 6, 21, 20, 21, tzinfo=timezone.utc)
        delta_min = abs((sunset - expected).total_seconds()) / 60.0
        assert delta_min <= 2.0, f"sunset off by {delta_min:.1f} min"

    def test_civil_twilight_keys_and_ordering(self):
        events = sun_events(
            LONDON_LAT, LONDON_LON, date(2024, 6, 21), depression=CIVIL_TWILIGHT_DEG
        )
        assert set(events.keys()) == {"dawn", "dusk"}
        # Civil dawn is before sunrise; civil dusk is after sunset.
        plain = sun_events(LONDON_LAT, LONDON_LON, date(2024, 6, 21))
        assert events["dawn"] < plain["sunrise"]
        assert events["dusk"] > plain["sunset"]

    def test_polar_night_returns_none(self):
        # Longyearbyen (78N) in deep winter: sun never rises.
        events = sun_events(78.22, 15.65, date(2024, 12, 21))
        assert events["sunrise"] is None
        assert events["sunset"] is None

    def test_returns_aware_utc(self):
        events = sun_events(LONDON_LAT, LONDON_LON, date(2024, 6, 21))
        assert events["sunrise"].tzinfo is not None


class TestSolarElevation:
    def test_negative_at_local_midnight(self):
        # London solar midnight ~00:00 UTC+1 -> 23:00 UTC the night before.
        midnight = datetime(2024, 6, 21, 0, 0, tzinfo=timezone.utc)
        assert solar_elevation(LONDON_LAT, LONDON_LON, midnight) < 0

    def test_positive_at_local_noon(self):
        # Solar noon ~12:02 UTC on the solstice (London ~0 deg longitude).
        noon = datetime(2024, 6, 21, 12, 2, tzinfo=timezone.utc)
        elev = solar_elevation(LONDON_LAT, LONDON_LON, noon)
        assert elev > 0
        # On the solstice at ~51.5N the sun gets to ~62 deg up.
        assert 55 < elev < 65

    def test_naive_datetime_treated_as_utc(self):
        aware = datetime(2024, 6, 21, 12, 2, tzinfo=timezone.utc)
        naive = datetime(2024, 6, 21, 12, 2)
        assert abs(
            solar_elevation(LONDON_LAT, LONDON_LON, aware)
            - solar_elevation(LONDON_LAT, LONDON_LON, naive)
        ) < 1e-6


class TestSolarAzimuth:
    def test_due_south_at_solar_noon_northern_hemisphere(self):
        noon = datetime(2024, 6, 21, 12, 2, tzinfo=timezone.utc)
        az = solar_azimuth(LONDON_LAT, LONDON_LON, noon)
        # At solar noon in the N hemisphere the sun is due south (~180 deg).
        assert abs(az - 180.0) < 3.0

    def test_in_range(self):
        when = datetime(2024, 6, 21, 8, 0, tzinfo=timezone.utc)
        az = solar_azimuth(LONDON_LAT, LONDON_LON, when)
        assert 0.0 <= az <= 360.0


class TestSolarPosition:
    def test_matches_individual_calls(self):
        when = datetime(2024, 6, 21, 9, 30, tzinfo=timezone.utc)
        elev, az = solar_position(LONDON_LAT, LONDON_LON, when)
        assert elev == solar_elevation(LONDON_LAT, LONDON_LON, when)
        assert az == solar_azimuth(LONDON_LAT, LONDON_LON, when)
