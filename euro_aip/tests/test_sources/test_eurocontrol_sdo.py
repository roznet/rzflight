"""Tests for Eurocontrol SDO Designated Points source."""

import pytest

from euro_aip.sources.eurocontrol_sdo import (
    EUROPE_BBOX,
    NORTH_AMERICA_BBOX,
    EurocontrolSDOSource,
    _in_bbox,
    _parse_lat,
    _parse_lon,
    _slug_originator,
)


# Realistic SDO export fragment with a mix of types and coord formats.
# Written as a single concatenated string — the real file is one long line
# but the parser doesn't care about whitespace between rows.
SAMPLE_HTML = """
<table>
<tr><td>Master gUID</td><td>Type</td><td>Identification</td><td>Name</td><td>Latitude</td><td>Longitude</td><td>Datum</td><td>Effective date</td><td>Originator</td></tr>
<tr><td>400001</td><td>ICAO</td><td>BILGO</td><td>BILGO</td><td>495406.94N</td><td>0032650.06E</td><td>WGE</td><td>03/10/2024</td><td>EUROCONTROL NMOC</td></tr>
<tr><td>400002</td><td>ICAO</td><td>VESAN</td><td>VESAN</td><td>50.37194444N</td><td>002.02638889E</td><td>WGE</td><td>12/06/2025</td><td>SERVICE DE LINFORMATION AERONAUTIQUE</td></tr>
<tr><td>400003</td><td>ICAO</td><td>AAALL</td><td>AAALL</td><td>420712.680N</td><td>0710830.340W</td><td>NAW</td><td>27/04/2017</td><td>FAA LOADER (EAD SP)</td></tr>
<tr><td>400004</td><td>ICAO</td><td>FAREAST</td><td>FAREAST</td><td>352000N</td><td>1391500E</td><td>WGE</td><td>01/01/2024</td><td>SOMETHING</td></tr>
<tr><td>400005</td><td>OTHER</td><td>001AB</td><td>2.0NM TO RW25</td><td>51.20591433N</td><td>014.58555031E</td><td>WGE</td><td>03/10/2024</td><td>EUROCONTROL NMOC</td></tr>
<tr><td>400006</td><td>ADHP</td><td>15NAT</td><td>15NAT</td><td>323147.7N</td><td>0344703.5E</td><td>WGE</td><td>09/11/2017</td><td>CIVIL AVIATION AUTHORITY ISRAEL</td></tr>
<tr><td>400007</td><td>COORD</td><td>00E50</td><td>00N150E</td><td>000000N</td><td>1500000E</td><td>WGE</td><td>01/08/2007</td><td>EUROCONTROL NMOC</td></tr>
<tr><td>400008</td><td>ICAO</td><td>NOFIX</td><td>NOFIX</td><td>BADCOORD</td><td>WORSE</td><td>U</td><td>01/01/2000</td><td>UNKNOWN</td></tr>
<tr><td>400009</td><td>ICAO</td><td>OCEAN</td><td>OCEAN</td><td>4830N</td><td>02100W</td><td>WGE</td><td>01/01/2020</td><td>EUROCONTROL NMOC</td></tr>
</table>
"""


class TestCoordParsing:
    def test_dms_with_decimal_seconds(self):
        # 49°54'06.94"N → 49.9019...
        assert _parse_lat("495406.94N") == pytest.approx(49.9019, abs=1e-3)
        # 003°26'50.06"E → 3.4472...
        assert _parse_lon("0032650.06E") == pytest.approx(3.4472, abs=1e-3)

    def test_dms_integer(self):
        # 53°55'20"N
        assert _parse_lat("535520N") == pytest.approx(53 + 55/60 + 20/3600, abs=1e-6)
        assert _parse_lon("0392841E") == pytest.approx(39 + 28/60 + 41/3600, abs=1e-6)

    def test_dm_only(self):
        # 48°30'N
        assert _parse_lat("4830N") == pytest.approx(48.5, abs=1e-6)
        # 021°00'W
        assert _parse_lon("02100W") == pytest.approx(-21.0, abs=1e-6)

    def test_dm_with_decimal_minutes(self):
        assert _parse_lat("0200.4N") == pytest.approx(2 + 0.4/60, abs=1e-6)

    def test_decimal_degrees(self):
        assert _parse_lat("56.64128497N") == pytest.approx(56.64128497, abs=1e-8)
        assert _parse_lon("003.32549222E") == pytest.approx(3.32549222, abs=1e-8)

    def test_southern_hemisphere(self):
        assert _parse_lat("523000S") == pytest.approx(-(52 + 30/60), abs=1e-6)

    def test_western_hemisphere(self):
        assert _parse_lon("0710830.340W") == pytest.approx(-(71 + 8/60 + 30.34/3600), abs=1e-6)

    def test_invalid_returns_none(self):
        assert _parse_lat("garbage") is None
        assert _parse_lat("") is None
        assert _parse_lon("999X") is None

    def test_priority_dms_before_decimal(self):
        # 420712.680 must NOT be parsed as decimal 420712.680 (impossible value).
        # It's DMS with decimal seconds: 42°07'12.68" = 42.12...
        assert _parse_lat("420712.680N") == pytest.approx(42.12018888, abs=1e-6)


