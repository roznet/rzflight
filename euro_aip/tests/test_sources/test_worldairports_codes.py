"""WorldAirportsSource stores airports under their current ICAO code."""

import pandas as pd

from euro_aip.models.euro_aip_model import EuroAipModel
from euro_aip.sources.worldairports import WorldAirportsSource


AIRPORT_COLUMNS = [
    "ident", "type", "name", "latitude_deg", "longitude_deg", "elevation_ft",
    "continent", "iso_country", "iso_region", "municipality", "scheduled_service",
    "icao_code", "iata_code", "gps_code", "local_code", "home_link",
    "wikipedia_link", "keywords",
]
RUNWAY_COLUMNS = [
    "airport_ident", "length_ft", "width_ft", "surface", "lighted", "closed",
    "le_ident", "le_latitude_deg", "le_longitude_deg", "le_elevation_ft",
    "le_heading_degT", "le_displaced_threshold_ft", "he_ident", "he_latitude_deg",
    "he_longitude_deg", "he_elevation_ft", "he_heading_degT",
    "he_displaced_threshold_ft",
]


def _airport_row(ident, name, lat, lon, country, icao_code=None, gps_code=None):
    row = dict.fromkeys(AIRPORT_COLUMNS)
    row.update(ident=ident, type="small_airport", name=name, latitude_deg=lat,
               longitude_deg=lon, continent="EU", iso_country=country,
               icao_code=icao_code, gps_code=gps_code)
    return row


def _runway_row(airport_ident, le_ident, he_ident):
    row = dict.fromkeys(RUNWAY_COLUMNS)
    row.update(airport_ident=airport_ident, length_ft=3500, surface="ASP",
               lighted=0, closed=0, le_ident=le_ident, he_ident=he_ident)
    return row


class _InMemoryWorldAirports(WorldAirportsSource):
    def __init__(self, cache_dir, airports, runways):
        super().__init__(cache_dir)
        self._airports_df = pd.DataFrame(airports, columns=AIRPORT_COLUMNS)
        self._runways_df = pd.DataFrame(runways, columns=RUNWAY_COLUMNS)

    def get_airports(self, max_age_days: int = 7) -> pd.DataFrame:
        return self._airports_df

    def get_runways(self, max_age_days: int = 7) -> pd.DataFrame:
        return self._runways_df


def test_airports_stored_under_current_codes(tmp_path):
    source = _InMemoryWorldAirports(
        str(tmp_path),
        airports=[
            _airport_row("GB-0007", "Enstone Aerodrome", 51.928167, -1.4285, "GB",
                         icao_code="EGTN", gps_code="EGTN"),
            _airport_row("LELO", "Logroño-Agoncillo Airport", 42.460953, -2.322235, "ES",
                         icao_code="LERJ", gps_code="LERJ"),
            _airport_row("EGTK", "London Oxford Airport", 51.8369, -1.32, "GB",
                         icao_code="EGTK", gps_code="EGTK"),
            _airport_row("GB-0023", "Shenstone Hall Farm Airstrip", 52.64, -1.82, "GB"),
        ],
        runways=[_runway_row("GB-0007", "08", "26")],
    )
    model = EuroAipModel()

    source.update_model(model)

    assert sorted(a.ident for a in model.airports) == ["EGTK", "EGTN", "LERJ"]
    enstone = model.airports["EGTN"]
    assert enstone.name == "Enstone Aerodrome"
    # Runways join on the OurAirports ident but belong to the stored code
    assert [r.airport_ident for r in enstone.runways] == ["EGTN"]
    assert model.airports["LERJ"].alt_ident == "LELO"
    assert model.airports["EGTK"].alt_ident is None


def test_filter_by_code(tmp_path):
    source = _InMemoryWorldAirports(
        str(tmp_path),
        airports=[
            _airport_row("GB-0007", "Enstone Aerodrome", 51.928167, -1.4285, "GB",
                         icao_code="EGTN"),
            _airport_row("EGTK", "London Oxford Airport", 51.8369, -1.32, "GB",
                         icao_code="EGTK"),
        ],
        runways=[],
    )
    model = EuroAipModel()

    source.update_model(model, airports=["EGTN"])

    assert [a.ident for a in model.airports] == ["EGTN"]
