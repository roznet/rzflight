"""
Tests for best-effort military aerodrome classification.

Real ICAO codes and real OurAirports names are used throughout: the classifier
is a set of empirical rules about published naming, so synthetic inputs would
not exercise what actually breaks.
"""

import pytest

from euro_aip.models.airport import Airport
from euro_aip.utils.military_aerodromes import (
    FORMER_MILITARY,
    KNOWN_CIVIL_ICAOS,
    KNOWN_MILITARY_ICAOS,
)
from euro_aip.utils.military_classifier import MilitaryClassifier


@pytest.fixture
def classifier():
    return MilitaryClassifier()


class TestIcaoPrefixRules:
    """German ET prefix and UK EG third-letter conventions."""

    @pytest.mark.parametrize('ident,name', [
        ('ETAR', 'Ramstein Air Base'),
        ('ETAD', 'Spangdahlem Air Base'),
        # The point of the prefix rule: these names give nothing away.
        ('ETHM', 'Mendig Airfield'),
        ('ETHR', 'Roth Airfield'),
        ('ETNL', 'Rostock-Laage Airport'),
        ('ETSI', 'Ingolstadt Manching Airport'),
        ('ETIN', 'Kitzingen Airfield'),
    ])
    def test_german_et_prefix(self, classifier, ident, name):
        assert classifier.is_military(ident, name) is True

    @pytest.mark.parametrize('ident,name', [
        ('EDDF', 'Frankfurt Main Airport'),
        ('EDDM', 'Munich Airport'),
        ('EDLW', 'Dortmund Airport'),
    ])
    def test_german_ed_prefix_is_civil(self, classifier, ident, name):
        assert classifier.is_military(ident, name) is False

    @pytest.mark.parametrize('ident,name', [
        ('EGVN', 'RAF Brize Norton'),
        ('EGDR', 'RNAS Culdrose'),
        ('EGQS', 'RAF Lossiemouth'),
        ('EGUW', 'Wattisham Airfield'),      # name-neutral
        ('EGOV', 'Anglesey Airport'),        # RAF Valley, joint use
        ('EGDN', 'Netheravon Airfield'),     # name-neutral
    ])
    def test_uk_military_third_letter(self, classifier, ident, name):
        assert classifier.is_military(ident, name) is True

    @pytest.mark.parametrize('ident,name', [
        ('EGLL', 'London Heathrow Airport'),
        ('EGKK', 'London Gatwick Airport'),
        ('EGTF', 'Fairoaks Airport'),
        ('EGBJ', 'Gloucestershire Airport'),
    ])
    def test_uk_civil_third_letter(self, classifier, ident, name):
        assert classifier.is_military(ident, name) is False

    def test_prefix_rule_reports_itself(self, classifier):
        result = classifier.classify('ETAR', 'Ramstein Air Base')
        assert result.rule == 'icao_prefix'
        assert result.detail == 'ET'

    def test_ident_is_case_insensitive(self, classifier):
        assert classifier.is_military('etar', 'Ramstein Air Base') is True

    @pytest.mark.parametrize('ident,name', [
        # Non-ICAO local codes that happen to share a military prefix. Sweeping
        # these up is the failure mode the isalpha() guard exists to prevent.
        ('ETT1', 'Etting-Adelmannsberg Glider Field'),
        ('EG74', 'Bruntingthorpe Aerodrome'),
    ])
    def test_local_codes_are_not_swept_up(self, classifier, ident, name):
        assert classifier.is_military(ident, name) is False


class TestNamesAreNotMatchedAtRuntime:
    """
    Aerodrome names generate candidates in the offline review tool, but never
    decide at runtime. A published name is not revoked when a base closes, so
    matching it would flag decommissioned fields forever.
    """

    @pytest.mark.parametrize('ident,name', [
        ('LIPA', 'Aviano Air Base'),
        ('LSZG', 'Militärflugplatz Grenchen'),
        ('EKKA', 'Midtjyllands Airport / Air Base Karup'),
        ('LSMP', 'Payerne Air Base'),
        ('ESCF', 'Malmen Air Base'),
    ])
    def test_military_names_alone_do_not_flag(self, classifier, ident, name):
        """Real military fields, not yet curated — only the list may say so."""
        assert ident not in KNOWN_MILITARY_ICAOS, (
            f'{ident} has since been promoted into the curated list, so it no '
            f'longer tests the name rule. Swap in an aerodrome from the '
            f'INCONCLUSIVE bucket of the review artifact.'
        )
        result = classifier.classify(ident, name)
        assert result.is_military is False
        assert result.rule == 'none'

    def test_name_argument_is_accepted_and_ignored(self, classifier):
        """The parameter stays for caller convenience but changes nothing."""
        assert classifier.classify('LFPG', 'Somewhere Air Base').is_military is False
        assert classifier.classify('ETAR').is_military is True
        assert classifier.classify('ETAR', 'Totally Civil Airport').is_military is True

    def test_no_name_pattern_rule_remains(self, classifier):
        """Guard against the runtime name rule being reintroduced."""
        for ident, name in [('LIPA', 'Aviano Air Base'),
                            ('EKKA', 'Midtjyllands Airport / Air Base Karup')]:
            assert classifier.classify(ident, name).rule != 'name_pattern'


