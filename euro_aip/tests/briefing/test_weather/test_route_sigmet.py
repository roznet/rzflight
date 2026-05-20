"""Tests for RouteSigmetService."""

from unittest.mock import MagicMock

from euro_aip.briefing.weather.route_sigmet import (
    RouteSigmet,
    RouteSigmetResult,
    RouteSigmetService,
)
from euro_aip.briefing.weather.sigmet import SigmetReport
from euro_aip.models.navpoint import NavPoint


def make_sigmet(fir_id, coords, base_ft=10000, top_ft=24000, hazard="TURB"):
    return SigmetReport(
        raw_text=f"{fir_id} SIGMET",
        fir_id=fir_id,
        hazard=hazard,
        qualifier="SEV",
        base_ft=base_ft,
        top_ft=top_ft,
        coords=coords,
        source="avwx",
    )


def box(lon_min, lat_min, lon_max, lat_max):
    """A rectangular (lon, lat) ring."""
    return [
        (lon_min, lat_min),
        (lon_max, lat_min),
        (lon_max, lat_max),
        (lon_min, lat_max),
        (lon_min, lat_min),
    ]


def make_airport(icao, lat, lon):
    apt = MagicMock()
    apt.ident = icao
    apt.navpoint = NavPoint(latitude=lat, longitude=lon, name=icao)
    return apt


def make_model(airports, route_firs):
    """Mock EuroAipModel: airports.get() resolves coords, firs_along_route()
    returns the supplied FIR list."""
    model = MagicMock()
    by_icao = {a.ident: a for a in airports}
    model.airports.get.side_effect = lambda icao, default=None: by_icao.get(icao, default)
    model.firs_along_route.return_value = list(route_firs)
    return model


def make_source(sigmets):
    source = MagicMock()
    source.fetch_isigmet.return_value = sigmets
    return source


# Route: A(51,0) → B(50,2). At lon=1.0 the centreline passes through (50.5, 1.0).
ROUTE = ["AAAA", "BBBB"]
ROUTE_AIRPORTS = [make_airport("AAAA", 51.0, 0.0), make_airport("BBBB", 50.0, 2.0)]


class TestResolution:
    def test_no_resolvable_points_returns_empty(self):
        model = make_model([], route_firs=["EGTT"])
        service = RouteSigmetService(source=make_source([]))
        result = service.fetch_route_sigmets(["ZZZZ"], corridor_nm=50, model=model)
        assert isinstance(result, RouteSigmetResult)
        assert result.sigmets == []
        assert result.route_firs == []


class TestGeometryMatching:
    def test_sigmet_on_route_matched(self):
        on_route = make_sigmet("EGTT", box(0.8, 50.3, 1.2, 50.7))
        model = make_model(ROUTE_AIRPORTS, route_firs=["EGTT"])
        service = RouteSigmetService(source=make_source([on_route]))

        result = service.fetch_route_sigmets(
            ROUTE, corridor_nm=25, model=model, altitude_band_ft=(0, 18000),
        )

        assert len(result.sigmets) == 1
        rs = result.sigmets[0]
        assert rs.sigmet.fir_id == "EGTT"
        assert rs.min_distance_nm == 0.0          # centreline enters polygon
        assert rs.enroute_distance_from_nm is not None
        assert rs.matched_firs == ["EGTT"]

    def test_far_sigmet_excluded(self):
        far = make_sigmet("LGGG", box(20.0, 38.0, 22.0, 40.0))
        model = make_model(ROUTE_AIRPORTS, route_firs=["EGTT"])
        service = RouteSigmetService(source=make_source([far]))

        result = service.fetch_route_sigmets(
            ROUTE, corridor_nm=25, model=model, altitude_band_ft=(0, 18000),
        )
        assert result.sigmets == []

    def test_nearby_sigmet_within_corridor_matched(self):
        # Box sits just north of the route; nearest edge ~12 nm from centreline.
        nearby = make_sigmet("EGTT", box(0.9, 50.7, 1.1, 50.9))
        model = make_model(ROUTE_AIRPORTS, route_firs=["EGTT"])
        service = RouteSigmetService(source=make_source([nearby]))

        wide = service.fetch_route_sigmets(
            ROUTE, corridor_nm=30, model=model, altitude_band_ft=(0, 18000),
        )
        assert len(wide.sigmets) == 1
        assert wide.sigmets[0].min_distance_nm > 0.0

        narrow = service.fetch_route_sigmets(
            ROUTE, corridor_nm=2, model=model, altitude_band_ft=(0, 18000),
        )
        assert narrow.sigmets == []


