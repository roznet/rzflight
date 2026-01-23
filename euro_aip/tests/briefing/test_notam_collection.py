"""Tests for NotamCollection."""

import pytest
from datetime import datetime, timedelta

from euro_aip.briefing.collections.notam_collection import NotamCollection
from euro_aip.briefing.models.notam import Notam, NotamCategory
from euro_aip.briefing.models.route import Route, RoutePoint


def create_notam(
    id: str = "A0001/24",
    location: str = "LFPG",
    q_code: str = None,
    category: NotamCategory = None,
    effective_from: datetime = None,
    effective_to: datetime = None,
    is_permanent: bool = False,
    coordinates: tuple = None,
    lower_limit: int = None,
    upper_limit: int = None,
    message: str = "TEST NOTAM",
    fir: str = None,
    traffic_type: str = None,
    purpose: str = None,
    scope: str = None,
    custom_categories: set = None,
    custom_tags: set = None,
    primary_category: str = None,
) -> Notam:
    """Helper to create test NOTAMs."""
    return Notam(
        id=id,
        location=location,
        q_code=q_code,
        category=category,
        effective_from=effective_from,
        effective_to=effective_to,
        is_permanent=is_permanent,
        coordinates=coordinates,
        lower_limit=lower_limit,
        upper_limit=upper_limit,
        message=message,
        raw_text=message,
        fir=fir,
        traffic_type=traffic_type,
        purpose=purpose,
        scope=scope,
        custom_categories=custom_categories or set(),
        custom_tags=custom_tags or set(),
        primary_category=primary_category,
    )


class TestNotamCollectionLocationFilters:
    """Tests for location-based filters."""

    def test_for_airport(self):
        """Test filtering by single airport."""
        notams = [
            create_notam(id="A0001/24", location="LFPG"),
            create_notam(id="A0002/24", location="EGLL"),
            create_notam(id="A0003/24", location="LFPG"),
        ]

        collection = NotamCollection(notams)
        result = collection.for_airport("LFPG").all()

        assert len(result) == 2
        assert all(n.location == "LFPG" for n in result)

    def test_for_airport_case_insensitive(self):
        """Test that airport filter is case insensitive."""
        notams = [create_notam(location="LFPG")]

        collection = NotamCollection(notams)
        result = collection.for_airport("lfpg").all()

        assert len(result) == 1

    def test_for_airports(self):
        """Test filtering by multiple airports."""
        notams = [
            create_notam(id="A0001/24", location="LFPG"),
            create_notam(id="A0002/24", location="EGLL"),
            create_notam(id="A0003/24", location="EHAM"),
        ]

        collection = NotamCollection(notams)
        result = collection.for_airports(["LFPG", "EGLL"]).all()

        assert len(result) == 2
        assert {n.location for n in result} == {"LFPG", "EGLL"}

    def test_for_fir(self):
        """Test filtering by FIR."""
        notams = [
            create_notam(id="A0001/24", fir="LFFF"),
            create_notam(id="A0002/24", fir="EGTT"),
            create_notam(id="A0003/24", fir="LFFF"),
        ]

        collection = NotamCollection(notams)
        result = collection.for_fir("LFFF").all()

        assert len(result) == 2

    def test_for_route(self):
        """Test filtering by route airports."""
        notams = [
            create_notam(id="A0001/24", location="LFPG"),
            create_notam(id="A0002/24", location="EGLL"),
            create_notam(id="A0003/24", location="EHAM"),
            create_notam(id="A0004/24", location="LFOB"),
        ]

        route = Route(
            departure="LFPG",
            destination="EGLL",
            alternates=["LFOB"]
        )

        collection = NotamCollection(notams)
        result = collection.for_route(route).all()

        assert len(result) == 3
        assert {n.location for n in result} == {"LFPG", "EGLL", "LFOB"}


