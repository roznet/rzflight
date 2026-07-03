"""Tests for country border-area membership and crossing-requirements helpers."""

import pytest

from euro_aip.borders import (
    EU_CUSTOMS_UNION,
    SCHENGEN,
    CrossingRequirements,
    crossing_requirements,
    is_eu_customs_union,
    is_known,
    is_schengen,
)
from euro_aip.models.airport import Airport


class TestMembershipPredicates:
    def test_schengen_and_customs_core_member(self):
        # France is in both blocs.
        assert is_schengen("FR")
        assert is_eu_customs_union("FR")

    def test_schengen_not_customs(self):
        # Switzerland: Schengen but outside the EU customs union.
        assert is_schengen("CH")
        assert not is_eu_customs_union("CH")

    def test_customs_not_schengen(self):
        # Ireland and Cyprus: EU customs union but outside Schengen.
        assert is_eu_customs_union("IE")
        assert not is_schengen("IE")
        assert is_eu_customs_union("CY")
        assert not is_schengen("CY")

    def test_case_insensitive(self):
        assert is_schengen("fr")
        assert is_schengen(" De ")
        assert is_eu_customs_union("ie")

    def test_unknown_and_empty(self):
        assert not is_schengen("XX")
        assert not is_eu_customs_union("XX")
        assert not is_schengen("")
        assert not is_schengen(None)

    def test_is_known(self):
        assert is_known("FR")
        assert is_known("IE")  # customs-only is still "known"
        assert is_known("CH")  # schengen-only is still "known"
        assert not is_known("GB")
        assert not is_known("XX")
        assert not is_known(None)

    def test_reference_tables_edge_membership(self):
        # Guard rails against accidental table drift on the tricky members.
        assert {"CH", "NO", "IS", "LI"} <= SCHENGEN
        assert not ({"CH", "NO", "IS", "LI"} & EU_CUSTOMS_UNION)
        assert {"CY", "IE"} <= EU_CUSTOMS_UNION
        assert not ({"CY", "IE"} & SCHENGEN)


class TestCrossingRequirements:
    # Acceptance criteria rows from the issue.

    def test_fr_gb_immigration_and_customs(self):
        req = crossing_requirements("FR", "GB")
        assert req.immigration_required is True
        assert req.customs_required is True
        assert req.from_known is True
        assert req.to_known is False  # GB is in neither table

    def test_fr_ch_customs_only(self):
        req = crossing_requirements("FR", "CH")
        assert req.immigration_required is False
        assert req.customs_required is True
        assert req.from_known is True
        assert req.to_known is True

    def test_fr_ie_immigration_only(self):
        req = crossing_requirements("FR", "IE")
        assert req.immigration_required is True
        assert req.customs_required is False
        assert req.from_known is True
        assert req.to_known is True

    def test_fr_de_no_formalities(self):
        req = crossing_requirements("FR", "DE")
        assert req.immigration_required is False
        assert req.customs_required is False
        assert req.from_known is True
        assert req.to_known is True

    def test_fr_unknown_to_not_known(self):
        req = crossing_requirements("FR", "XX")
        assert req.to_known is False
        assert req.from_known is True
        # Unknown destination is treated as outside every bloc -> both flags set.
        assert req.immigration_required is True
        assert req.customs_required is True

    def test_same_country_no_border(self):
        req = crossing_requirements("FR", "FR")
        assert req.immigration_required is False
        assert req.customs_required is False
        assert req.from_known is True
        assert req.to_known is True

    def test_same_unknown_country_no_border(self):
        # Identical codes mean a domestic flight, even for an unknown country.
        req = crossing_requirements("GB", "GB")
        assert req.immigration_required is False
        assert req.customs_required is False
        assert req.from_known is False
        assert req.to_known is False

    def test_case_insensitive_pair(self):
        assert crossing_requirements("fr", "de") == crossing_requirements("FR", "DE")

    def test_is_dataclass_instance(self):
        assert isinstance(crossing_requirements("FR", "DE"), CrossingRequirements)

    def test_channel_islands_vs_eu(self):
        # Jersey is outside both blocs -> customs + immigration vs France.
        req = crossing_requirements("JE", "FR")
        assert req.immigration_required is True
        assert req.customs_required is True
        assert req.from_known is False


class TestAirportConvenienceProperties:
    def test_schengen_customs_country(self):
        airport = Airport(ident="LFPG", iso_country="FR")
        assert airport.is_schengen is True
        assert airport.is_eu_customs_union is True

    def test_schengen_only_country(self):
        airport = Airport(ident="LSGG", iso_country="CH")
        assert airport.is_schengen is True
        assert airport.is_eu_customs_union is False

    def test_customs_only_country(self):
        airport = Airport(ident="EIDW", iso_country="IE")
        assert airport.is_schengen is False
        assert airport.is_eu_customs_union is True

    def test_unknown_country_is_none(self):
        airport = Airport(ident="EGLL", iso_country="GB")
        assert airport.is_schengen is None
        assert airport.is_eu_customs_union is None

    def test_missing_country_is_none(self):
        airport = Airport(ident="ZZZZ", iso_country=None)
        assert airport.is_schengen is None
        assert airport.is_eu_customs_union is None