class TestVerticalFilter:
    def test_band_below_layer_excluded(self):
        s = make_sigmet("EGTT", box(0.8, 50.3, 1.2, 50.7), base_ft=20000, top_ft=30000)
        model = make_model(ROUTE_AIRPORTS, route_firs=["EGTT"])
        service = RouteSigmetService(source=make_source([s]))

        result = service.fetch_route_sigmets(
            ROUTE, corridor_nm=25, model=model, altitude_band_ft=(0, 5000),
        )
        assert result.sigmets == []

    def test_band_overlaps_included(self):
        s = make_sigmet("EGTT", box(0.8, 50.3, 1.2, 50.7), base_ft=20000, top_ft=30000)
        model = make_model(ROUTE_AIRPORTS, route_firs=["EGTT"])
        service = RouteSigmetService(source=make_source([s]))

        result = service.fetch_route_sigmets(
            ROUTE, corridor_nm=25, model=model, altitude_band_ft=(0, 25000),
        )
        assert len(result.sigmets) == 1

    def test_open_band_includes_all_altitudes(self):
        s = make_sigmet("EGTT", box(0.8, 50.3, 1.2, 50.7), base_ft=35000, top_ft=45000)
        model = make_model(ROUTE_AIRPORTS, route_firs=["EGTT"])
        service = RouteSigmetService(source=make_source([s]))

        result = service.fetch_route_sigmets(ROUTE, corridor_nm=25, model=model)
        assert len(result.sigmets) == 1


class TestFirFallback:
    def test_no_coords_uses_fir_match(self):
        s = make_sigmet("EGTT", coords=[])  # no usable polygon
        model = make_model(ROUTE_AIRPORTS, route_firs=["EGTT"])
        service = RouteSigmetService(source=make_source([s]))

        result = service.fetch_route_sigmets(
            ROUTE, corridor_nm=25, model=model, altitude_band_ft=(0, 18000),
        )
        assert len(result.sigmets) == 1
        rs = result.sigmets[0]
        assert rs.matched_firs == ["EGTT"]
        assert rs.min_distance_nm is None
        assert rs.enroute_distance_from_nm is None

    def test_no_coords_no_fir_match_excluded(self):
        s = make_sigmet("LGGG", coords=[])
        model = make_model(ROUTE_AIRPORTS, route_firs=["EGTT"])
        service = RouteSigmetService(source=make_source([s]))

        result = service.fetch_route_sigmets(
            ROUTE, corridor_nm=25, model=model, altitude_band_ft=(0, 18000),
        )
        assert result.sigmets == []


class TestResultMetadata:
    def test_route_firs_reported(self):
        model = make_model(ROUTE_AIRPORTS, route_firs=["EGTT", "EBBU"])
        service = RouteSigmetService(source=make_source([]))
        result = service.fetch_route_sigmets(ROUTE, corridor_nm=25, model=model)
        assert result.route_firs == ["EBBU", "EGTT"]
        assert result.corridor_nm == 25
        assert result.route_icaos == ROUTE

    def test_sorted_by_enroute_distance(self):
        # Two on-route boxes at different along-track positions.
        near_start = make_sigmet("EGTT", box(-0.1, 50.85, 0.1, 51.05))  # near A(51,0)
        near_end = make_sigmet("EGTT", box(1.9, 49.95, 2.1, 50.15))      # near B(50,2)
        model = make_model(ROUTE_AIRPORTS, route_firs=["EGTT"])
        service = RouteSigmetService(source=make_source([near_end, near_start]))

        result = service.fetch_route_sigmets(
            ROUTE, corridor_nm=30, model=model, altitude_band_ft=(0, 18000),
        )
        assert len(result.sigmets) == 2
        froms = [rs.enroute_distance_from_nm for rs in result.sigmets]
        assert froms == sorted(froms)


class TestLazySource:
    def test_source_created_lazily(self):
        from unittest.mock import patch
        model = make_model(ROUTE_AIRPORTS, route_firs=["EGTT"])
        service = RouteSigmetService()
        with patch("euro_aip.briefing.sources.avwx.AvWxSource") as mock_cls:
            instance = MagicMock()
            instance.fetch_isigmet.return_value = []
            mock_cls.return_value = instance
            service.fetch_route_sigmets(ROUTE, corridor_nm=25, model=model)
            mock_cls.assert_called_once()
