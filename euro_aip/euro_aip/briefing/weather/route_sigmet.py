"""Route SIGMET service — find SIGMETs that affect a planned route.

Mirrors :class:`RouteWeatherService`: resolve a route to geometry, query the
SIGMET source, then filter to the hazards that actually intersect the route
corridor and altitude band. Filtering runs in three stages, cheapest first:

1. **Vertical filter** — drop SIGMETs whose layer misses the altitude band.
2. **FIR prefilter** — the FIRs the route crosses (``model.firs_along_route``)
   give a cheap candidate test against each SIGMET's ``fir_id``.
3. **Geometry refine** — densely sample the route and measure each sample
   against the SIGMET polygon (bbox prefilter, then containment + corridor
   distance) to confirm and to record the enroute extent affected.

The result carries enough metadata (matched FIRs, perpendicular distance,
enroute span) for a client to order and present SIGMETs along the route.
"""

import logging
from dataclasses import dataclass, field
from typing import List, Optional, Tuple, TYPE_CHECKING

from euro_aip.utils.geometry import (
    bbox_intersects,
    bbox_pad,
    haversine_nm,
    min_distance_point_to_multipolygon_nm,
    point_in_multipolygon,
    sample_polyline,
)

if TYPE_CHECKING:
    from euro_aip.briefing.sources.avwx import AvWxSource
    from euro_aip.briefing.weather.sigmet import SigmetReport
    from euro_aip.models.euro_aip_model import EuroAipModel

logger = logging.getLogger(__name__)


@dataclass
class RouteSigmet:
    """A SIGMET matched to a route, with intersection metadata.

    Attributes:
        sigmet: The matched SigmetReport.
        matched_firs: Route FIRs whose id equals the SIGMET's ``fir_id``.
        min_distance_nm: Smallest perpendicular distance between the route
            centreline and the SIGMET polygon (0.0 if the route enters it).
            None when matched without usable geometry.
        enroute_distance_from_nm: Nearest along-route distance (from departure)
            at which the corridor meets the SIGMET. None without geometry.
        enroute_distance_to_nm: Farthest along-route distance still affected.
            None without geometry.
    """

    sigmet: "SigmetReport"
    matched_firs: List[str] = field(default_factory=list)
    min_distance_nm: Optional[float] = None
    enroute_distance_from_nm: Optional[float] = None
    enroute_distance_to_nm: Optional[float] = None


@dataclass
class RouteSigmetResult:
    """SIGMETs affecting a route.

    Attributes:
        route_icaos: ICAO codes defining the route.
        corridor_nm: Corridor half-width used for matching, in nautical miles.
        altitude_band_ft: ``(low_ft, high_ft)`` band tested vertically; either
            bound may be None (open-ended).
        route_firs: FIR ICAO codes the route corridor crosses.
        sigmets: Matched SIGMETs, sorted by nearest enroute distance.
    """

    route_icaos: List[str]
    corridor_nm: float
    altitude_band_ft: Tuple[Optional[int], Optional[int]]
    route_firs: List[str] = field(default_factory=list)
    sigmets: List[RouteSigmet] = field(default_factory=list)


@dataclass
class _RouteSample:
    lon: float
    lat: float
    enroute_nm: float


