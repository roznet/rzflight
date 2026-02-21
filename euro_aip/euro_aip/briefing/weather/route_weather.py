"""Route weather service — spatial airport discovery + weather fetch orchestration."""

import logging
from dataclasses import dataclass, field
from typing import List, Optional, TYPE_CHECKING

from euro_aip.briefing.weather.collection import WeatherCollection
from euro_aip.briefing.weather.models import WeatherReport, WeatherType

if TYPE_CHECKING:
    from euro_aip.briefing.sources.avwx import AvWxSource
    from euro_aip.models.euro_aip_model import EuroAipModel

logger = logging.getLogger(__name__)


@dataclass
class RouteAirportWeather:
    """Weather data for a single airport along a route.

    Attributes:
        icao: Airport ICAO code.
        name: Airport name (if available).
        distance_from_route_nm: Perpendicular distance to route centerline.
        enroute_distance_nm: Distance along route from departure.
        reports: WeatherCollection of all reports for this airport.
    """

    icao: str
    name: Optional[str]
    distance_from_route_nm: float
    enroute_distance_nm: Optional[float]
    reports: WeatherCollection = field(default_factory=lambda: WeatherCollection([]))

    @property
    def latest_metar(self) -> Optional[WeatherReport]:
        """Most recent METAR/SPECI for this airport."""
        return self.reports.metars().latest()

    @property
    def latest_taf(self) -> Optional[WeatherReport]:
        """Most recent TAF for this airport."""
        return self.reports.tafs().latest()

    @property
    def has_weather(self) -> bool:
        """Whether any weather reports exist for this airport."""
        return len(self.reports) > 0


@dataclass
class RouteWeatherResult:
    """Weather along a route corridor.

    Attributes:
        route_icaos: ICAO codes defining the route.
        corridor_nm: Corridor width in nautical miles.
        airports: All airports found along the route, sorted by enroute distance.
    """

    route_icaos: List[str]
    corridor_nm: float
    airports: List[RouteAirportWeather] = field(default_factory=list)

    @property
    def airports_with_weather(self) -> List[RouteAirportWeather]:
        """Airports that have at least one weather report."""
        return [a for a in self.airports if a.has_weather]

    @property
    def collection(self) -> WeatherCollection:
        """All weather reports merged into a single collection."""
        all_reports = []
        for airport in self.airports:
            all_reports.extend(airport.reports.all())
        return WeatherCollection(all_reports)


class RouteWeatherService:
    """Orchestrates spatial airport discovery and weather fetching for a route.

    Combines EuroAipModel.find_airports_near_route() for spatial queries
    with AvWxSource for live weather data.

    Example:
        from euro_aip import load_model
        from euro_aip.briefing.sources.avwx import AvWxSource
        from euro_aip.briefing.weather.route_weather import RouteWeatherService

        model = load_model("airports.db")
        service = RouteWeatherService()
        result = service.fetch_route_weather(
            ["EGLL", "LFPG"], corridor_nm=25, model=model
        )
        for apt in result.airports_with_weather:
            metar = apt.latest_metar
            print(f"{apt.icao} ({apt.name}): {metar.flight_category}")
    """

    def __init__(self, source: Optional['AvWxSource'] = None):
        """
        Args:
            source: AvWxSource instance. Created automatically if not provided.
        """
        self._source = source

    def _get_source(self) -> 'AvWxSource':
        if self._source is None:
            from euro_aip.briefing.sources.avwx import AvWxSource
            self._source = AvWxSource()
        return self._source

    def fetch_route_weather(
        self,
        route_icaos: List[str],
        corridor_nm: float,
        model: 'EuroAipModel',
        metar_hours: float = 3,
    ) -> RouteWeatherResult:
        """
        Find airports along a route and fetch their weather.

        Args:
            route_icaos: ICAO codes defining the route waypoints.
            corridor_nm: Corridor width in nautical miles from route centerline.
            model: EuroAipModel with airport database for spatial queries.
            metar_hours: Hours of METAR history to fetch.

        Returns:
            RouteWeatherResult with airports sorted by enroute distance.
        """
        # 1. Find airports near the route
        nearby = model.find_airports_near_route(route_icaos, distance_nm=corridor_nm)
        logger.info(
            "Found %d airports within %dnm of route %s",
            len(nearby), corridor_nm, "-".join(route_icaos),
        )

        # 2. Build airport info list
        airport_infos = {}
        for entry in nearby:
            airport = entry["airport"]
            icao = airport.ident
            airport_infos[icao] = RouteAirportWeather(
                icao=icao,
                name=getattr(airport, "name", None),
                distance_from_route_nm=entry["segment_distance_nm"],
                enroute_distance_nm=entry.get("enroute_distance_nm"),
            )

        # Ensure route airports are always included
        for icao in route_icaos:
            icao_upper = icao.upper()
            if icao_upper not in airport_infos:
                airport_infos[icao_upper] = RouteAirportWeather(
                    icao=icao_upper,
                    name=None,
                    distance_from_route_nm=0.0,
                    enroute_distance_nm=None,
                )

        # 3. Fetch weather for all airports
        all_icaos = list(airport_infos.keys())
        source = self._get_source()
        reports = source.fetch_weather(all_icaos, metar_hours=metar_hours)

        # 4. Distribute reports to airports by ICAO
        for report in reports:
            icao = report.icao.upper()
            if icao in airport_infos:
                existing = list(airport_infos[icao].reports.all())
                existing.append(report)
                airport_infos[icao].reports = WeatherCollection(existing)

        # 5. Sort by enroute distance (None values at end)
        airports_sorted = sorted(
            airport_infos.values(),
            key=lambda a: a.enroute_distance_nm if a.enroute_distance_nm is not None else float("inf"),
        )

        return RouteWeatherResult(
            route_icaos=route_icaos,
            corridor_nm=corridor_nm,
            airports=airports_sorted,
        )

    def fetch_airports_weather(
        self,
        icaos: List[str],
        metar_hours: float = 3,
    ) -> WeatherCollection:
        """
        Fetch weather for a known list of airports (no spatial query).

        Args:
            icaos: List of ICAO airport codes.
            metar_hours: Hours of METAR history to fetch.

        Returns:
            WeatherCollection with all fetched reports.
        """
        source = self._get_source()
        reports = source.fetch_weather(icaos, metar_hours=metar_hours)
        return WeatherCollection(reports)
