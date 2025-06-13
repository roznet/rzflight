import pytest
from pathlib import Path
from euro_aip.parsers import AIPParserFactory
from tests.assets.expected_results import EXPECTED_RESULTS
import logging

logger = logging.getLogger(__name__)

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

def test_aip_parser_parse_airports(test_pdfs):
    """Test that the AIP parser can parse all test PDF files."""
    assert test_pdfs, "No test PDF files found"
    skip_list = ['ESMS']
    debug_list = ['LFAT']
    
    for pdf_file in test_pdfs.values():
        # Extract ICAO from filename (documents_ICAO.pdf)
        icao = pdf_file.stem.split('_')[1]
        authority = get_authority_from_icao(icao)
        if icao in skip_list:
            logger.info(f"Skipping {icao}")
            continue
        # Create parser for the specific authority
        parser = AIPParserFactory.get_parser(authority)
        
        # Read PDF file as bytes
        pdf_data = pdf_file.read_bytes()
        
        # Parse the file
        if icao in debug_list:
            logger.info(f"Parsing {icao}")
        result = parser.parse(pdf_data, icao)
        
        # Basic validation of the result
        assert result is not None, f"Parser returned None for {icao}"
        assert isinstance(result, list), f"Result is not a list for {icao}"
        assert len(result) > 0, f"Empty result for {icao}"
        if icao in debug_list:
            AIPParserFactory.pretty_print_results(result)
            
        # If we have expected results for this airport, validate them
        if icao in EXPECTED_RESULTS:
            expected = EXPECTED_RESULTS[icao]
            
            # Check number of items
            if 'count' in expected:
                assert len(result) >= expected['count'], \
                    f"Expected {expected['count']} items for {icao}, got {len(result)}"
            
            # Check for specific fields

        found = {'Customs': False, 'Fuel Types': False}
        for item in result:
            if 'customs' in item['field'].lower():
                found['Customs'] = True
            if 'fuel types' in item['field'].lower():
                found['Fuel Types'] = True

        assert found['Customs'], f"Customs field not found for {icao}"
        assert found['Fuel Types'], f"Fuel Types field not found for {icao}"