class TestBoundingBox:
    def test_europe_box(self):
        assert _in_bbox(48.86, 2.35, EUROPE_BBOX)        # Paris
        assert _in_bbox(60.17, 24.94, EUROPE_BBOX)       # Helsinki
        assert not _in_bbox(40.71, -74.00, EUROPE_BBOX)  # NYC
        assert not _in_bbox(35.69, 139.69, EUROPE_BBOX)  # Tokyo

    def test_north_america_box(self):
        assert _in_bbox(40.71, -74.00, NORTH_AMERICA_BBOX)   # NYC
        assert _in_bbox(60.0, -100.0, NORTH_AMERICA_BBOX)    # central Canada
        assert not _in_bbox(48.86, 2.35, NORTH_AMERICA_BBOX) # Paris


class TestSlugOriginator:
    def test_strips_punctuation(self):
        assert _slug_originator("EUROCONTROL NMOC") == "EUROCONTROL_NMOC"
        assert _slug_originator("FAA LOADER (EAD SP)") == "FAA_LOADER_EAD_SP"

    def test_handles_empty(self):
        assert _slug_originator("") == "unknown"


class TestParse:
    def _make_source(self, tmp_path, html=SAMPLE_HTML):
        f = tmp_path / "sample.html"
        f.write_text(html)
        return EurocontrolSDOSource(local_paths=[str(f)])

    def test_keeps_only_icao_in_bbox(self, tmp_path):
        src = self._make_source(tmp_path)
        wps = src._collect_waypoints()
        names = {w.name for w in wps}
        # In-scope ICAO: BILGO (FR), VESAN (FR), AAALL (US), OCEAN (mid-Atlantic, in EU box)
        assert "BILGO" in names
        assert "VESAN" in names
        assert "AAALL" in names
        # Out: FAREAST (Japan, no box), OTHER/ADHP/COORD types, NOFIX (bad coords)
        assert "FAREAST" not in names
        assert "001AB" not in names
        assert "15NAT" not in names
        assert "00E50" not in names
        assert "NOFIX" not in names

    def test_waypoint_fields(self, tmp_path):
        src = self._make_source(tmp_path)
        wps = src._collect_waypoints()
        by_name = {w.name: w for w in wps}

        bilgo = by_name["BILGO"]
        assert bilgo.point_type == "5LNC"
        assert bilgo.source == "eurocontrol_sdo"
        assert bilgo.source_id == "eurocontrol_sdo:EUROCONTROL_NMOC"
        assert bilgo.latitude_deg == pytest.approx(49.9019, abs=1e-3)

    def test_originator_included_in_source_id(self, tmp_path):
        src = self._make_source(tmp_path)
        wps = src._collect_waypoints()
        by_name = {w.name: w for w in wps}
        assert by_name["AAALL"].source_id == "eurocontrol_sdo:FAA_LOADER_EAD_SP"

    def test_missing_file_warns_but_does_not_crash(self, tmp_path):
        src = EurocontrolSDOSource(local_paths=[str(tmp_path / "missing.html")])
        wps = src._collect_waypoints()
        assert wps == []

    def test_dedup_across_files(self, tmp_path):
        # Same fix appearing in two files (e.g. NE and NW exports of an
        # oceanic waypoint) should only land once.
        f1 = tmp_path / "ne.html"
        f2 = tmp_path / "nw.html"
        for f in (f1, f2):
            f.write_text(SAMPLE_HTML)
        src = EurocontrolSDOSource(local_paths=[str(f1), str(f2)])
        wps = src._collect_waypoints()
        names = [w.name for w in wps]
        # BILGO only once even though it's in both files
        assert names.count("BILGO") == 1

    def test_custom_bbox_changes_filter(self, tmp_path):
        # If we expand the bbox to include Japan, FAREAST should pass
        f = tmp_path / "sample.html"
        f.write_text(SAMPLE_HTML)
        src = EurocontrolSDOSource(
            local_paths=[str(f)],
            bboxes=[(0.0, 90.0, 100.0, 180.0)],  # Asia/Pacific only
        )
        names = {w.name for w in src._collect_waypoints()}
        assert "FAREAST" in names
        # And the Europe ones should now be excluded
        assert "BILGO" not in names

    def test_custom_types_includes_adhp(self, tmp_path):
        f = tmp_path / "sample.html"
        f.write_text(SAMPLE_HTML)
        # 15NAT is an ADHP at 32.53°N, 34.78°E — inside the EU bbox
        src = EurocontrolSDOSource(
            local_paths=[str(f)],
            types=("ICAO", "ADHP"),
        )
        names = {w.name for w in src._collect_waypoints()}
        assert "15NAT" in names
