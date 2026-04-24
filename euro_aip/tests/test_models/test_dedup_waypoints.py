"""Tests for EuroAipModel.dedup_waypoints()."""

import itertools

from euro_aip.models.euro_aip_model import EuroAipModel
from euro_aip.models.waypoint import Waypoint

# Unique source_id per call so add_waypoint doesn't merge distinct test waypoints
# that happen to share (name, source). Real sources use e.g. "ourairports:DE" —
# we just need any distinct token per call.
_sid_counter = itertools.count()


def _make_waypoint(name, lat, lon, source, point_type="5LNC", source_id=None):
    return Waypoint(
        name=name,
        latitude_deg=lat,
        longitude_deg=lon,
        point_type=point_type,
        source=source,
        source_id=source_id or f"{source}:t{next(_sid_counter)}",
    )


class TestDedupBasics:
    def test_empty_model_is_noop(self):
        model = EuroAipModel()
        result = model.dedup_waypoints()
        assert result == {"kept": 0, "dropped": 0}

    def test_single_candidate_unaffected(self):
        model = EuroAipModel()
        model.add_waypoint(_make_waypoint("ABCDE", 45.0, 2.0, "opennav"))
        result = model.dedup_waypoints()
        assert result == {"kept": 1, "dropped": 0}
        assert len(model._waypoints["ABCDE"]) == 1

    def test_identical_coords_collapse_to_one(self):
        """Two candidates at the same coords from different sources — one survives."""
        model = EuroAipModel()
        model.add_waypoint(_make_waypoint("REM", 49.31, 3.16, "eurocontrol_fra"))
        model.add_waypoint(_make_waypoint("REM", 49.31, 3.16, "opennav"))
        model.add_waypoint(_make_waypoint("REM", 49.31, 3.16, "ourairports"))

        result = model.dedup_waypoints()
        assert result == {"kept": 1, "dropped": 2}
        survivors = model._waypoints["REM"]
        assert len(survivors) == 1
        assert survivors[0].source == "eurocontrol_fra"  # highest priority


class TestSourcePriority:
    def test_default_priority_order(self):
        """FRA > OpenNav > OurAirports > FAA by default."""
        for winner_source, losers in [
            ("eurocontrol_fra", ["opennav", "ourairports", "faa_nasr"]),
            ("opennav", ["ourairports", "faa_nasr"]),
            ("ourairports", ["faa_nasr"]),
        ]:
            model = EuroAipModel()
            model.add_waypoint(_make_waypoint("X", 45.0, 2.0, winner_source))
            for loser in losers:
                model.add_waypoint(_make_waypoint("X", 45.0, 2.0, loser))

            model.dedup_waypoints()
            survivors = model._waypoints["X"]
            assert len(survivors) == 1
            assert survivors[0].source == winner_source, (
                f"{winner_source} should win over {losers}"
            )

    def test_custom_priority_order(self):
        """User-supplied priority list overrides default."""
        model = EuroAipModel()
        model.add_waypoint(_make_waypoint("X", 45.0, 2.0, "eurocontrol_fra"))
        model.add_waypoint(_make_waypoint("X", 45.0, 2.0, "opennav"))

        # Invert the default: opennav should win
        model.dedup_waypoints(source_priority=["opennav", "eurocontrol_fra"])
        survivors = model._waypoints["X"]
        assert len(survivors) == 1
        assert survivors[0].source == "opennav"

    def test_unlisted_source_ranks_lowest(self):
        """Sources not in the priority list rank below all listed ones."""
        model = EuroAipModel()
        model.add_waypoint(_make_waypoint("X", 45.0, 2.0, "mystery_source"))
        model.add_waypoint(_make_waypoint("X", 45.0, 2.0, "ourairports"))

        model.dedup_waypoints()
        survivors = model._waypoints["X"]
        assert len(survivors) == 1
        assert survivors[0].source == "ourairports"


