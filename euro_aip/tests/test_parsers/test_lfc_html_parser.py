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
    fuels = [row for row in data if row['section'] == 'handling' and 'fuel' in row['field'].lower()]
    assert len(fuels) >= 1
    # Ensure values contain the expected fuel types
    found = any(('100LL' in (row['value'] or '') or 'JET A1' in (row['value'] or '')) for row in fuels)
    assert found, 'Expected 100LL or JET A1 in fuel types'

    # Check that at least one admin section entry exists (AD 2.2)
    admin_rows = [row for row in data if row['section'] == 'admin']
    assert len(admin_rows) > 0


def test_lfc_html_extract_procedures():
    icao = 'LFAQ'
    html_bytes = load_asset_bytes('FR-AD-2.LFAQ-fr-FR.html')

    parser = AIPParserFactory.get_parser('LFC', 'html')
    procs = parser.extract_procedures(html_bytes, icao)

    # Expect at least one approach-related chart parsed
    assert isinstance(procs, list)
    assert len(procs) > 0

    # Expect specific basenames present in sample
    names = [p.get('name', '') for p in procs]
    expected_any = ['RWY08 RNP', 'RWY26 FNA RNP']
    assert any(exp in names for exp in expected_any), f"Expected one of {expected_any} in parsed names, got: {names}"


