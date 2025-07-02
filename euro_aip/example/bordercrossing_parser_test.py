#!/usr/bin/env python3
"""
Test script for BorderCrossingParser.

This script tests various edge cases and input formats to ensure
the parser handles unicode characters and special cases correctly.
"""

import sys
from pathlib import Path

# Add the project root to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from euro_aip.parsers import BorderCrossingParser

def test_unicode_and_special_characters():
    """Test the parser with unicode characters and special cases."""
    
    parser = BorderCrossingParser()
    
    # Test cases with various unicode characters and special cases
    test_cases = [
        # French airports with accents
        "(1) Aéroport Charles de Gaulle",
        "(2) Aéroport d'Orly",
        "(3) Aéroport Nice Côte d'Azur",
        
        # German airports
        "(4) Flughafen München",
        "(5) Flughafen Frankfurt am Main",
        "(6) Flughafen Berlin-Tegel",
        
        # Italian airports
        "(7) Aeroporto di Roma-Fiumicino",
        "(8) Aeroporto di Milano-Malpensa",
        "(9) Aeroporto di Venezia Marco Polo",
        
        # Spanish airports
        "(10) Aeropuerto de Madrid-Barajas",
        "(11) Aeropuerto de Barcelona-El Prat",
        "(12) Aeropuerto de Málaga-Costa del Sol",
        
        # Dutch airports
        "(13) Luchthaven Schiphol",
        "(14) Luchthaven Rotterdam The Hague",
        
        # Scandinavian airports
        "(15) Københavns Lufthavn",  # Danish
        "(16) Stockholm Arlanda flygplats",  # Swedish
        "(17) Oslo lufthavn",  # Norwegian
        
        # Eastern European airports
        "(18) Lotnisko Chopina w Warszawie",  # Polish
        "(19) Letiště Václava Havla Praha",  # Czech
        "(20) Liszt Ferenc Nemzetközi Repülőtér",  # Hungarian
        
        # Edge cases
        "(21) Airport with numbers 123",
        "(22) Airport with symbols @#$%",
        "(23) Airport with parentheses (internal)",
        "(24) Airport with brackets [internal]",
        "(25) Airport with quotes \"internal\"",
        
        # Different number formats
        "1) Simple format",
        "2. Period format",
        "3 - Dash format",
        "(4) Standard format",
    ]
    
    print("Testing BorderCrossingParser with unicode and special characters")
    print("=" * 70)
    
    all_extracted = set()
    
    for i, test_case in enumerate(test_cases, 1):
        names = parser._extract_names_from_text(test_case)
        print(f"Test {i:2d}: {test_case}")
        print(f"       Extracted: {list(names)}")
        all_extracted.update(names)
        print()
    
    print(f"Total unique names extracted: {len(all_extracted)}")
    print("All extracted names:")
    for name in sorted(all_extracted):
        print(f"  - {name}")

def test_edge_cases():
    """Test edge cases and error handling."""
    
    parser = BorderCrossingParser()
    
    edge_cases = [
        "",  # Empty string
        "(1)",  # Just number, no name
        "(1) ",  # Number with space, no name
        "(1) A",  # Very short name
        "(1) Airport Name\n(2) Another Airport",  # Multiple lines
        "(1) Airport Name, (2) Another Airport",  # Multiple on same line
        "No number Airport Name",  # No number pattern
        "(abc) Airport Name",  # Non-numeric number
        "(1 Airport Name",  # Missing closing parenthesis
        "1) Airport Name",  # Missing opening parenthesis
    ]
    
    print("\nTesting edge cases:")
    print("-" * 40)
    
    for i, test_case in enumerate(edge_cases, 1):
        names = parser._extract_names_from_text(test_case)
        print(f"Edge case {i:2d}: '{test_case}'")
        print(f"            Extracted: {list(names)}")
        print()

def test_bulk_text():
    """Test with a larger block of text containing multiple entries."""
    
    parser = BorderCrossingParser()
    
    bulk_text = """
    Border Crossing Airports:
    
    (1) Charles de Gaulle Airport, Paris
    (2) Orly Airport, Paris
    (3) Nice Côte d'Azur Airport
    (4) Lyon-Saint Exupéry Airport
    (5) Marseille Provence Airport
    (6) Toulouse-Blagnac Airport
    (7) Bordeaux-Mérignac Airport
    (8) Nantes Atlantique Airport
    (9) Strasbourg Airport
    (10) Montpellier-Méditerranée Airport
    
    Additional airports:
    11) Lille Airport
    12. Brest Bretagne Airport
    13 - Clermont-Ferrand Airport
    """
    
    print("\nTesting bulk text extraction:")
    print("-" * 40)
    
    names = parser._extract_names_from_text(bulk_text)
    print("Extracted names:")
    for i, name in enumerate(sorted(names), 1):
        print(f"  {i:2d}. {name}")

if __name__ == "__main__":
    test_unicode_and_special_characters()
    test_edge_cases()
    test_bulk_text() 