class TestNotamCollectionTimeFilters:
    """Tests for time-based filters."""

    def test_active_at(self):
        """Test filtering by active at specific time."""
        now = datetime.utcnow()
        notams = [
            create_notam(
                id="A0001/24",
                effective_from=now - timedelta(hours=1),
                effective_to=now + timedelta(hours=1),
            ),
            create_notam(
                id="A0002/24",
                effective_from=now + timedelta(hours=2),
                effective_to=now + timedelta(hours=4),
            ),
        ]

        collection = NotamCollection(notams)
        result = collection.active_at(now).all()

        assert len(result) == 1
        assert result[0].id == "A0001/24"

    def test_active_now(self):
        """Test filtering for currently active NOTAMs."""
        now = datetime.utcnow()
        notams = [
            create_notam(
                id="A0001/24",
                effective_from=now - timedelta(hours=1),
                effective_to=now + timedelta(hours=1),
            ),
            create_notam(
                id="A0002/24",
                effective_from=now - timedelta(hours=5),
                effective_to=now - timedelta(hours=1),
            ),
        ]

        collection = NotamCollection(notams)
        result = collection.active_now().all()

        assert len(result) == 1
        assert result[0].id == "A0001/24"

    def test_active_during_window(self):
        """Test filtering for NOTAMs active during time window."""
        now = datetime.utcnow()
        notams = [
            # Active throughout window
            create_notam(
                id="A0001/24",
                effective_from=now - timedelta(hours=2),
                effective_to=now + timedelta(hours=4),
            ),
            # Starts during window
            create_notam(
                id="A0002/24",
                effective_from=now + timedelta(hours=1),
                effective_to=now + timedelta(hours=5),
            ),
            # Ends during window
            create_notam(
                id="A0003/24",
                effective_from=now - timedelta(hours=3),
                effective_to=now + timedelta(hours=1),
            ),
            # Completely before window
            create_notam(
                id="A0004/24",
                effective_from=now - timedelta(hours=10),
                effective_to=now - timedelta(hours=5),
            ),
        ]

        collection = NotamCollection(notams)
        start = now
        end = now + timedelta(hours=2)
        result = collection.active_during(start, end).all()

        assert len(result) == 3
        assert {n.id for n in result} == {"A0001/24", "A0002/24", "A0003/24"}

    def test_permanent_notams(self):
        """Test filtering permanent NOTAMs."""
        notams = [
            create_notam(id="A0001/24", is_permanent=True),
            create_notam(id="A0002/24", is_permanent=False),
        ]

        collection = NotamCollection(notams)
        result = collection.permanent().all()

        assert len(result) == 1
        assert result[0].id == "A0001/24"

    def test_temporary_notams(self):
        """Test filtering temporary NOTAMs."""
        notams = [
            create_notam(id="A0001/24", is_permanent=True),
            create_notam(id="A0002/24", is_permanent=False),
        ]

        collection = NotamCollection(notams)
        result = collection.temporary().all()

        assert len(result) == 1
        assert result[0].id == "A0002/24"


class TestNotamCollectionCategoryFilters:
    """Tests for category-based filters."""

    def test_by_category(self):
        """Test filtering by NOTAM category."""
        notams = [
            create_notam(id="A0001/24", category=NotamCategory.RUNWAY),
            create_notam(id="A0002/24", category=NotamCategory.NAVIGATION),
            create_notam(id="A0003/24", category=NotamCategory.RUNWAY),
        ]

        collection = NotamCollection(notams)
        result = collection.by_category(NotamCategory.RUNWAY).all()

        assert len(result) == 2

    def test_runway_related(self):
        """Test filtering runway-related NOTAMs."""
        notams = [
            create_notam(id="A0001/24", category=NotamCategory.RUNWAY),
            create_notam(id="A0002/24", category=NotamCategory.LIGHTING),
            create_notam(id="A0003/24", q_code="QMRLC"),  # Runway closed
            create_notam(id="A0004/24", category=NotamCategory.NAVIGATION),
        ]

        collection = NotamCollection(notams)
        result = collection.runway_related().all()

        # Should include RUNWAY category, LIGHTING, and QMRLC
        assert len(result) >= 2

    def test_navigation_related(self):
        """Test filtering navigation-related NOTAMs."""
        notams = [
            create_notam(id="A0001/24", category=NotamCategory.NAVIGATION),
            create_notam(id="A0002/24", q_code="QNVAS"),  # VOR unserviceable
            create_notam(id="A0003/24", category=NotamCategory.RUNWAY),
        ]

        collection = NotamCollection(notams)
        result = collection.navigation_related().all()

        assert len(result) == 2

    def test_airspace_related(self):
        """Test filtering airspace-related NOTAMs."""
        notams = [
            create_notam(id="A0001/24", category=NotamCategory.AIRSPACE),
            create_notam(id="A0002/24", q_code="QARAU"),  # Restricted area active
            create_notam(id="A0003/24", category=NotamCategory.RUNWAY),
        ]

        collection = NotamCollection(notams)
        result = collection.airspace_related().all()

        assert len(result) == 2


