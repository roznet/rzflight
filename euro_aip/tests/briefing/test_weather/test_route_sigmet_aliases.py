"""A route airport given by its previous code places the SIGMET corridor like its current one."""

from unittest.mock import MagicMock

import pytest

from euro_aip.briefing.weather.route_sigmet import RouteSigmetService
from euro_aip.briefing.weather.sigmet import SigmetReport
from euro_aip.models.airport import Airport
from euro_aip.models.euro_aip_model import EuroAipModel


def _airport(ident, lat, lon, alt_ident=None):
    airport = Airport(ident=ident, alt_ident=alt_ident, name=f"{ident} Field",
                      latitude_deg=lat, longitude_deg=lon, iso_country="ES")
    airport.add_source("test_source")
    return airport


@pytest.fixture
def model():
    model = EuroAipModel()
    model.add_airport(_airport("LEMD", 40.4719, -3.5626))
    model.add_airport(_airport("LERJ", 42.4610, -2.3222, alt_ident="LELO"))
    return model


# Shaped like an AWC isigmet for Madrid FIR: a box around Logroño, well
# clear of Madrid, so it only matches when the route starts at LERJ.
SIGMET = SigmetReport(
    raw_text="LECM SIGMET 3 VALID 061200/061600 LEMM- LECM MADRID FIR SEV TURB "
             "OBS WI N4300 W00300 - N4300 W00145 - N4200 W00145 - N4200 W00300 "
             "- N4300 W00300 FL100/240 STNR NC=",
    fir_id="LECM",
    hazard="TURB",
    qualifier="SEV",
    base_ft=10000,
    top_ft=24000,
    coords=[(-3.0, 43.0), (-1.75, 43.0), (-1.75, 42.0), (-3.0, 42.0), (-3.0, 43.0)],
    source="avwx",
)


def _fetch(route, model):
    source = MagicMock()
    source.fetch_isigmet.return_value = [SIGMET]
    return RouteSigmetService(source=source).fetch_route_sigmets(
        route, corridor_nm=10, model=model, altitude_band_ft=(0, 18000),
    )


def test_previous_code_gives_same_corridor_as_current_code(model):
    current = _fetch(["LERJ", "LEMD"], model)
    previous = _fetch(["LELO", "LEMD"], model)

    [match] = current.sigmets
    [alias_match] = previous.sigmets
    assert alias_match.min_distance_nm == match.min_distance_nm
    assert alias_match.enroute_distance_from_nm == match.enroute_distance_from_nm
    assert alias_match.enroute_distance_to_nm == match.enroute_distance_to_nm
    assert previous.route_firs == current.route_firs


def test_route_names_keep_the_code_as_given(model):
    assert _fetch(["lelo", "LEMD"], model).route_icaos == ["lelo", "LEMD"]
