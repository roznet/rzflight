#!/usr/bin/env python3
"""
Test script demonstrating the save_only_std_fields functionality in DatabaseStorage.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from euro_aip.storage.database_storage import DatabaseStorage
from euro_aip.models.euro_aip_model import EuroAipModel
from euro_aip.models.airport import Airport
from euro_aip.models.aip_entry import AIPEntry
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def create_test_model():
    """Create a test model with both standardized and non-standardized AIP entries."""
    model = EuroAipModel()
    
    # Create a test airport
    airport = Airport(
        ident="TEST",
        name="Test Airport",
        type="medium_airport",
        latitude_deg=51.4706,
        longitude_deg=-0.4619,
        elevation_ft=83,
        continent="EU",
        iso_country="GB",
        iso_region="GB-ENG",
        municipality="London",
        scheduled_service=True,
        gps_code="EGLL",
        iata_code="LHR",
        local_code="LHR",
        home_link="",
        wikipedia_link="",
        keywords=""
    )
    
    # Add standardized AIP entries (with std_field_id)
    std_entry1 = AIPEntry(
        ident="TEST",
        section="AD-2",
        field="Airport Name",
        value="Test Airport",
        std_field="airport_name",
        std_field_id=1,
        mapping_score=0.95,
        alt_field="",
        alt_value="",
        source="test_source"
    )
    
    std_entry2 = AIPEntry(
        ident="TEST",
        section="AD-2",
        field="ICAO Code",
        value="TEST",
        std_field="icao_code",
        std_field_id=2,
        mapping_score=1.0,
        alt_field="",
        alt_value="",
        source="test_source"
    )
    
    # Add non-standardized AIP entries (without std_field_id)
    non_std_entry1 = AIPEntry(
        ident="TEST",
        section="AD-2",
        field="Some Random Field",
        value="Random Value",
        std_field="",
        std_field_id=None,
        mapping_score=0.0,
        alt_field="",
        alt_value="",
        source="test_source"
    )
    
    non_std_entry2 = AIPEntry(
        ident="TEST",
        section="AD-2",
        field="Another Unknown Field",
        value="Another Value",
        std_field="",
        std_field_id=None,
        mapping_score=0.0,
        alt_field="",
        alt_value="",
        source="test_source"
    )
    
    # Add all entries to airport
    airport.add_aip_entry(std_entry1)
    airport.add_aip_entry(std_entry2)
    airport.add_aip_entry(non_std_entry1)
    airport.add_aip_entry(non_std_entry2)
    
    # Add airport to model
    model.airports["TEST"] = airport
    
    return model

def test_std_fields_filtering():
    """Test the save_only_std_fields functionality."""
    
    print("=== Testing save_only_std_fields Functionality ===\n")
    
    # Test 1: Default behavior (save_only_std_fields=True)
    print("1. Testing default behavior (save_only_std_fields=True):")
    db1 = DatabaseStorage("cache/test_std_fields_default.db")
    print(f"   Default setting: {db1.get_save_only_std_fields()}")
    
    model = create_test_model()
    db1.save_model(model)
    
    # Load and check what was saved
    loaded_model = db1.load_model()
    test_airport = loaded_model.airports.get("TEST")
    if test_airport:
        print(f"   Saved {len(test_airport.aip_entries)} AIP entries")
        for entry in test_airport.aip_entries:
            print(f"     - {entry.section}.{entry.field}: {entry.value} (std_field_id: {entry.std_field_id})")
    print()
    
    # Test 2: Explicitly set to True
    print("2. Testing explicitly set to True:")
    db2 = DatabaseStorage("cache/test_std_fields_true.db", save_only_std_fields=True)
    print(f"   Setting: {db2.get_save_only_std_fields()}")
    
    db2.save_model(model)
    loaded_model = db2.load_model()
    test_airport = loaded_model.airports.get("TEST")
    if test_airport:
        print(f"   Saved {len(test_airport.aip_entries)} AIP entries")
        for entry in test_airport.aip_entries:
            print(f"     - {entry.section}.{entry.field}: {entry.value} (std_field_id: {entry.std_field_id})")
    print()
    
    # Test 3: Set to False to save all entries
    print("3. Testing save_only_std_fields=False:")
    db3 = DatabaseStorage("cache/test_std_fields_false.db", save_only_std_fields=False)
    print(f"   Setting: {db3.get_save_only_std_fields()}")
    
    db3.save_model(model)
    loaded_model = db3.load_model()
    test_airport = loaded_model.airports.get("TEST")
    if test_airport:
        print(f"   Saved {len(test_airport.aip_entries)} AIP entries")
        for entry in test_airport.aip_entries:
            print(f"     - {entry.section}.{entry.field}: {entry.value} (std_field_id: {entry.std_field_id})")
    print()
    
    # Test 4: Change setting after initialization
    print("4. Testing changing setting after initialization:")
    db4 = DatabaseStorage("cache/test_std_fields_change.db")
    print(f"   Initial setting: {db4.get_save_only_std_fields()}")
    
    # Save with default (True)
    db4.save_model(model)
    loaded_model = db4.load_model()
    test_airport = loaded_model.airports.get("TEST")
    print(f"   After saving with default: {len(test_airport.aip_entries) if test_airport else 0} entries")
    
    # Change setting and save again
    db4.set_save_only_std_fields(False)
    print(f"   Changed setting to: {db4.get_save_only_std_fields()}")
    
    db4.save_model(model)
    loaded_model = db4.load_model()
    test_airport = loaded_model.airports.get("TEST")
    print(f"   After saving with False: {len(test_airport.aip_entries) if test_airport else 0} entries")
    
    print("\n=== Test completed ===")

if __name__ == "__main__":
    test_std_fields_filtering() 