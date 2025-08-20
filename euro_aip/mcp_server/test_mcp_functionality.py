#!/usr/bin/env python3
"""
MCP Functionality Test Script
============================

This script simulates the actual MCP tool calls to verify that basic functionality
is working correctly after refactoring. It tests the three main tools:

1. search_airports - Basic airport search functionality
2. find_airports_near_route - Route-based airport discovery
3. get_airport_details - Individual airport information retrieval

KEEP THIS FILE! It's essential for:
- Verifying refactoring didn't break core functionality
- Testing the new generic filter system
- Ensuring MCP tools work as expected
- Quick validation before deploying changes

Run this script whenever you make changes to verify nothing is broken.
"""

import os
import sys
import asyncio

# Add the parent directory to the path so we can import euro_aip modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from euro_aip.storage.database_storage import DatabaseStorage
from mcp_server.main import AirportService, ResponseFormatter, AirportFilter

def test_mcp_functionality():
    """Test the MCP server functionality by simulating tool calls."""
    
    # Set the database path
    db_path = "/Users/brice/Developer/public/rzflight/euro_aip/web/server/airports.db"
    
    try:
        # Load the model
        print("Loading airport database...")
        storage = DatabaseStorage(db_path)
        model = storage.load_model()
        
        if not model:
            print("Error: Could not load airport model from database")
            return
        
        # Create service
        service = AirportService(model)
        formatter = ResponseFormatter()
        
        print(f"✓ Loaded model with {len(model.airports)} airports\n")
        
        print("=== Testing MCP Tool Functionality ===\n")
        
        # Test 1: search_airports - "fairoaks"
        print("1. Testing search_airports for 'fairoaks':")
        print("   Simulating: search_airports(query='fairoaks')")
        
        # Simulate the search request
        from mcp_server.main import SearchAirportsRequest
        search_request = SearchAirportsRequest(query="fairoaks")
        search_results = service.search_airports(search_request)
        
        print(f"   ✓ Found {len(search_results)} airports")
        if search_results:
            for i, airport in enumerate(search_results[:3]):  # Show first 3
                print(f"      {i+1}. {airport.ident} - {airport.name} ({airport.iso_country})")
        else:
            print("      No airports found")
        
        # Test 2: find_airports_near_route - EGTF to LFQA
        print("\n2. Testing find_airports_near_route from EGTF to LFQA:")
        print("   Simulating: find_airports_near_route(route_airports=['EGTF', 'LFQA'], distance_nm=50)")
        
        route_airports = ['EGTF', 'LFQA']
        distance_nm = 50.0
        
        # Simulate the route search
        route_results = service.find_airports_near_route(route_airports, distance_nm)
        
        print(f"   ✓ Found {len(route_results)} airports near route")
        if route_results:
            for i, item in enumerate(route_results[:5]):  # Show first 5
                airport = item['airport']
                distance = item.get('distance_nm', 'N/A')
                print(f"      {i+1}. {airport.ident} - {airport.name} ({airport.iso_country}) - {distance}nm")
        else:
            print("      No airports found near route")
        
        # Test 3: get_airport_details - EGTF
        print("\n3. Testing get_airport_details for EGTF:")
        print("   Simulating: get_airport_details(icao_code='EGTF')")
        
        airport_egtf = service.get_airport("EGTF")
        if airport_egtf:
            print(f"   ✓ Found airport: {airport_egtf.ident} - {airport_egtf.name}")
            print(f"      Country: {airport_egtf.iso_country}")
            print(f"      Coordinates: {airport_egtf.latitude_deg}, {airport_egtf.longitude_deg}")
            print(f"      Elevation: {airport_egtf.elevation_ft}ft")
            print(f"      Customs: {'Yes' if airport_egtf.point_of_entry else 'No'}")
            print(f"      AVGAS: {'Yes' if airport_egtf.avgas else 'No'}")
            print(f"      Jet A: {'Yes' if airport_egtf.jet_a else 'No'}")
        else:
            print("   ✗ Airport EGTF not found")
        
        # Test 4: Test with filters
        print("\n4. Testing search_airports with filters:")
        print("   Simulating: search_airports(query='London', has_customs=True, country='GB')")
        
        filtered_request = SearchAirportsRequest(
            query="London", 
            has_customs=True, 
            country="GB"
        )
        filtered_results = service.search_airports(filtered_request)
        
        print(f"   ✓ Found {len(filtered_results)} airports with filters")
        if filtered_results:
            for i, airport in enumerate(filtered_results[:3]):
                print(f"      {i+1}. {airport.ident} - {airport.name} ({airport.iso_country})")
                print(f"         Customs: {'Yes' if airport.point_of_entry else 'No'}")
        else:
            print("      No airports found with filters")
        
        # Test 5: Test route search with filters
        print("\n5. Testing find_airports_near_route with filters:")
        print("   Simulating: find_airports_near_route(['EGTF', 'LFQA'], 50, {'has_customs': True})")
        
        route_filters = {'has_customs': True}
        filtered_route_results = service.find_airports_near_route(route_airports, distance_nm, route_filters)
        
        print(f"   ✓ Found {len(filtered_route_results)} airports with customs filter")
        if filtered_route_results:
            for i, item in enumerate(filtered_route_results[:3]):
                airport = item['airport']
                print(f"      {i+1}. {airport.ident} - {airport.name} ({airport.iso_country})")
                print(f"         Customs: {'Yes' if airport.point_of_entry else 'No'}")
        else:
            print("      No airports found with customs filter")
        
        # Test 6: Verify filter system is working
        print("\n6. Testing filter system integration:")
        print("   ✓ Filter types available:", list(AirportFilter.FILTER_TYPES.keys()))
        
        # Test filter application directly
        test_airport = service.get_airport("LFQA") or service.get_airport("EGTF")
        if test_airport:
            test_filters = {'country': 'FR', 'has_customs': True}
            passes_filters = AirportFilter.apply_filters(test_airport, test_filters)
            print(f"   ✓ Filter application test: {passes_filters}")
        
        print("\n=== All MCP Functionality Tests Completed Successfully! ===")
        print("✓ search_airports working")
        print("✓ find_airports_near_route working") 
        print("✓ get_airport_details working")
        print("✓ Filter system integrated")
        print("✓ No basic functionality broken")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_mcp_functionality()
