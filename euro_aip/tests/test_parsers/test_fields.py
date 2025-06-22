import pytest
import json
from pathlib import Path
from euro_aip.parsers import AIPParserFactory
from euro_aip.utils.field_mapper import FieldMapper
import logging

logger = logging.getLogger(__name__)

def load_expected_fields_map():
    """
    Load the expected fields map from JSON file.
    
    Returns:
        Dictionary containing expected field mappings
    """
    expected_file = Path(__file__).parent.parent / "assets" / "expected_fields_map.json"
    
    if not expected_file.exists():
        logger.warning(f"Expected fields map file not found: {expected_file}")
        return {}
    
    try:
        with open(expected_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error loading expected fields map: {e}")
        return {}

def test_expected_fields_still_mapped():
    """
    Test that all fields in the expected fields map are still being mapped correctly.
    """
    # Load expected fields map
    expected_fields_map = load_expected_fields_map()
    
    if not expected_fields_map:
        pytest.skip("No expected fields map available")
    
    # Initialize field mapper
    field_mapper = FieldMapper()
    
    # Track test results
    test_results = {
        'total_expected_fields': 0,
        'still_mapped_fields': 0,
        'unmapped_fields': [],
        'changed_mappings': [],
        'authority_results': {}
    }
    
    # Test each expected field mapping
    for field_info in expected_fields_map.get('mapped_fields', []):
        (field_name,section) = field_info
        
        test_results['total_expected_fields'] += 1
        
        # Try to map the field
        mapping = field_mapper.map_field(field_name, section)
        if mapping['mapped']:
            test_results['still_mapped_fields'] += 1
        else:
            test_results['unmapped_fields'].append((field_name,section))
    # check no fields are now unmapped
    assert test_results['unmapped_fields'] == []
     
def test_unmapped_fields_can_be_mapped():
    # Load expected fields map
    expected_fields_map = load_expected_fields_map()
    
    if not expected_fields_map:
        pytest.skip("No expected fields map available")
    
    # Initialize field mapper
    field_mapper = FieldMapper()

    # Log test results
    logger.info("=" * 80)
    logger.info("FIELD MAPPING VALIDATION RESULTS")
    logger.info("=" * 80)
    
    focus_authority = []
    focus_fields = []

    test_results = {
        'total_unmapped_fields': 0,
        'still_unmapped_fields': 0,
        'now_mapped_fields':set()
    }
    # now got through unmapped fields and see if they can be mapped now
    # by default loops through each authority and field, but if focus_authority or focus_fields is set,
    # only loop through those authorities and fields
    for authority,field_infos in expected_fields_map['unmapped_fields_by_authority'].items():
        if focus_authority and authority not in focus_authority:
            continue
        for field_info in field_infos:
            (field_name,section) = field_info
            if focus_fields and field_name not in focus_fields:
                continue
            mapping = field_mapper.map_field(field_name)
            if mapping['mapped']:
                test_results['now_mapped_fields'].add(field_name)
            else:
                test_results['still_unmapped_fields'] += 1 

    logger.info(f"Total unmapped fields: {test_results['total_unmapped_fields']}")
    logger.info(f"Still unmapped fields: {test_results['still_unmapped_fields']}")
    logger.info(f"Now mapped fields: {test_results['now_mapped_fields']}")
