import pytest

from euro_aip.sources.norway_eaip_web import NorwayEAIPWebSource


HISTORY_HTML = """
<html><body>
<div class="history_pane">
  <h2>Gjeldende utgave</h2>
  <table><tbody><tr>
    <td><a href="2026-06-11-AIRAC/html/index-no-NO.html">11 JUN 2026</a></td>
  </tr></tbody></table>
  <h2>Neste utgave</h2>
  <table><tbody><tr>
    <td><a href="2026-07-09-AIRAC/html/index-no-NO.html">09 JUL 2026</a></td>
  </tr></tbody></table>
</div>
</body></html>
"""


def make_source(cache_dir, airac_date, available=('2026-06-11', '2026-07-09')):
    """Source with publication discovery pre-seeded, so no network is touched."""
    source = NorwayEAIPWebSource(str(cache_dir), airac_date)
    source._base_url = 'https://aim-prod.avinor.no/no/AIP/View/Index/154'
    source._available_airac_dates = list(available)
    return source


def test_parse_available_airac_dates(test_cache_dir):
    source = make_source(test_cache_dir, '2026-06-11')
    assert source._parse_available_airac_dates(HISTORY_HTML) == ['2026-06-11', '2026-07-09']


def test_requested_edition_used_when_served(test_cache_dir):
    source = make_source(test_cache_dir, '2026-07-09')
    assert source.effective_airac_date == '2026-07-09'


def test_falls_back_to_latest_served_when_not_yet_published(test_cache_dir):
    """Avinor lags the calendar: 2026-08-06 requested, only older editions served."""
    source = make_source(test_cache_dir, '2026-08-06', available=('2026-06-11',))
    assert source.effective_airac_date == '2026-06-11'


def test_falls_back_to_newest_edition_at_or_before_request(test_cache_dir):
    source = make_source(test_cache_dir, '2026-08-06')
    assert source.effective_airac_date == '2026-07-09'


def test_falls_back_forwards_when_requested_edition_retired(test_cache_dir):
    """Requested cycle already superseded, so only newer editions remain."""
    source = make_source(test_cache_dir, '2026-05-14')
    assert source.effective_airac_date == '2026-06-11'


def test_assumes_requested_when_no_editions_listed(test_cache_dir):
    source = make_source(test_cache_dir, '2026-08-06', available=())
    assert source.effective_airac_date == '2026-08-06'


def test_urls_and_cache_keys_use_effective_edition(test_cache_dir):
    source = make_source(test_cache_dir, '2026-08-06', available=('2026-06-11',))

    assert source._get_airport_url('ENZV') == (
        'https://aim-prod.avinor.no/no/AIP/View/Index/154/'
        '2026-06-11-AIRAC/html/eAIP/EN-AD-2.ENZV-en-GB.html'
    )
    assert source._get_cache_key('airport', 'ENZV') == '2026-06-11_airport_ENZV.html'
    assert source._get_cache_key('index') == '2026-06-11_index.html'


def test_index_url_pattern_extracts_publication_base():
    m = NorwayEAIPWebSource.INDEX_URL_PATTERN.match(
        'https://aim-prod.avinor.no/no/AIP/View/Index/154/history-no-NO.html'
    )
    assert m.group('base') == 'https://aim-prod.avinor.no/no/AIP/View/Index/154'


def test_invalid_airac_date_rejected(test_cache_dir):
    with pytest.raises(ValueError):
        NorwayEAIPWebSource(str(test_cache_dir), '11-06-2026')