class TestNotamCollectionSpatialFilters:
    """Tests for spatial filters."""

    def test_within_radius(self):
        """Test filtering by radius from point."""
        notams = [
            create_notam(id="A0001/24", coordinates=(49.0, 2.5)),  # Near Paris CDG
            create_notam(id="A0002/24", coordinates=(51.5, -0.5)),  # Near London
            create_notam(id="A0003/24", coordinates=(49.1, 2.6)),  # Also near Paris
        ]

        collection = NotamCollection(notams)
        # Filter within 50nm of Paris CDG (approx 49.0, 2.5)
        result = collection.within_radius(49.0, 2.5, 50).all()

        assert len(result) == 2
        assert {n.id for n in result} == {"A0001/24", "A0003/24"}

    def test_along_route(self):
        """Test filtering along route corridor."""
        # Create a simple route Paris -> London
        route = Route(
            departure="LFPG",
            destination="EGLL",
            departure_coords=(49.0, 2.5),
            destination_coords=(51.5, -0.5),
            waypoint_coords=[
                RoutePoint(name="BIBAX", latitude=50.0, longitude=1.0, point_type="waypoint"),
            ]
        )

        notams = [
            create_notam(id="A0001/24", coordinates=(50.0, 1.0)),  # On route
            create_notam(id="A0002/24", coordinates=(45.0, 5.0)),  # Far south
            create_notam(id="A0003/24", coordinates=(50.5, 0.5)),  # Near route
        ]

        collection = NotamCollection(notams)
        result = collection.along_route(route, corridor_nm=50).all()

        # Should include NOTAMs near the route
        assert len(result) >= 1


class TestNotamCollectionAltitudeFilters:
    """Tests for altitude filters."""

    def test_below_altitude(self):
        """Test filtering NOTAMs below altitude."""
        notams = [
            create_notam(id="A0001/24", upper_limit=5000),
            create_notam(id="A0002/24", upper_limit=15000),
            create_notam(id="A0003/24", upper_limit=3000),
        ]

        collection = NotamCollection(notams)
        result = collection.below_altitude(10000).all()

        assert len(result) == 2
        assert {n.id for n in result} == {"A0001/24", "A0003/24"}

    def test_above_altitude(self):
        """Test filtering NOTAMs above altitude."""
        notams = [
            create_notam(id="A0001/24", lower_limit=5000),
            create_notam(id="A0002/24", lower_limit=15000),
            create_notam(id="A0003/24", lower_limit=25000),
        ]

        collection = NotamCollection(notams)
        result = collection.above_altitude(10000).all()

        assert len(result) == 2
        assert {n.id for n in result} == {"A0002/24", "A0003/24"}

    def test_in_altitude_range(self):
        """Test filtering NOTAMs in altitude range."""
        notams = [
            create_notam(id="A0001/24", lower_limit=0, upper_limit=5000),
            create_notam(id="A0002/24", lower_limit=10000, upper_limit=20000),
            create_notam(id="A0003/24", lower_limit=30000, upper_limit=40000),
        ]

        collection = NotamCollection(notams)
        # Flight at FL150 (15000ft)
        result = collection.in_altitude_range(13000, 17000).all()

        assert len(result) == 1
        assert result[0].id == "A0002/24"


