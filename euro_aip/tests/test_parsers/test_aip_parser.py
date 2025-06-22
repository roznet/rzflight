import pytest
from pathlib import Path
from euro_aip.parsers import AIPParserFactory
from tests.assets.expected_results import EXPECTED_RESULTS
import logging
from collections import defaultdict
from euro_aip.utils.field_mapper import FieldMapper

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
    skip_list = ['ESMS', 'EKAH']
    debug_list = []
    
    # Track field coverage across authorities
    field_coverage = defaultdict(lambda: defaultdict(dict))  # field_name -> authority -> defs
    authority_fields = defaultdict(set)  # authority -> set of field names
    authority_icao_mapping = {}  # authority -> list of ICAO codes
    field_mapper = FieldMapper()
    
    for pdf_file in test_pdfs.values():
        # Extract ICAO from filename (documents_ICAO.pdf)
        icao = pdf_file.stem.split('_')[1]
        if debug_list and icao not in debug_list:
            continue
        authority = get_authority_from_icao(icao)
        if icao in skip_list:
            logger.info(f"Skipping {icao}")
            continue
            
        # Track authority to ICAO mapping
        if authority not in authority_icao_mapping:
            authority_icao_mapping[authority] = []
        authority_icao_mapping[authority].append(icao)
        
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
            
        # Track field coverage
        for item in result:
            field_name = item.get('field', '')
            if field_name:
                field_coverage[field_name][authority] = item
                authority_fields[authority].add(field_name.strip())
            
        # If we have expected results for this airport, validate them
        if icao in EXPECTED_RESULTS:
            expected = EXPECTED_RESULTS[icao]
            
            # Check number of items
            if 'count' in expected:
                assert len(result) >= expected['count'], \
                    f"Expected {expected['count']} items for {icao}, got {len(result)}"
            

        standardised_result = field_mapper.standardise_fields(result)
        logger.info(f"Standardised result: {len(standardised_result)}/{len(result)}")
        # Check for specific fields
        found_results = {
            402: False, # Fuel Types
            302: False # Customs
        }
        for item in standardised_result:
            for field_id, found in found_results.items():
                if item['field_id'] == field_id:
                    found_results[field_id] = True
        for field_id, found in found_results.items():
            assert found, f"Field {field_id} {field_mapper.get_field_for_id(field_id)['field_name']} not found for {icao}"



    
    # Analyze and log field coverage
    analyze_field_coverage(field_coverage, authority_fields, authority_icao_mapping)
    json_mapping_stats = analyze_field_mapping(field_coverage)
    
    # Make the JSON mapping stats available for external use (e.g., saving to file)
    # You can access this in the debug console or save it to a file
    return json_mapping_stats

def analyze_field_coverage(field_coverage, authority_fields, authority_icao_mapping):
    """
    Analyze field coverage across authorities and log detailed statistics.
    
    Args:
        field_coverage: Dictionary mapping field names to set of authorities
        authority_fields: Dictionary mapping authorities to set of field names
        authority_icao_mapping: Dictionary mapping authorities to list of ICAO codes
    """
    logger.info("=" * 80)
    logger.info("FIELD COVERAGE ANALYSIS")
    logger.info("=" * 80)
    
    
    # Basic statistics
    total_fields = len(field_coverage)
    total_authorities = len(authority_fields)
    
    logger.info(f"Total unique fields found: {total_fields}")
    logger.info(f"Total authorities tested: {total_authorities}")
    
    # Authority statistics
    logger.info("\nAUTHORITY STATISTICS:")
    logger.info("-" * 40)
    for authority, fields in authority_fields.items():
        icao_codes = authority_icao_mapping.get(authority, [])
        logger.info(f"{authority}: {len(fields)} fields from {len(icao_codes)} airports ({icao_codes})")
    
    # Field coverage statistics
    logger.info("\nFIELD COVERAGE STATISTICS:")
    logger.info("-" * 40)
    
    # Group fields by coverage level
    coverage_levels = defaultdict(list)
    for field_name, authorities in field_coverage.items():
        coverage_count = len(authorities)
        coverage_levels[coverage_count].append(field_name)
    
    # Show fields by coverage level (most common first)
    for coverage_count in sorted(coverage_levels.keys(), reverse=True):
        fields = coverage_levels[coverage_count]
        percentage = (coverage_count / total_authorities) * 100
        logger.info(f"Fields found in {coverage_count}/{total_authorities} authorities ({percentage:.1f}%): {len(fields)} fields")
        
        # Show field names for high coverage fields
        if coverage_count >= total_authorities // 2:  # Show fields found in at least half of authorities
            for field_name in sorted(fields):
                authorities_list = sorted(field_coverage[field_name])
                logger.info(f"  - {field_name} ({authorities_list})")
    
    # Unique fields per authority
    logger.info("\nUNIQUE FIELDS PER AUTHORITY:")
    logger.info("-" * 40)
    for authority, fields in authority_fields.items():
        unique_fields = []
        for field_name in fields:
            if len(field_coverage[field_name]) == 1:  # Only found in this authority
                unique_fields.append(field_name)
        
        if unique_fields:
            logger.info(f"{authority} unique fields ({len(unique_fields)}):")
            for field_name in sorted(unique_fields):
                logger.info(f"  - {field_name}")
        else:
            logger.info(f"{authority}: No unique fields")
    
    # Most common fields
    logger.info("\nMOST COMMON FIELDS:")
    logger.info("-" * 40)
    sorted_fields = sorted(field_coverage.items(), key=lambda x: len(x[1]), reverse=True)
    for field_name, authorities in sorted_fields[:20]:  # Top 20
        coverage_count = len(authorities)
        percentage = (coverage_count / total_authorities) * 100
        authorities_list = sorted(authorities)
        logger.info(f"{field_name}: {coverage_count}/{total_authorities} ({percentage:.1f}%) - {authorities_list}")