class TestKeywordsAreIgnored:
    """
    The OurAirports keywords column is worse than names: it retains wartime
    identities. These are all civil GA fields today.
    """

    @pytest.mark.parametrize('ident,name', [
        ('EGSU', 'Duxford Aerodrome'),                # keywords: RAF Duxford
        ('EDDF', 'Frankfurt Main Airport'),           # keywords: Rhein-Main Air Base
        ('EGHI', 'Southampton Airport'),              # keywords: RAF Eastleigh
        ('EGTB', 'Wycombe Air Park'),                 # keywords: RAF Booker
        ('EGNX', 'East Midlands Airport'),            # keywords: RAF Castle Donington
        ('EPRA', 'Warsaw Radom Airport'),             # keywords: Radom Military Air Base
        ('LSZM', 'Mollis Airfield'),                  # keywords: Militärflugplatz Mollis
        ('ESTA', 'Ängelholm-Helsingborg Airport'),    # keywords: Ängelholm Air Base
    ])
    def test_historical_military_keywords_do_not_leak(self, classifier, ident, name):
        assert classifier.is_military(ident, name) is False

    def test_classifier_signature_has_no_keywords_parameter(self, classifier):
        """Guard against someone helpfully wiring keywords back in."""
        import inspect
        params = inspect.signature(classifier.classify).parameters
        assert 'keywords' not in params


class TestOverrides:
    """Curated list, and its precedence over the rules."""

    @pytest.mark.parametrize('ident,name', [
        ('EKYT', 'Aalborg Airport'),
        ('EFRO', 'Rovaniemi Airport'),
        ('LKPD', 'Pardubice Airport'),
        ('LEZG', 'Zaragoza Airport'),
        ('ENOL', 'Ørland Airport'),
        ('EYSA', 'Šiauliai International Airport'),
        ('LRTR', 'Timișoara Traian Vuia International  Airport'),
        ('LGTS', 'Thessaloniki Macedonia International Airport'),
    ])
    def test_joint_use_needs_the_curated_list(self, classifier, ident, name):
        result = classifier.classify(ident, name)
        assert result.is_military is True
        assert result.rule == 'override_military'

    def test_civil_override_beats_prefix_rule(self, classifier):
        """EGXG matches the UK military third-letter set but is civil since 2014."""
        result = classifier.classify('EGXG', 'Leeds East Airport')
        assert result.is_military is False
        assert result.rule == 'override_civil'

    def test_civil_override_beats_military_override(self):
        classifier = MilitaryClassifier(extra_military={'XXXX': 'm'},
                                        extra_civil={'XXXX': 'c'})
        assert classifier.classify('XXXX').is_military is False

    def test_former_military_records_rejected_reviews(self):
        """Decommissioned bases stay listed so a future review re-rejects them."""
        for icao in ('EBSU', 'EBUL', 'EBWE', 'EBBX', 'EBSL', 'LSGR', 'LSML'):
            assert icao in FORMER_MILITARY

    def test_extra_military_is_merged(self):
        classifier = MilitaryClassifier(extra_military={'LFAT': 'test only'})
        assert classifier.is_military('LFAT', 'Le Touquet Airport') is True
        # built-ins survive the merge
        assert classifier.is_military('EKYT', 'Aalborg Airport') is True

    def test_builtin_lists_do_not_contradict(self):
        assert not (set(KNOWN_MILITARY_ICAOS) & set(KNOWN_CIVIL_ICAOS))

    def test_override_entries_are_documented(self):
        for icao, reason in {**KNOWN_MILITARY_ICAOS, **KNOWN_CIVIL_ICAOS}.items():
            assert len(icao) == 4, f'{icao} is not a 4-letter ICAO code'
            assert reason, f'{icao} has no reason recorded'


class TestAirportAnnotation:
    """Writing the verdict onto the Airport model."""

    def test_annotate_sets_the_flag(self, classifier):
        airport = Airport(ident='ETAR', name='Ramstein Air Base')
        assert airport.military is None
        result = classifier.annotate(airport)
        assert airport.military is True
        assert result.rule == 'icao_prefix'

    def test_annotate_sets_false_when_nothing_matches(self, classifier):
        airport = Airport(ident='LFPG', name='Charles de Gaulle')
        classifier.annotate(airport)
        assert airport.military is False

    def test_classify_airport_does_not_mutate(self, classifier):
        airport = Airport(ident='ETAR', name='Ramstein Air Base')
        assert classifier.classify_airport(airport).is_military is True
        assert airport.military is None

    def test_annotate_all_returns_breakdown(self, classifier):
        airports = [
            Airport(ident='ETAR', name='Ramstein Air Base'),      # prefix
            Airport(ident='EGVN', name='RAF Brize Norton'),       # prefix
            Airport(ident='EKYT', name='Aalborg Airport'),        # override
            Airport(ident='LIPA', name='Aviano Air Base'),        # not curated yet
            Airport(ident='LFPG', name='Charles de Gaulle'),      # civil
        ]
        counts = classifier.annotate_all(airports)
        assert counts == {
            'icao_prefix': 2,
            'override_military': 1,
        }
        assert [a.military for a in airports] == [True, True, True, False, False]


class TestCollectionFilters:
    """AirportCollection.military() / .civil()."""

    def _collection(self):
        from euro_aip.models.airport_collection import AirportCollection
        return AirportCollection([
            Airport(ident='ETAR', name='Ramstein Air Base', military=True),
            Airport(ident='LFPG', name='Charles de Gaulle', military=False),
            Airport(ident='LFAT', name='Le Touquet'),  # never classified
        ])

    def test_military_filter(self):
        assert [a.ident for a in self._collection().military()] == ['ETAR']

    def test_civil_filter_keeps_unclassified(self):
        """None is 'unknown', not 'military' — dropping it would hide airports."""
        assert [a.ident for a in self._collection().civil()] == ['LFPG', 'LFAT']
