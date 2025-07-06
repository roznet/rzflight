#!/usr/bin/env python3

"""
Test script to verify nan handling in the border crossing CSV parsing.
"""

import sys
import logging
from pathlib import Path

# Add the parent directory to the path so we can import euro_aip
sys.path.insert(0, str(Path(__file__).parent.parent))

from euro_aip.sources.border_crossing import BorderCrossingSource

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_nan_handling():
    """Test that nan values are properly handled."""
    
    print("=== Testing NaN Handling ===\n")
    
    # Initialize the source
    source = BorderCrossingSource(
        cache_dir="cache",
        inputs=[("test_airfield", "airfieldmap.csv")]
    )
    
    # Get the parsed data
    data = source.get_border_crossing_data("test_airfield")
    
    # Check for any "nan" strings in the data
    nan_strings_found = []
    none_values_found = []
    
    for i, entry in enumerate(data[:10]):  # Check first 10 entries
        print(f"Entry {i+1}: {entry['airport_name']}")
        print(f"  ICAO: {entry['icao_code']}")
        print(f"  Country: {entry['country']}")
        print(f"  Type: {entry['metadata']['type']}")
        print(f"  Comment: {entry['metadata']['comment']}")
        print(f"  Airfield Name: {entry['metadata']['airfield_name']}")
        print()
        
        # Check for "nan" strings
        for key, value in entry.items():
            if isinstance(value, str) and value.lower() == 'nan':
                nan_strings_found.append(f"{key}: {value}")
        
        # Check for None values (which is correct)
        for key, value in entry.items():
            if value is None:
                none_values_found.append(f"{key}: None")
    
    print("=== Results ===")
    if nan_strings_found:
        print(f"❌ Found {len(nan_strings_found)} 'nan' strings (BAD):")
        for item in nan_strings_found:
            print(f"  - {item}")
    else:
        print("✅ No 'nan' strings found (GOOD)")
    
    if none_values_found:
        print(f"✅ Found {len(none_values_found)} None values (GOOD):")
        for item in none_values_found:
            print(f"  - {item}")
    else:
        print("ℹ️  No None values found")
    
    print(f"\nTotal entries processed: {len(data)}")
    
    return len(nan_strings_found) == 0

if __name__ == "__main__":
    success = test_nan_handling()
    if success:
        print("\n✅ NaN handling test PASSED")
    else:
        print("\n❌ NaN handling test FAILED") 