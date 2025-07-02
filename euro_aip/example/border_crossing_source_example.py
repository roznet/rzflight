#!/usr/bin/env python3
"""
Example script demonstrating BorderCrossingSource usage.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from euro_aip.sources.border_crossing import BorderCrossingSource
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def main():
    """Demonstrate BorderCrossingSource usage."""
    
    print("=== Border Crossing Source Example ===\n")
    
    # Example 1: Using default URLs
    print("1. Using default URLs:")
    source1 = BorderCrossingSource("cache")
    print(f"   Available inputs: {[name for name, _ in source1.get_available_inputs()]}")
    
    # Get data from all inputs
    try:
        data = source1.get_border_crossing_data()
        print(f"   Retrieved {len(data)} airport entries")
        
        # Show first few entries
        if data:
            print("   First 3 entries:")
            for i, entry in enumerate(data[:3]):
                print(f"     {i+1}. {entry.get('airport_name', 'N/A')} ({entry.get('country', 'N/A')})")
    except Exception as e:
        print(f"   Error: {e}")
    
    print()
    
    # Example 2: Using custom inputs
    print("2. Using custom inputs:")
    custom_inputs = [
        ("local_test", "cache/OJ_BorderCrossing.html"),  # Local file
        ("official_2023", "https://eur-lex.europa.eu/legal-content/EN/TXT/HTML/?uri=CELEX:52023XC0609(06)")  # URL
    ]
    
    source2 = BorderCrossingSource("cache", custom_inputs)
    print(f"   Available inputs: {[name for name, _ in source2.get_available_inputs()]}")
    
    # Get data from specific input
    try:
        data = source2.get_border_crossing_data(input_name="local_test")
        print(f"   Retrieved {len(data)} airport entries from local_test")
    except Exception as e:
        print(f"   Error: {e}")
    
    print()
    
    # Example 3: Using simple string inputs (names auto-generated)
    print("3. Using simple string inputs (auto-generated names):")
    simple_inputs = [
        "cache/OJ_BorderCrossing.html",  # Name will be "OJ_BorderCrossing"
        "https://eur-lex.europa.eu/legal-content/EN/TXT/HTML/?uri=CELEX:52023XC0609(06)"  # Name will be "eur_lex_europa_eu"
    ]
    
    source3 = BorderCrossingSource("cache", simple_inputs)
    print(f"   Available inputs: {[name for name, _ in source3.get_available_inputs()]}")
    
    print()
    
    # Example 4: Adding inputs dynamically
    print("4. Adding inputs dynamically:")
    source4 = BorderCrossingSource("cache")
    print(f"   Initial inputs: {[name for name, _ in source4.get_available_inputs()]}")
    
    source4.add_input("custom_file", "cache/OJ_BorderCrossing.html")
    print(f"   After adding: {[name for name, _ in source4.get_available_inputs()]}")
    
    source4.remove_input("official_journal_2023")
    print(f"   After removing: {[name for name, _ in source4.get_available_inputs()]}")
    
    print()
    
    # Example 5: Force refresh
    print("5. Force refresh example:")
    source5 = BorderCrossingSource("cache", [("test", "cache/OJ_BorderCrossing.html")])
    
    # First call (normal)
    print("   First call (normal):")
    try:
        data = source5.get_border_crossing_data(input_name="test")
        print(f"   Retrieved {len(data)} entries")
    except Exception as e:
        print(f"   Error: {e}")
    
    # Force refresh
    print("   Force refresh:")
    source5.set_force_refresh(True)
    try:
        data = source5.get_border_crossing_data(input_name="test")
        print(f"   Retrieved {len(data)} entries (forced refresh)")
    except Exception as e:
        print(f"   Error: {e}")
    
    # Reset to normal
    source5.set_force_refresh(False)
    
    print("\n=== Example completed ===")

if __name__ == "__main__":
    main() 