class TestGeographicCollisions:
    def test_faraway_candidates_preserved(self):
        """Same name at genuinely different locations (> tolerance) is kept as separate candidates."""
        model = EuroAipModel()
        # 'MA' is an NDB in both Germany and USA — real-world case
        model.add_waypoint(_make_waypoint(
            "MA", 51.4, 12.34, "ourairports", "NDB", "ourairports:DE"
        ))
        model.add_waypoint(_make_waypoint(
            "MA", 31.99, -102.32, "ourairports", "NDB", "ourairports:US"
        ))

        result = model.dedup_waypoints()
        assert result["dropped"] == 0
        assert len(model._waypoints["MA"]) == 2

    def test_tolerance_threshold_respected(self):
        """Candidates just outside tolerance stay separate; just inside collapse."""
        model = EuroAipModel()
        # Two candidates ~1.5 nm apart (roughly 1 arc-min of latitude = 1 nm)
        model.add_waypoint(_make_waypoint("X", 45.00, 2.0, "opennav"))
        model.add_waypoint(_make_waypoint("X", 45.025, 2.0, "ourairports"))  # ~1.5 nm north

        # With tolerance 0.5 nm → kept separate
        result = model.dedup_waypoints(tolerance_nm=0.5)
        assert result["dropped"] == 0
        assert len(model._waypoints["X"]) == 2

    def test_tolerance_wide_enough_collapses(self):
        model = EuroAipModel()
        model.add_waypoint(_make_waypoint("X", 45.00, 2.0, "opennav"))
        model.add_waypoint(_make_waypoint("X", 45.025, 2.0, "ourairports"))  # ~1.5 nm north

        # With tolerance 5 nm → collapsed
        result = model.dedup_waypoints(tolerance_nm=5.0)
        assert result["dropped"] == 1
        assert len(model._waypoints["X"]) == 1
        assert model._waypoints["X"][0].source == "opennav"  # higher priority


class TestMixedTypes:
    def test_same_coords_different_types_merge_by_priority(self):
        """When candidates share coords but disagree on type, priority wins — the
        'correct' classification comes from the more authoritative source."""
        model = EuroAipModel()
        # FRA says VORDME, OurAirports says NDB at same point — FRA wins.
        model.add_waypoint(_make_waypoint(
            "ABB", 50.12, 1.85, "eurocontrol_fra", "VORDME"
        ))
        model.add_waypoint(_make_waypoint(
            "ABB", 50.12, 1.85, "ourairports", "NDB"
        ))

        model.dedup_waypoints()
        survivors = model._waypoints["ABB"]
        assert len(survivors) == 1
        assert survivors[0].point_type == "VORDME"

    def test_collocated_different_types_far_enough_preserved(self):
        """Physically distinct installations sharing a name at >tolerance stay separate."""
        model = EuroAipModel()
        model.add_waypoint(_make_waypoint(
            "X", 45.00, 2.0, "opennav", "VORDME"
        ))
        model.add_waypoint(_make_waypoint(
            "X", 45.05, 2.0, "opennav", "VORTAC"  # ~3 nm away
        ))

        result = model.dedup_waypoints(tolerance_nm=0.5)
        assert result["dropped"] == 0
        assert {w.point_type for w in model._waypoints["X"]} == {"VORDME", "VORTAC"}


class TestMultipleClusters:
    def test_name_with_both_redundant_and_genuine_collisions(self):
        """A name might have some redundant candidates AND real geographic collisions.
        Each cluster is resolved independently."""
        model = EuroAipModel()
        # US cluster: two sources at same US location
        model.add_waypoint(_make_waypoint("MA", 31.99, -102.32, "ourairports", "NDB"))
        model.add_waypoint(_make_waypoint("MA", 31.99, -102.32, "opennav", "NDB"))
        # DE location (separate)
        model.add_waypoint(_make_waypoint("MA", 51.4, 12.34, "ourairports", "NDB"))

        result = model.dedup_waypoints()
        assert result["kept"] == 2
        assert result["dropped"] == 1
        survivors = model._waypoints["MA"]
        assert len(survivors) == 2
        # US cluster: opennav wins (higher priority than ourairports)
        us_survivor = next(w for w in survivors if w.longitude_deg < 0)
        assert us_survivor.source == "opennav"
        # DE cluster: only ourairports candidate was there
        de_survivor = next(w for w in survivors if w.longitude_deg > 0)
        assert de_survivor.source == "ourairports"