class TestNotamCollectionQCodeFilters:
    """Tests for Q-code filters."""

    def test_by_q_code(self):
        """Test filtering by exact Q-code."""
        notams = [
            create_notam(id="A0001/24", q_code="QMRLC"),
            create_notam(id="A0002/24", q_code="QMXLC"),
            create_notam(id="A0003/24", q_code="QMRLC"),
        ]

        collection = NotamCollection(notams)
        result = collection.by_q_code("QMRLC").all()

        assert len(result) == 2

    def test_by_q_code_prefix(self):
        """Test filtering by Q-code prefix."""
        notams = [
            create_notam(id="A0001/24", q_code="QMRLC"),
            create_notam(id="A0002/24", q_code="QMXLC"),
            create_notam(id="A0003/24", q_code="QNVAS"),
        ]

        collection = NotamCollection(notams)
        # QM = Movement area
        result = collection.by_q_code_prefix("QM").all()

        assert len(result) == 2
        assert {n.id for n in result} == {"A0001/24", "A0002/24"}

    def test_by_traffic_type(self):
        """Test filtering by traffic type."""
        notams = [
            create_notam(id="A0001/24", traffic_type="IV"),
            create_notam(id="A0002/24", traffic_type="I"),
            create_notam(id="A0003/24", traffic_type="V"),
        ]

        collection = NotamCollection(notams)
        result = collection.by_traffic_type("I").all()

        # Should match IV and I
        assert len(result) == 2


class TestNotamCollectionContentFilters:
    """Tests for content-based filters."""

    def test_containing(self):
        """Test filtering by text content."""
        notams = [
            create_notam(id="A0001/24", message="RWY 09L/27R CLSD"),
            create_notam(id="A0002/24", message="TWY A CLSD"),
            create_notam(id="A0003/24", message="VOR PGS U/S"),
        ]

        collection = NotamCollection(notams)
        result = collection.containing("CLSD").all()

        assert len(result) == 2

    def test_matching_regex(self):
        """Test filtering by regex pattern."""
        notams = [
            create_notam(id="A0001/24", message="RWY 09L/27R CLSD"),
            create_notam(id="A0002/24", message="RWY 18R/36L LIMITED"),
            create_notam(id="A0003/24", message="TWY A CLSD"),
        ]

        collection = NotamCollection(notams)
        result = collection.matching(r"RWY\s+\d+[LRC]").all()

        assert len(result) == 2


class TestNotamCollectionCustomCategoryFilters:
    """Tests for custom category filters."""

    def test_by_custom_category(self):
        """Test filtering by custom category."""
        notams = [
            create_notam(id="A0001/24", custom_categories={"runway", "closed"}),
            create_notam(id="A0002/24", custom_categories={"navaid"}),
            create_notam(id="A0003/24", custom_categories={"runway"}),
        ]

        collection = NotamCollection(notams)
        result = collection.by_custom_category("runway").all()

        assert len(result) == 2

    def test_by_custom_tag(self):
        """Test filtering by custom tag."""
        notams = [
            create_notam(id="A0001/24", custom_tags={"crane", "obstacle"}),
            create_notam(id="A0002/24", custom_tags={"ils", "unserviceable"}),
            create_notam(id="A0003/24", custom_tags={"crane"}),
        ]

        collection = NotamCollection(notams)
        result = collection.by_custom_tag("crane").all()

        assert len(result) == 2


