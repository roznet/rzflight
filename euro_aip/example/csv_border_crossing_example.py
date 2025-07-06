#!/usr/bin/env python3

"""
Example script demonstrating CSV border crossing data parsing.

This script shows how to use the BorderCrossingSource with CSV files
that contain border crossing airport data.
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

def main():
    """Demonstrate CSV border crossing functionality."""
    
    print("=== CSV Border Crossing Example ===\n")
    
    # Initialize the source with CSV file
    csv_file = "airfieldmap.csv"
    
    if not Path(csv_file).exists():
        print(f"❌ CSV file not found: {csv_file}")
        print("Please place the airfieldmap.csv file in the current directory.")
        return
    
    print(f"1. Initializing BorderCrossingSource with CSV file: {csv_file}")
    
    source = BorderCrossingSource(
        cache_dir="cache",
        inputs=[("airfield_map", csv_file)]
    )
    
    print(f"   Available inputs: {[name for name, _ in source.get_available_inputs()]}")
    
    print("\n2. Fetching and parsing CSV data:")
    
    try:
        # Get parsed data
        data = source.get_border_crossing_data()
        print(f"   ✅ Successfully parsed {len(data)} airport entries")
        
        # Show first few entries
        print(f"\n3. First 5 entries:")
        for i, entry in enumerate(data[:5]):
            print(f"   {i+1}. {entry['airport_name']} ({entry['country']})")
            print(f"      ICAO: {entry.get('icao_code', 'N/A')}")
            print(f"      Type: {entry['metadata']['type']}")
            print(f"      Comment: {entry['metadata']['comment']}")
            print(f"      Airfield Name: {entry['metadata']['airfield_name']}")
            print(f"      Is Airport: {entry['is_airport']}")
            print()
        
        # Show statistics
        print(f"4. Statistics:")
        countries = set(entry['country'] for entry in data)
        types = set(entry['metadata']['type'] for entry in data)
        airports_with_icao = sum(1 for entry in data if entry.get('icao_code'))
        
        print(f"   Total entries: {len(data)}")
        print(f"   Countries: {len(countries)}")
        print(f"   Types: {', '.join(sorted(types))}")
        print(f"   Entries with ICAO codes: {airports_with_icao}")
        print(f"   Airport/Aerodrome entries: {sum(1 for entry in data if entry['is_airport'])}")
        
        # Show some country statistics
        print(f"\n5. Entries by country (top 5):")
        country_counts = {}
        for entry in data:
            country = entry['country']
            country_counts[country] = country_counts.get(country, 0) + 1
        
        for country, count in sorted(country_counts.items(), key=lambda x: x[1], reverse=True)[:5]:
            print(f"   {country}: {count} entries")
        
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return
    
    print(f"\n=== Example completed successfully ===")

if __name__ == '__main__':
    main() 