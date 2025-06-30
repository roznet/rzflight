#!/usr/bin/env python3

"""
Example demonstrating field extensibility in the database storage system.

This shows how to:
1. Add new fields to the centralized field definitions
2. Handle schema migrations automatically
3. Maintain type safety and change tracking
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from euro_aip.storage.field_definitions import AirportFields, FieldType, FieldDefinition
from euro_aip.storage.database_storage import DatabaseStorage
from euro_aip.models.euro_aip_model import EuroAipModel
from euro_aip.models.airport import Airport
from datetime import datetime

def demonstrate_field_addition():
    """Demonstrate how to add new fields to the system."""
    
    print("=== Field Extensibility Example ===\n")
    
    # Step 1: Show current field definitions
    print("1. Current airport fields:")
    for field in AirportFields.get_all_fields():
        print(f"   - {field.name}: {field.field_type.value} ({field.description})")
    
    print("\n2. Adding new fields to AirportFields class:")
    print("   # Add these lines to AirportFields class:")
    print("   WEATHER_STATION = FieldDefinition('weather_station', FieldType.STRING, description='Weather station code')")
    print("   TIMEZONE = FieldDefinition('timezone', FieldType.STRING, description='Timezone')")
    print("   MAGNETIC_VARIATION = FieldDefinition('magnetic_variation', FieldType.FLOAT, description='Magnetic variation in degrees')")
    print("   RUNWAY_COUNT = FieldDefinition('runway_count', FieldType.INTEGER, description='Number of runways')")
    print("   HAS_CUSTOMS = FieldDefinition('has_customs', FieldType.BOOLEAN, description='Customs facility available')")
    
    print("\n3. The system automatically handles:")
    print("   - Schema creation with new fields")
    print("   - Type-safe storage and retrieval")
    print("   - Change tracking for new fields")
    print("   - Migration from old schema to new schema")
    
    # Step 2: Demonstrate with a test database
    print("\n4. Testing with a sample database:")
    
    # Create a test database
    db_path = "test_field_extensibility.db"
    storage = DatabaseStorage(db_path)
    
    # Create a sample model
    model = EuroAipModel()
    
    # Add a sample airport
    airport = Airport(
        ident="EGLL",
        name="London Heathrow Airport",
        type="large_airport",
        latitude_deg=51.4706,
        longitude_deg=-0.461941,
        elevation_ft=83,
        continent="EU",
        iso_country="GB",
        iso_region="GB-ENG",
        municipality="London",
        scheduled_service="yes",
        gps_code="EGLL",
        iata_code="LHR",
        local_code="",
        home_link="https://www.heathrow.com/",
        wikipedia_link="https://en.wikipedia.org/wiki/Heathrow_Airport",
        keywords="heathrow,london,uk"
    )
    airport.add_source("WorldAirports")
    
    model.airports["EGLL"] = airport
    
    # Save to database
    storage.save_model(model)
    print(f"   - Saved airport to database: {db_path}")
    
    # Load from database
    loaded_model = storage.load_model()
    loaded_airport = loaded_model.airports["EGLL"]
    print(f"   - Loaded airport: {loaded_airport.name}")
    print(f"   - Type-safe coordinates: {loaded_airport.latitude_deg}°N, {loaded_airport.longitude_deg}°E")
    print(f"   - Integer elevation: {loaded_airport.elevation_ft} ft")
    
    # Get database info
    info = storage.get_database_info()
    print(f"   - Database tables: {list(info['tables'].keys())}")
    print(f"   - Airport records: {info['tables']['airports']}")
    
    # Clean up
    os.remove(db_path)
    print(f"   - Cleaned up test database")

def demonstrate_schema_migration():
    """Demonstrate schema migration capabilities."""
    
    print("\n=== Schema Migration Example ===\n")
    
    print("1. Current schema version: 1")
    print("2. To add new fields in the future:")
    print("   a) Add field definitions to AirportFields class")
    print("   b) Increment schema version in SchemaManager")
    print("   c) Add migration logic in migrate_schema() method")
    print("   d) The system automatically detects and applies migrations")
    
    print("\n3. Example migration code:")
    print("""
    def migrate_schema(self, conn, current_version: int) -> int:
        if current_version < 2:
            # Add weather_station field
            weather_field = AirportFields.WEATHER_STATION
            conn.execute(self.get_alter_table_sql("airports", weather_field))
            
        if current_version < 3:
            # Add timezone field
            timezone_field = AirportFields.TIMEZONE
            conn.execute(self.get_alter_table_sql("airports", timezone_field))
            
        return self.version  # Current version
    """)

def demonstrate_type_safety():
    """Demonstrate type safety features."""
    
    print("\n=== Type Safety Example ===\n")
    
    print("1. Field types are enforced:")
    print("   - STRING: Stored as TEXT, compared as strings")
    print("   - INTEGER: Stored as INTEGER, compared as integers")
    print("   - FLOAT: Stored as REAL, compared as floats")
    print("   - BOOLEAN: Stored as INTEGER (0/1), compared as booleans")
    print("   - DATETIME: Stored as TEXT (ISO format), compared as datetime objects")
    
    print("\n2. Automatic type conversion:")
    print("   - format_for_storage(): Converts Python types to SQL types")
    print("   - format_for_comparison(): Converts values for change detection")
    print("   - Loading: Converts SQL types back to Python types")
    
    print("\n3. Example type conversions:")
    print("   - Boolean: True -> 1, False -> 0")
    print("   - Integer: 123 -> 123 (no conversion needed)")
    print("   - Float: 123.45 -> 123.45 (no conversion needed)")
    print("   - String: 'test' -> 'test' (no conversion needed)")
    print("   - DateTime: datetime(2024,1,1) -> '2024-01-01T00:00:00'")

def demonstrate_change_tracking():
    """Demonstrate change tracking capabilities."""
    
    print("\n=== Change Tracking Example ===\n")
    
    print("1. Changes are tracked with type information:")
    print("   - Field name and type")
    print("   - Old and new values (properly formatted)")
    print("   - Source of the change")
    print("   - Timestamp of the change")
    
    print("\n2. Change detection is type-aware:")
    print("   - Integer comparison: 123 != '123'")
    print("   - Float comparison: 123.0 != 123")
    print("   - Boolean comparison: True != 1")
    print("   - String comparison: 'test' != 'TEST'")
    
    print("\n3. Change history is queryable:")
    print("   - By airport: get_changes_for_airport('EGLL')")
    print("   - By time range: Last 30 days")
    print("   - By field type: Only integer changes")
    print("   - By source: Changes from specific data source")

if __name__ == "__main__":
    demonstrate_field_addition()
    demonstrate_schema_migration()
    demonstrate_type_safety()
    demonstrate_change_tracking()
    
    print("\n=== Summary ===")
    print("The new field definition system provides:")
    print("✅ Centralized field definitions")
    print("✅ Type safety and automatic conversion")
    print("✅ Easy schema evolution")
    print("✅ Comprehensive change tracking")
    print("✅ No hard-coded field lists")
    print("✅ Automatic migration support")
    print("✅ Extensible design for new field types") 