def analyze_field_mapping(field_coverage):
    # FIELD MAPPING ANALYSIS
    logger.info("\nFIELD MAPPING ANALYSIS:")
    logger.info("-" * 40)
    
    # Initialize field mapper
    field_mapper = FieldMapper()

    # Track mapping statistics
    mapping_stats = {
        'total_fields': 0,
        'mapped_fields': set(),  # Set of field names that were mapped
        'unmapped_fields': set(),  # Set of field names that were not mapped
        'mapped_fields_by_authority': defaultdict(set),  # authority -> set of mapped field names
        'unmapped_fields_by_authority': defaultdict(set),  # authority -> set of unmapped field names
        'high_confidence_mappings': set(),  # Set of (field_name, mapped_to) tuples with score >= 0.8
        'medium_confidence_mappings': set(),  # Set of (field_name, mapped_to) tuples with score >= 0.6
        'low_confidence_mappings': set(),  # Set of (field_name, mapped_to) tuples with score < 0.6
        'mappings_by_section': defaultdict(lambda: {'mapped': set(), 'unmapped': set()}),
        'unmapped_fields_list': [],
        'low_confidence_mappings_list': []
    }
    
    # Analyze each field for mapping potential
    for field_name, authorities in field_coverage.items():
        mapping_stats['total_fields'] += 1
        
        # Get the first occurrence's section and field_aip_id for better mapping
        first_authority = next(iter(authorities))
        first_item = authorities[first_authority]
        section = first_item.get('section')
        field_aip_id = first_item.get('field_aip_id')
        field_aip_id = None
        
        # Try to map this field using the actual section and field_aip_id
        mapping = field_mapper.map_field(field_name, section, field_aip_id)
        
        if mapping['mapped']:
            mapping_stats['mapped_fields'].add((field_name,section))
            found_section = mapping['section']
            mapping_stats['mappings_by_section'][found_section]['mapped'].add(field_name)
            
            # Track which authorities have this mapped field
            for authority in authorities:
                mapping_stats['mapped_fields_by_authority'][authority].add((field_name,section))
            
            score = mapping['similarity_score']
            mapping_tuple = (field_name, mapping['mapped_field_name'], score, found_section)
            
            if score >= 0.8:
                mapping_stats['high_confidence_mappings'].add(mapping_tuple)
            elif score >= 0.6:
                mapping_stats['medium_confidence_mappings'].add(mapping_tuple)
            else:
                mapping_stats['low_confidence_mappings'].add(mapping_tuple)
                mapping_stats['low_confidence_mappings_list'].append({
                    'field': field_name,
                    'mapped_to': mapping['mapped_field_name'],
                    'score': score,
                    'section': found_section
                })
        else:
            mapping_stats['unmapped_fields'].add((field_name,section))
            mapping_stats['unmapped_fields_list'].append(field_name)
            # Track which authorities have this unmapped field
            for authority in authorities:
                mapping_stats['unmapped_fields_by_authority'][authority].add(field_name)
    
    # Convert mapping_stats to JSON serializable format
    json_mapping_stats = convert_mapping_stats_to_json(mapping_stats)
    
    # Log mapping statistics
    logger.info(f"Total fields analyzed: {mapping_stats['total_fields']}")
    logger.info(f"Mapped fields: {len(mapping_stats['mapped_fields'])} ({len(mapping_stats['mapped_fields'])/mapping_stats['total_fields']*100:.1f}%)")
    logger.info(f"Unmapped fields: {len(mapping_stats['unmapped_fields'])} ({len(mapping_stats['unmapped_fields'])/mapping_stats['total_fields']*100:.1f}%)")
    logger.info(f"High confidence mappings (≥0.8): {len(mapping_stats['high_confidence_mappings'])}")
    logger.info(f"Medium confidence mappings (≥0.6): {len(mapping_stats['medium_confidence_mappings'])}")
    logger.info(f"Low confidence mappings (<0.6): {len(mapping_stats['low_confidence_mappings'])}")
    
    # Mapping by section
    logger.info("\nMAPPING BY SECTION:")
    for section, stats in mapping_stats['mappings_by_section'].items():
        total_section = len(stats['mapped']) + len(stats['unmapped'])
        if total_section > 0:
            percentage = (len(stats['mapped']) / total_section) * 100
            logger.info(f"{section}: {len(stats['mapped'])}/{total_section} mapped ({percentage:.1f}%)")
    
    # Show mapped fields by authority
    logger.info("\nMAPPED FIELDS BY AUTHORITY:")
    for authority in sorted(mapping_stats['mapped_fields_by_authority'].keys()):
        mapped_fields = mapping_stats['mapped_fields_by_authority'][authority]
        if mapped_fields:
            logger.info(f"{authority}: {len(mapped_fields)} mapped fields")
            # Show first few mapped fields for each authority
            for field_name in sorted(list(mapped_fields))[:5]:
                logger.info(f"  - {field_name}")
            if len(mapped_fields) > 5:
                logger.info(f"  ... and {len(mapped_fields) - 5} more")
    
    # Show unmapped fields by authority
    logger.info("\nUNMAPPED FIELDS BY AUTHORITY:")
    for authority in sorted(mapping_stats['unmapped_fields_by_authority'].keys()):
        unmapped_fields = mapping_stats['unmapped_fields_by_authority'][authority]
        if unmapped_fields:
            logger.info(f"{authority}: {len(unmapped_fields)} unmapped fields")
            # Show first few unmapped fields for each authority
            for field_name in sorted(list(unmapped_fields))[:5]:
                logger.info(f"  - {field_name}")
            if len(unmapped_fields) > 5:
                logger.info(f"  ... and {len(unmapped_fields) - 5} more")
    
    # Show some unmapped fields for analysis
    if mapping_stats['unmapped_fields']:
        logger.info(f"\nSAMPLE UNMAPPED FIELDS ({min(10, len(mapping_stats['unmapped_fields']))} of {len(mapping_stats['unmapped_fields'])}):")
        for field_name in sorted(list(mapping_stats['unmapped_fields']))[:10]:
            logger.info(f"  - {field_name}")
    
    # Show high confidence mappings
    if mapping_stats['high_confidence_mappings']:
        logger.info(f"\nHIGH CONFIDENCE MAPPINGS ({min(10, len(mapping_stats['high_confidence_mappings']))} of {len(mapping_stats['high_confidence_mappings'])}):")
        for mapping_tuple in sorted(mapping_stats['high_confidence_mappings'], key=lambda x: x[2], reverse=True)[:10]:
            field_name, mapped_to, score, section = mapping_tuple
            logger.info(f"  - '{field_name}' -> '{mapped_to}' (score: {score:.2f}, section: {section})")
    
    # Show medium confidence mappings
    if mapping_stats['medium_confidence_mappings']:
        logger.info(f"\nMEDIUM CONFIDENCE MAPPINGS ({min(10, len(mapping_stats['medium_confidence_mappings']))} of {len(mapping_stats['medium_confidence_mappings'])}):")
        for mapping_tuple in sorted(mapping_stats['medium_confidence_mappings'], key=lambda x: x[2], reverse=True)[:10]:
            field_name, mapped_to, score, section = mapping_tuple
            logger.info(f"  - '{field_name}' -> '{mapped_to}' (score: {score:.2f}, section: {section})")
    
    # Show low confidence mappings for review
    if mapping_stats['low_confidence_mappings']:
        logger.info(f"\nLOW CONFIDENCE MAPPINGS ({min(10, len(mapping_stats['low_confidence_mappings']))} of {len(mapping_stats['low_confidence_mappings'])}):")
        for mapping_tuple in sorted(mapping_stats['low_confidence_mappings'], key=lambda x: x[2])[:10]:
            field_name, mapped_to, score, section = mapping_tuple
            logger.info(f"  - '{field_name}' -> '{mapped_to}' (score: {score:.2f}, section: {section})")
    
    # Return the JSON serializable version for external use
    return json_mapping_stats

def convert_mapping_stats_to_json(mapping_stats):
    """
    Convert mapping_stats to a JSON serializable format.
    
    Args:
        mapping_stats: The original mapping_stats dictionary
        
    Returns:
        Dictionary with all minimum information to be used for mapping tests
    """
    json_stats = {}
    
    # Convert simple fields
    json_stats['total_fields'] = mapping_stats['total_fields']
    
    # Convert sets to sorted lists
    json_stats['mapped_fields'] = sorted(list(mapping_stats['mapped_fields']))
    
    # Convert defaultdict sets to regular dicts with sorted lists
    json_stats['mapped_fields_by_authority'] = {}
    for authority, field_set in mapping_stats['mapped_fields_by_authority'].items():
        json_stats['mapped_fields_by_authority'][authority] = sorted(list(field_set))
    
    json_stats['unmapped_fields_by_authority'] = {}
    for authority, field_set in mapping_stats['unmapped_fields_by_authority'].items():
        json_stats['unmapped_fields_by_authority'][authority] = sorted(list(field_set))
    
    
    return json_stats
