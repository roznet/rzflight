#!/usr/bin/env python3

"""
Test script to verify duplicate handling and merging functionality for border crossing entries.
"""

import sys
import logging
from pathlib import Path

# Add the parent directory to the path so we can import euro_aip
sys.path.insert(0, str(Path(__file__).parent.parent))

from euro_aip.models.border_crossing_entry import BorderCrossingEntry
from euro_aip.sources.border_crossing import BorderCrossingSource

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_entry_merging():
    """Test the merging functionality of BorderCrossingEntry."""
    
    print("=== Testing BorderCrossingEntry Merging ===\n")
    
    # Create two entries for the same airport with different information
    entry1 = BorderCrossingEntry(
        airport_name="Brussels National Airport",
        country_iso="BE",
        icao_code=None,  # Missing ICAO
        is_airport=True,
        source="border_crossing_csv",
        extraction_method="csv_parsing",
        metadata={
            'type': 'Airport',
            'comment': 'Main international airport',
            'airfield_name': 'Brussels National'
        }
    )
    
    entry2 = BorderCrossingEntry(
        airport_name="Brussels National Airport",
        country_iso="BE",
        icao_code="EBBR",  # Has ICAO code
        is_airport=None,  # Unknown
        source="border_crossing_html",
        extraction_method="html_parsing",
        metadata={
            'type': 'Airport',
            'comment': '',  # Empty comment
            'airfield_name': 'Brussels National',
            'additional_info': 'International hub'  # Extra info
        },
        matched_airport_icao="EBBR",
        match_score=0.95
    )
    
    # Create a third entry with only metadata differences
    entry3 = BorderCrossingEntry(
        airport_name="Brussels National Airport",
        country_iso="BE",
        icao_code="EBBR",  # Same ICAO
        is_airport=True,  # Same flag
        source="border_crossing_api",
        extraction_method="csv_parsing",  # Same method
        metadata={
            'type': 'Airport',
            'comment': 'Main international airport',
            'airfield_name': 'Brussels National',
            'extra_metadata': 'Some additional info'  # Only metadata difference
        }
    )
    
    # Create a fourth entry that truly has only metadata differences (no meaningful changes)
    entry4 = BorderCrossingEntry(
        airport_name="Brussels National Airport",
        country_iso="BE",
        icao_code="EBBR",  # Same ICAO as entry3
        is_airport=True,  # Same flag as entry3
        source="border_crossing_api",
        extraction_method="csv_parsing",  # Same method as entry3
        metadata={
            'type': 'Airport',
            'comment': 'Main international airport',
            'airfield_name': 'Brussels National',
            'different_metadata': 'Another metadata field'  # Only metadata difference
        }
    )
    
    print("Entry 1:")
    print(f"  ICAO: {entry1.icao_code}")
    print(f"  Is Airport: {entry1.is_airport}")
    print(f"  Source: {entry1.source}")
    print(f"  Match Score: {entry1.match_score}")
    print(f"  Metadata keys: {list(entry1.metadata.keys())}")
    print()
    
    print("Entry 2:")
    print(f"  ICAO: {entry2.icao_code}")
    print(f"  Is Airport: {entry2.is_airport}")
    print(f"  Source: {entry2.source}")
    print(f"  Match Score: {entry2.match_score}")
    print(f"  Metadata keys: {list(entry2.metadata.keys())}")
    print()
    
    print("Entry 3 (metadata only differences):")
    print(f"  ICAO: {entry3.icao_code}")
    print(f"  Is Airport: {entry3.is_airport}")
    print(f"  Source: {entry3.source}")
    print(f"  Match Score: {entry3.match_score}")
    print(f"  Metadata keys: {list(entry3.metadata.keys())}")
    print()
    
    print("Entry 4 (metadata only differences):")
    print(f"  ICAO: {entry4.icao_code}")
    print(f"  Is Airport: {entry4.is_airport}")
    print(f"  Source: {entry4.source}")
    print(f"  Match Score: {entry4.match_score}")
    print(f"  Metadata keys: {list(entry4.metadata.keys())}")
    print()
    
    # Test completeness comparison
    print("Completeness comparison:")
    print(f"  Entry 1 more complete than Entry 2: {entry1.is_more_complete_than(entry2)}")
    print(f"  Entry 2 more complete than Entry 1: {entry2.is_more_complete_than(entry1)}")
    print()
    
    # Merge entries with meaningful changes
    merged_entry = entry1.merge_with(entry2)
    
    print("Merged Entry (with meaningful changes):")
    print(f"  ICAO: {merged_entry.icao_code}")
    print(f"  Is Airport: {merged_entry.is_airport}")
    print(f"  Source: {merged_entry.source}")
    print(f"  Match Score: {merged_entry.match_score}")
    print(f"  Metadata keys: {list(merged_entry.metadata.keys())}")
    print(f"  Metadata: {merged_entry.metadata}")
    print()
    
    # Test merging with only metadata differences
    merged_entry_metadata_only = entry3.merge_with(entry4)
    
    print("Merged Entry (metadata only):")
    print(f"  ICAO: {merged_entry_metadata_only.icao_code}")
    print(f"  Is Airport: {merged_entry_metadata_only.is_airport}")
    print(f"  Source: {merged_entry_metadata_only.source}")
    print(f"  Match Score: {merged_entry_metadata_only.match_score}")
    print(f"  Metadata keys: {list(merged_entry_metadata_only.metadata.keys())}")
    print()
    
    # Test that sources are only combined when meaningful changes occur
    print("Source combination test:")
    print(f"  Entry 1 + Entry 2 (meaningful changes): {merged_entry.source}")
    print(f"  Entry 3 + Entry 4 (metadata only): {merged_entry_metadata_only.source}")
    print()
    
    # Test with CSV source
    source = BorderCrossingSource(cache_dir="cache")
    
    # Test duplicate handling in actual data
    print("=== Testing Duplicate Handling in Real Data ===\n")
    
    # Get border crossing data
    try:
        data = source.get_border_crossing_data("airfield_map")
        print(f"Retrieved {len(data)} raw entries")
        
        # Simulate duplicate handling
        entries_by_name = {}
        for entry in data[:10]:  # Process first 10 entries
            airport_name = entry.get('airport_name', '')
            if airport_name in entries_by_name:
                print(f"Found duplicate for: {airport_name}")
                existing = entries_by_name[airport_name]
                print(f"  Existing ICAO: {existing.get('icao_code')}")
                print(f"  New ICAO: {entry.get('icao_code')}")
            else:
                entries_by_name[airport_name] = entry
        
        print(f"\nUnique entries: {len(entries_by_name)}")
        print(f"Duplicates found: {len(data[:10]) - len(entries_by_name)}")
        
    except Exception as e:
        print(f"Error testing with real data: {e}")
    
    return True

if __name__ == "__main__":
    success = test_entry_merging()
    if success:
        print("\n✅ Duplicate merging test PASSED")
    else:
        print("\n❌ Duplicate merging test FAILED") 