class TestNotamCollectionSetOperations:
    """Tests for set operations."""

    def test_union(self):
        """Test union of collections."""
        notams = [
            create_notam(id="A0001/24", location="LFPG"),
            create_notam(id="A0002/24", location="EGLL"),
            create_notam(id="A0003/24", location="EHAM"),
        ]

        collection = NotamCollection(notams)
        paris = collection.for_airport("LFPG")
        london = collection.for_airport("EGLL")

        result = (paris | london).all()

        assert len(result) == 2
        assert {n.id for n in result} == {"A0001/24", "A0002/24"}

    def test_intersection(self):
        """Test intersection of collections."""
        now = datetime.utcnow()
        notams = [
            create_notam(
                id="A0001/24",
                location="LFPG",
                category=NotamCategory.RUNWAY,
                effective_from=now - timedelta(hours=1),
                effective_to=now + timedelta(hours=1),
            ),
            create_notam(
                id="A0002/24",
                location="LFPG",
                category=NotamCategory.NAVIGATION,
                effective_from=now - timedelta(hours=1),
                effective_to=now + timedelta(hours=1),
            ),
            create_notam(
                id="A0003/24",
                location="LFPG",
                category=NotamCategory.RUNWAY,
                effective_from=now + timedelta(hours=5),
                effective_to=now + timedelta(hours=10),
            ),
        ]

        collection = NotamCollection(notams)
        runway = collection.by_category(NotamCategory.RUNWAY)
        active = collection.active_now()

        result = (runway & active).all()

        assert len(result) == 1
        assert result[0].id == "A0001/24"

    def test_difference(self):
        """Test difference of collections."""
        notams = [
            create_notam(id="A0001/24", location="LFPG"),
            create_notam(id="A0002/24", location="EGLL"),
            create_notam(id="A0003/24", location="EHAM"),
        ]

        collection = NotamCollection(notams)
        all_notams = NotamCollection(notams)
        london = collection.for_airport("EGLL")

        result = (all_notams - london).all()

        assert len(result) == 2
        assert {n.id for n in result} == {"A0001/24", "A0003/24"}


class TestNotamCollectionGrouping:
    """Tests for grouping methods."""

    def test_group_by_airport(self):
        """Test grouping by airport."""
        notams = [
            create_notam(id="A0001/24", location="LFPG"),
            create_notam(id="A0002/24", location="EGLL"),
            create_notam(id="A0003/24", location="LFPG"),
        ]

        collection = NotamCollection(notams)
        groups = collection.group_by_airport()

        assert len(groups) == 2
        assert len(groups["LFPG"].all()) == 2
        assert len(groups["EGLL"].all()) == 1

    def test_group_by_category(self):
        """Test grouping by category."""
        notams = [
            create_notam(id="A0001/24", category=NotamCategory.RUNWAY),
            create_notam(id="A0002/24", category=NotamCategory.NAVIGATION),
            create_notam(id="A0003/24", category=NotamCategory.RUNWAY),
        ]

        collection = NotamCollection(notams)
        groups = collection.group_by_category()

        assert len(groups) == 2
        assert len(groups[NotamCategory.RUNWAY].all()) == 2
        assert len(groups[NotamCategory.NAVIGATION].all()) == 1


class TestNotamCollectionChaining:
    """Tests for filter chaining."""

    def test_chain_multiple_filters(self):
        """Test chaining multiple filters."""
        now = datetime.utcnow()
        notams = [
            create_notam(
                id="A0001/24",
                location="LFPG",
                category=NotamCategory.RUNWAY,
                effective_from=now - timedelta(hours=1),
                effective_to=now + timedelta(hours=1),
            ),
            create_notam(
                id="A0002/24",
                location="LFPG",
                category=NotamCategory.NAVIGATION,
                effective_from=now - timedelta(hours=1),
                effective_to=now + timedelta(hours=1),
            ),
            create_notam(
                id="A0003/24",
                location="EGLL",
                category=NotamCategory.RUNWAY,
                effective_from=now - timedelta(hours=1),
                effective_to=now + timedelta(hours=1),
            ),
        ]

        collection = NotamCollection(notams)
        result = (
            collection
            .for_airport("LFPG")
            .active_now()
            .by_category(NotamCategory.RUNWAY)
            .all()
        )

        assert len(result) == 1
        assert result[0].id == "A0001/24"
