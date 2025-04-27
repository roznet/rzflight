import pytest
from pathlib import Path
from euro_aip.parsers import AIPParserFactory
from tests.assets.expected_results import EXPECTED_RESULTS

def get_authority_from_icao(icao: str) -> str:
    """
    Determine the authority code from an ICAO code.
    
    Args:
        icao: ICAO airport code
        
    Returns:
        Authority code (e.g., 'LEC' for European airports)
    """
    # First letter of ICAO code indicates the region
    region = icao[0].upper()
    
    # Special case for European airports
    if region in ['L', 'E']:
        # Get first two letters
        prefix = icao[:2].upper()
        
        # Exception list for European airports
        exceptions = {
            'ET': 'EDC'  # German military airports
        }
        
        # Return exception if exists, otherwise use prefix + 'C'
        return exceptions.get(prefix, f"{prefix}C")
    
    # Map other regions to authorities
    region_to_authority = {
        'K': 'FAA',  # Federal Aviation Administration
        # Add more mappings as needed
    }
    
    return region_to_authority.get(region, 'DEFAULT')

def test_aip_parser_parse_files(test_pdfs):
    """Test that the AIP parser can parse all test PDF files."""
    assert test_pdfs, "No test PDF files found"
    
    for pdf_file in test_pdfs.values():
        # Extract ICAO from filename (documents_ICAO.pdf)
        icao = pdf_file.stem.split('_')[1]
        authority = get_authority_from_icao(icao)
        
        # Create parser for the specific authority
        parser = AIPParserFactory.get_parser(authority)
        
        # Read PDF file as bytes
        pdf_data = pdf_file.read_bytes()
        
        # Parse the file
        result = parser.parse(pdf_data, icao)
        
        # Basic validation of the result
        assert result is not None, f"Parser returned None for {icao}"
        assert isinstance(result, list), f"Result is not a list for {icao}"
        assert len(result) > 0, f"Empty result for {icao}"
        
        # If we have expected results for this airport, validate them
        if icao in EXPECTED_RESULTS:
            expected = EXPECTED_RESULTS[icao]
            
            # Check number of items
            if 'count' in expected:
                assert len(result) == expected['count'], \
                    f"Expected {expected['count']} items for {icao}, got {len(result)}"
            
            # Check for specific sections
            if 'sections' in expected:
                for section_name, count in expected['sections'].items():
                    actual_count = sum(1 for item in result if item.get('section') == section_name)
                    assert actual_count == count, \
                        f"Expected {count} items in section '{section_name}' for {icao}, got {actual_count}"
            
            # Check for specific items
            if 'items' in expected:
                for expected_item in expected['items']:
                    assert any(
                        all(item.get(k) == v for k, v in expected_item.items())
                        for item in result
                    ), f"Expected item not found in {icao}: {expected_item}"

def test_aip_parser_specific_airport(test_pdfs):
    """Test specific aspects of parsing for each airport type."""
    for pdf_file in test_pdfs.values():
        icao = pdf_file.stem.split('_')[1]
        authority = get_authority_from_icao(icao)
        
        parser = AIPParserFactory.get_parser(authority)
        pdf_data = pdf_file.read_bytes()
        result = parser.parse(pdf_data, icao)
        
        # Count items per section
        section_counts = {}
        section_items = {}  # Store items by section for detailed output
        for item in result:
            section = item.get('section', 'unknown')
            section_counts[section] = section_counts.get(section, 0) + 1
            if section not in section_items:
                section_items[section] = []
            section_items[section].append(item)
        
        # Print summary for debugging
        print(f"\nParsing summary for {icao}:")
        for section, count in section_counts.items():
            print(f"  {section}: {count} fields")
        
        # Test that all items have required fields
        for item in result:
            assert 'ident' in item, f"Item missing 'ident' field in {icao}"
            assert 'section' in item, f"Item missing 'section' field in {icao}"
            assert 'field' in item, f"Item missing 'field' field in {icao}"
            assert 'value' in item, f"Item missing 'value' field in {icao}"
        
        # Validate section counts against expected results if available
        if icao in EXPECTED_RESULTS and 'sections' in EXPECTED_RESULTS[icao]:
            expected_sections = EXPECTED_RESULTS[icao]['sections']
            for section, expected_count in expected_sections.items():
                actual_count = section_counts.get(section, 0)
                if actual_count != expected_count:
                    print(f"\nMismatch in {section} section for {icao}:")
                    print(f"Expected {expected_count} items, got {actual_count}")
                    print("\nActual items in section:")
                    for item in section_items.get(section, []):
                        print(f"  - {item['field']}: {item['value']}")
                assert actual_count == expected_count, \
                    f"Expected {expected_count} items in section '{section}' for {icao}, got {actual_count}"
        
        # Ensure we have at least one admin section
        assert 'admin' in section_counts, f"No admin section found for {icao}"
        assert section_counts['admin'] > 0, f"Empty admin section for {icao}" 