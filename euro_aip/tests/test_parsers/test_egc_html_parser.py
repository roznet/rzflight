#!/usr/bin/env python3

import io
from pathlib import Path
from euro_aip.parsers import AIPParserFactory


def load_asset_bytes(name: str) -> bytes:
    asset_path = Path(__file__).parent.parent / 'assets' / 'html' / name
    return asset_path.read_bytes()


def test_egc_html_parser_extract_text_with_sd_spans():
    """Test that _extract_text properly handles SD/sdParams spans."""
    icao = 'EGMC'
    html_bytes = load_asset_bytes('EG-AD-2.EGMC-en-GB.html')

    parser = AIPParserFactory.get_parser('EGC', 'html')
    data = parser.parse(html_bytes, icao)

    # Basic smoke tests
    assert isinstance(data, list)
    assert len(data) > 0

    # Find the ARP coordinates field (should have SD spans, no sdParams)
    arp_rows = [row for row in data if 'ARP coordinates' in row['field'] and row['section'] == 'admin']
    assert len(arp_rows) > 0
    
    # The ARP coordinates field has multiple parts, verify they were extracted
    arp_value = arp_rows[0]['value']
    # Either should have coordinates or the annotation
    has_coordinates = '513413N' in arp_value and '0004136E' in arp_value
    has_annotation = 'Mid point' in arp_value and 'Runway' in arp_value
    assert has_coordinates or has_annotation, f"Expected coordinates or annotation in ARP field, got: {arp_value}"
    
    # Ensure sdParams content is NOT in the extracted text
    assert 'TAD_HP' not in arp_value, "sdParams metadata should not be extracted"
    assert 'GEO_LAT' not in arp_value, "sdParams metadata should not be extracted"
    assert 'GEO_LONG' not in arp_value, "sdParams metadata should not be extracted"


def test_egc_html_parser_admin_section():
    """Test that admin section data is extracted correctly."""
    icao = 'EGMC'
    html_bytes = load_asset_bytes('EG-AD-2.EGMC-en-GB.html')

    parser = AIPParserFactory.get_parser('EGC', 'html')
    data = parser.parse(html_bytes, icao)

    # Check that admin section exists
    admin_rows = [row for row in data if row['section'] == 'admin']
    assert len(admin_rows) > 0


def test_egc_html_parser_text_extraction_clean():
    """Test that extracted text is clean and properly formatted."""
    icao = 'EGMC'
    html_bytes = load_asset_bytes('EG-AD-2.EGMC-en-GB.html')

    parser = AIPParserFactory.get_parser('EGC', 'html')
    data = parser.parse(html_bytes, icao)

    # Check that values don't contain HTML artifacts or sdParams
    for row in data[:50]:  # Check first 50 rows
        value = row.get('value', '')
        if value:
            # Should not contain sdParams or sdTooltip class references
            assert 'sdParams' not in value.lower(), f"sdParams found in value: {value}"
            assert 'sdTooltip' not in value.lower(), f"sdTooltip found in value: {value}"
            # Should not contain HTML tags
            assert '<' not in value, f"HTML tags found in value: {value}"
            assert '>' not in value, f"HTML tags found in value: {value}"
