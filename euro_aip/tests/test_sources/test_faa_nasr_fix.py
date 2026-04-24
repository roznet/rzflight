"""Tests for FAA NASR fixes source."""

import io
import zipfile

import pytest

from euro_aip.sources.faa_nasr_fix import FAANasrFixSource


# Real FAA FIX_BASE.csv header + a few real rows, lightly edited for coverage.
SAMPLE_CSV = (
    '"EFF_DATE","FIX_ID","ICAO_REGION_CODE","STATE_CODE","COUNTRY_CODE",'
    '"LAT_DEG","LAT_MIN","LAT_SEC","LAT_HEMIS","LAT_DECIMAL",'
    '"LONG_DEG","LONG_MIN","LONG_SEC","LONG_HEMIS","LONG_DECIMAL",'
    '"FIX_ID_OLD","CHARTING_REMARK","FIX_USE_CODE","ARTCC_ID_HIGH","ARTCC_ID_LOW",'
    '"PITCH_FLAG","CATCH_FLAG","SUA_ATCAA_FLAG","MIN_RECEP_ALT","COMPULSORY","CHARTS"\n'
    # Standard row: ARTCCs match
    '"2026/04/16","AAALL","K6","MA","US",42,7,12.68,"N",42.12018888,'
    '71,8,30.34,"W",-71.14176111,"","","WP","ZBW","ZBW",'
    '"N","N","N",,"","IAP"\n'
    # ARTCCs differ — expect joined
    '"2026/04/16","DIFFR","K2","CA","US",37,0,0.0,"N",37.0,'
    '122,0,0.0,"W",-122.0,"","","WP","ZOA","ZLA",'
    '"N","N","N",,"","ENROUTE"\n'
    # No state — source_id should still be well-formed
    '"2026/04/16","NOSTA","KX","","US",40,0,0.0,"N",40.0,'
    '100,0,0.0,"W",-100.0,"","","WP","ZKC","ZKC",'
    '"N","N","N",,"","ENROUTE"\n'
    # Bad coords — should be skipped
    '"2026/04/16","BADCO","K1","TX","US",,,"","N",,'
    ',,"","W",,"","","WP","ZHU","ZHU",'
    '"N","N","N",,"",""\n'
    # Empty FIX_ID — should be skipped
    '"2026/04/16","","K1","TX","US",30,0,0.0,"N",30.0,'
    '90,0,0.0,"W",-90.0,"","","WP","ZHU","ZHU",'
    '"N","N","N",,"",""\n'
)


class TestParseCSV:
    def _make_source(self):
        return FAANasrFixSource(cache_dir="/tmp/test_faa_cache")

    def test_parses_valid_rows(self):
        waypoints = self._make_source()._parse_csv(SAMPLE_CSV)
        names = {wp.name for wp in waypoints}
        assert names == {"AAALL", "DIFFR", "NOSTA"}

    def test_skips_bad_coords(self):
        waypoints = self._make_source()._parse_csv(SAMPLE_CSV)
        assert all(wp.name != "BADCO" for wp in waypoints)

    def test_skips_empty_fix_id(self):
        waypoints = self._make_source()._parse_csv(SAMPLE_CSV)
        # Empty-ident row should be silently skipped
        assert all(wp.name for wp in waypoints)

    def test_coordinates_are_decimal(self):
        waypoints = self._make_source()._parse_csv(SAMPLE_CSV)
        by_name = {wp.name: wp for wp in waypoints}
        assert abs(by_name["AAALL"].latitude_deg - 42.12018888) < 1e-6
        assert abs(by_name["AAALL"].longitude_deg - (-71.14176111)) < 1e-6

    def test_point_type_is_5lnc(self):
        """All FAA fixes map to 5LNC — the source doesn't emit NAVAIDs."""
        waypoints = self._make_source()._parse_csv(SAMPLE_CSV)
        assert all(wp.point_type == "5LNC" for wp in waypoints)

    def test_source_field(self):
        waypoints = self._make_source()._parse_csv(SAMPLE_CSV)
        assert all(wp.source == "faa_nasr" for wp in waypoints)

    def test_source_id_encodes_state(self):
        waypoints = self._make_source()._parse_csv(SAMPLE_CSV)
        by_name = {wp.name: wp for wp in waypoints}
        assert by_name["AAALL"].source_id == "faa_nasr:MA"
        assert by_name["DIFFR"].source_id == "faa_nasr:CA"

    def test_source_id_handles_missing_state(self):
        waypoints = self._make_source()._parse_csv(SAMPLE_CSV)
        by_name = {wp.name: wp for wp in waypoints}
        # Missing state still produces a well-formed (if empty-suffixed) id
        assert by_name["NOSTA"].source_id.startswith("faa_nasr:")


class TestFirCodes:
    def _make_source(self):
        return FAANasrFixSource(cache_dir="/tmp/test_faa_cache")

    def test_same_artccs_store_one(self):
        """When ARTCC_HIGH == ARTCC_LOW, fir_codes is a single ICAO, not duplicated."""
        waypoints = self._make_source()._parse_csv(SAMPLE_CSV)
        by_name = {wp.name: wp for wp in waypoints}
        assert by_name["AAALL"].fir_codes == "ZBW"

    def test_different_artccs_joined(self):
        """When HIGH and LOW differ, fir_codes is 'HIGH,LOW'."""
        waypoints = self._make_source()._parse_csv(SAMPLE_CSV)
        by_name = {wp.name: wp for wp in waypoints}
        assert by_name["DIFFR"].fir_codes == "ZOA,ZLA"


class TestUrlBuilding:
    def test_url_format_matches_published_pattern(self):
        """The extra/CSV zip URL encodes date as DD_MonAbbr_YYYY."""
        url = FAANasrFixSource._build_download_url("2026-04-16")
        assert url == (
            "https://nfdc.faa.gov/webContent/28DaySub/extra/"
            "16_Apr_2026_FIX_CSV.zip"
        )

    def test_url_zero_pads_day(self):
        url = FAANasrFixSource._build_download_url("2026-01-07")
        assert "07_Jan_2026_FIX_CSV.zip" in url

    def test_bad_date_raises(self):
        with pytest.raises(ValueError):
            FAANasrFixSource._build_download_url("not-a-date")


class TestZipExtraction:
    def test_extracts_fix_base_csv(self):
        # Synthesise a minimal zip containing FIX_BASE.csv
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("FIX_BASE.csv", SAMPLE_CSV)
            zf.writestr("README.txt", "ignore me")

        extracted = FAANasrFixSource._extract_fix_base_csv(buf.getvalue())
        assert "AAALL" in extracted
        assert "EFF_DATE" in extracted