class RouteSigmetService:
    """Orchestrates SIGMET discovery for a route corridor.

    Combines EuroAipModel geometry (route resolution + FIR boundaries) with
    AvWxSource SIGMET data.

    Example:
        from euro_aip import load_model
        from euro_aip.briefing.weather.route_sigmet import RouteSigmetService

        model = load_model("airports.db")
        service = RouteSigmetService()
        result = service.fetch_route_sigmets(
            ["EGLL", "LFPG"], corridor_nm=50, model=model,
            altitude_band_ft=(0, 18000),
        )
        for rs in result.sigmets:
            print(rs.sigmet.fir_id, rs.sigmet.hazard, rs.min_distance_nm)
    """

    def __init__(self, source: Optional["AvWxSource"] = None):
        """
        Args:
            source: AvWxSource instance. Created automatically if not provided.
        """
        self._source = source

    def _get_source(self) -> "AvWxSource":
        if self._source is None:
            from euro_aip.briefing.sources.avwx import AvWxSource
            self._source = AvWxSource()
        return self._source

    def fetch_route_sigmets(
        self,
        route_icaos: List[str],
        corridor_nm: float,
        model: "EuroAipModel",
        altitude_band_ft: Tuple[Optional[int], Optional[int]] = (None, None),
        hazard: Optional[str] = None,
        region: str = "eur",
        sample_step_nm: float = 5.0,
    ) -> RouteSigmetResult:
        """
        Find SIGMETs that affect a route.

        Args:
            route_icaos: ICAO codes defining the route waypoints.
            corridor_nm: Corridor half-width in nautical miles from the centreline.
            model: EuroAipModel providing airport coordinates and FIR boundaries.
            altitude_band_ft: ``(low_ft, high_ft)`` band to test; either may be
                None for open-ended.
            hazard: Optional hazard filter passed to the source (``"turb"``/``"ice"``).
            region: SIGMET region code (default ``"eur"``).
            sample_step_nm: Route sampling interval for geometry refinement.

        Returns:
            RouteSigmetResult with matched SIGMETs sorted by enroute distance.
        """
        low_ft, high_ft = altitude_band_ft
        route_points = self._resolve_route_points(route_icaos, model)

        if not route_points:
            logger.warning("No resolvable coordinates for route %s", "-".join(route_icaos))
            return RouteSigmetResult(
                route_icaos=route_icaos,
                corridor_nm=corridor_nm,
                altitude_band_ft=altitude_band_ft,
            )

        # Stage 2 (FIR prefilter) inputs: which FIRs does the corridor cross?
        route_firs = set(model.firs_along_route(route_points, corridor_nm=corridor_nm))

        # Dense route samples (with along-track distance) for geometry refine.
        samples = self._sample_route(route_points, sample_step_nm)
        route_bbox = self._samples_bbox(samples)
        route_bbox_padded = bbox_pad(route_bbox, corridor_nm)

        source = self._get_source()
        sigmets = source.fetch_isigmet(region=region, hazard=hazard)
        logger.info(
            "Fetched %d SIGMET(s); route crosses FIRs %s",
            len(sigmets), sorted(route_firs),
        )

        matched: List[RouteSigmet] = []
        for sigmet in sigmets:
            # Stage 1: vertical filter.
            if not sigmet.overlaps_altitude(low_ft, high_ft):
                continue

            fir_match = bool(sigmet.fir_id and sigmet.fir_id.upper() in route_firs)
            polygons = sigmet.polygons

            if polygons:
                # Stage 3: geometry refine (authoritative when geometry exists).
                geom = self._intersect(
                    samples, route_bbox_padded, sigmet, corridor_nm,
                )
                if geom is None:
                    continue
                min_dist, d_from, d_to = geom
                matched.append(RouteSigmet(
                    sigmet=sigmet,
                    matched_firs=[sigmet.fir_id] if fir_match else [],
                    min_distance_nm=min_dist,
                    enroute_distance_from_nm=d_from,
                    enroute_distance_to_nm=d_to,
                ))
            elif fir_match:
                # No usable polygon — fall back to the FIR prefilter result.
                matched.append(RouteSigmet(
                    sigmet=sigmet,
                    matched_firs=[sigmet.fir_id],
                ))

        matched.sort(key=lambda rs: (
            rs.enroute_distance_from_nm
            if rs.enroute_distance_from_nm is not None else float("inf")
        ))

        return RouteSigmetResult(
            route_icaos=route_icaos,
            corridor_nm=corridor_nm,
            altitude_band_ft=altitude_band_ft,
            route_firs=sorted(route_firs),
            sigmets=matched,
        )

    @staticmethod
    def _resolve_route_points(route_icaos: List[str], model: "EuroAipModel") -> list:
        """Resolve route ICAOs to NavPoints, dropping any without coordinates."""
        airports = model.airports
        points = []
        for icao in route_icaos:
            airport = airports.get(icao.strip().upper())
            if airport is None:
                logger.warning("Route airport %s not found, skipping", icao)
                continue
            navpoint = getattr(airport, "navpoint", None)
            if navpoint is None:
                logger.warning("Route airport %s missing coordinates, skipping", icao)
                continue
            points.append(navpoint)
        return points

    @staticmethod
    def _sample_route(route_points: list, step_nm: float) -> List[_RouteSample]:
        """Sample the route polyline, tagging each sample with along-track distance."""
        polyline = [(p.longitude, p.latitude) for p in route_points]
        if len(polyline) == 1:
            return [_RouteSample(polyline[0][0], polyline[0][1], 0.0)]

        sampled = sample_polyline(polyline, step_nm)
        out: List[_RouteSample] = []
        cumulative = 0.0
        prev: Optional[Tuple[float, float]] = None
        for lon, lat in sampled:
            if prev is not None:
                cumulative += haversine_nm(prev[1], prev[0], lat, lon)
            out.append(_RouteSample(lon, lat, cumulative))
            prev = (lon, lat)
        return out

    @staticmethod
    def _samples_bbox(samples: List[_RouteSample]) -> Tuple[float, float, float, float]:
        lons = [s.lon for s in samples]
        lats = [s.lat for s in samples]
        return (min(lons), min(lats), max(lons), max(lats))

    @staticmethod
    def _intersect(
        samples: List[_RouteSample],
        route_bbox_padded: Tuple[float, float, float, float],
        sigmet: "SigmetReport",
        corridor_nm: float,
    ) -> Optional[Tuple[float, float, float]]:
        """Corridor ∩ SIGMET polygon test.

        Returns ``(min_distance_nm, enroute_from_nm, enroute_to_nm)`` if any
        route sample lies inside the polygon or within ``corridor_nm`` of its
        boundary, else None. A bbox prefilter (SIGMET bbox padded by the
        corridor) short-circuits non-overlapping SIGMETs.
        """
        sigmet_bbox = sigmet.bbox
        if sigmet_bbox is None:
            return None
        if not bbox_intersects(bbox_pad(sigmet_bbox, corridor_nm), route_bbox_padded):
            return None

        polygons = sigmet.polygons
        min_dist = float("inf")
        d_from: Optional[float] = None
        d_to: Optional[float] = None

        for s in samples:
            if point_in_multipolygon(s.lon, s.lat, polygons):
                dist = 0.0
            else:
                dist = min_distance_point_to_multipolygon_nm(s.lon, s.lat, polygons)
                if dist > corridor_nm:
                    continue
            min_dist = min(min_dist, dist)
            if d_from is None or s.enroute_nm < d_from:
                d_from = s.enroute_nm
            if d_to is None or s.enroute_nm > d_to:
                d_to = s.enroute_nm

        if d_from is None:
            return None
        return (min_dist, d_from, d_to)
