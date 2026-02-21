"""Queryable collection for weather report filtering."""

from datetime import datetime
from typing import List, Dict, Optional, Callable

from euro_aip.models.queryable_collection import QueryableCollection
from euro_aip.briefing.weather.models import (
    WeatherReport,
    WeatherType,
    FlightCategory,
)


class WeatherCollection(QueryableCollection[WeatherReport]):
    """
    Queryable collection for weather report filtering.

    Extends QueryableCollection with aviation weather-specific filters for:
    - Report type (METAR, SPECI, TAF)
    - Location (airport)
    - Flight category (VFR, MVFR, IFR, LIFR)
    - Time (latest, before, after, between, chronological)
    - Wind (crosswind limits)

    Supports fluent chaining, set operations, and iteration.

    Example:
        # Get latest METAR for an airport
        latest = collection.metars().for_airport("LFPG").latest()

        # Find IFR or worse conditions
        bad_wx = collection.metars().worse_than(FlightCategory.MVFR).all()

        # Check crosswind limits
        exceeds = collection.crosswind_exceeds(270, 20).all()
    """

    def __init__(self, items: List[WeatherReport]):
        super().__init__(items)

    def _new_collection(self, items: List[WeatherReport]) -> 'WeatherCollection':
        """Create new collection."""
        return WeatherCollection(items)

    def filter(self, predicate: Callable[[WeatherReport], bool]) -> 'WeatherCollection':
        """Filter items using a predicate function."""
        return self._new_collection([item for item in self._items if predicate(item)])

    # --- Type filters ---

    def metars(self) -> 'WeatherCollection':
        """Filter to METAR and SPECI reports only."""
        return self._new_collection([
            r for r in self._items
            if r.report_type in (WeatherType.METAR, WeatherType.SPECI)
        ])

    def tafs(self) -> 'WeatherCollection':
        """Filter to TAF reports only."""
        return self._new_collection([
            r for r in self._items
            if r.report_type == WeatherType.TAF
        ])

    # --- Location filters ---

    def for_airport(self, icao: str) -> 'WeatherCollection':
        """
        Filter reports for a specific airport.

        Args:
            icao: Airport ICAO code

        Returns:
            Collection with reports for the airport
        """
        icao_upper = icao.upper()
        return self._new_collection([
            r for r in self._items
            if r.icao.upper() == icao_upper
        ])

    def for_airports(self, icaos: List[str]) -> 'WeatherCollection':
        """
        Filter reports for any of the specified airports.

        Args:
            icaos: List of ICAO codes

        Returns:
            Collection with reports for any of the airports
        """
        icaos_upper = {i.upper() for i in icaos}
        return self._new_collection([
            r for r in self._items
            if r.icao.upper() in icaos_upper
        ])

    # --- Category filters ---

    def by_category(self, category: FlightCategory) -> 'WeatherCollection':
        """
        Filter by exact flight category.

        Args:
            category: FlightCategory to match
        """
        return self._new_collection([
            r for r in self._items
            if r.flight_category == category
        ])

    def worse_than(self, category: FlightCategory) -> 'WeatherCollection':
        """
        Filter reports with category strictly worse than given.

        Args:
            category: Threshold category (exclusive)
        """
        return self._new_collection([
            r for r in self._items
            if r.flight_category is not None and r.flight_category < category
        ])

    def at_or_worse_than(self, category: FlightCategory) -> 'WeatherCollection':
        """
        Filter reports with category at or worse than given.

        Args:
            category: Threshold category (inclusive)
        """
        return self._new_collection([
            r for r in self._items
            if r.flight_category is not None and r.flight_category <= category
        ])

    # --- Time filters ---

    def latest(self) -> Optional[WeatherReport]:
        """
        Get the most recent report by observation time.

        Returns:
            Most recent WeatherReport or None
        """
        with_time = [r for r in self._items if r.observation_time is not None]
        if not with_time:
            return self.last()
        return max(with_time, key=lambda r: r.observation_time)

    def before(self, dt: datetime) -> 'WeatherCollection':
        """Filter reports observed before a given time."""
        return self._new_collection([
            r for r in self._items
            if r.observation_time is not None and r.observation_time < dt
        ])

    def after(self, dt: datetime) -> 'WeatherCollection':
        """Filter reports observed after a given time."""
        return self._new_collection([
            r for r in self._items
            if r.observation_time is not None and r.observation_time > dt
        ])

    def between(self, start: datetime, end: datetime) -> 'WeatherCollection':
        """Filter reports observed within a time window."""
        return self._new_collection([
            r for r in self._items
            if r.observation_time is not None
            and start <= r.observation_time <= end
        ])

    def chronological(self) -> 'WeatherCollection':
        """Sort reports by observation time (oldest first)."""
        return self._new_collection(
            sorted(
                self._items,
                key=lambda r: r.observation_time or datetime.min,
            )
        )

    # --- Wind filters ---

    def crosswind_exceeds(
        self,
        runway_heading: int,
        limit_kt: float,
    ) -> 'WeatherCollection':
        """
        Filter reports where crosswind exceeds a limit for a runway heading.

        Args:
            runway_heading: Runway heading in degrees
            limit_kt: Crosswind limit in knots

        Returns:
            Collection with reports exceeding the crosswind limit
        """
        from euro_aip.briefing.weather.analysis import WeatherAnalyzer

        def exceeds(report: WeatherReport) -> bool:
            wc = WeatherAnalyzer.wind_components(report, runway_heading)
            if wc is None:
                return False
            effective_xw = wc.max_crosswind if wc.max_crosswind is not None else abs(wc.crosswind)
            return effective_xw > limit_kt

        return self._new_collection([r for r in self._items if exceeds(r)])

    # --- Grouping ---

    def group_by_airport(self) -> Dict[str, 'WeatherCollection']:
        """Group reports by ICAO code."""
        groups = self.group_by(lambda r: r.icao)
        return {k: self._new_collection(v) for k, v in groups.items()}

    # --- Set operations (override to preserve type) ---

    def __or__(self, other: 'WeatherCollection') -> 'WeatherCollection':
        result = super().__or__(other)
        return self._new_collection(result._items)

    def __and__(self, other: 'WeatherCollection') -> 'WeatherCollection':
        result = super().__and__(other)
        return self._new_collection(result._items)

    def __sub__(self, other: 'WeatherCollection') -> 'WeatherCollection':
        result = super().__sub__(other)
        return self._new_collection(result._items)
