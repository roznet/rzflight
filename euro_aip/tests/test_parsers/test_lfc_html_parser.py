#!/usr/bin/env python3

import io
from pathlib import Path

from euro_aip.parsers import AIPParserFactory


def load_asset_bytes(name: str) -> bytes:
    asset_path = Path(__file__).parent.parent / 'assets' / 'html' / name
    return asset_path.read_bytes()


def test_lfc_html_parser_basic_extraction():
    icao = 'LFAQ'
    html_bytes = load_asset_bytes('FR-AD-2.LFAQ-fr-FR.html')

    parser = AIPParserFactory.get_parser('LFC', 'html')
    data = parser.parse(html_bytes, icao)

    # Basic smoke tests
    assert isinstance(data, list)
    assert len(data) > 0

    # Find a known field/value pair from section AD 2.4 (handling)
    # Field (FR): "Types de carburants et lubrifiants" should map to handling section
    fuels = [row for row in data if row['section'] == 'handling' and 'carburants' in row['field'].lower()]
    assert len(fuels) >= 1
    # Ensure values contain the expected fuel types
    found = any(('100LL' in (row['value'] or '') or 'JET A1' in (row['value'] or '')) for row in fuels)
    assert found, 'Expected 100LL or JET A1 in fuel types'

    # Check that at least one admin section entry exists (AD 2.2)
    admin_rows = [row for row in data if row['section'] == 'admin']
    assert len(admin_rows) > 0


