#!/usr/bin/env python3

"""
Test script to verify that get_source_name correctly removes Source suffixes
and returns a single lowercase word (no underscores).
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from euro_aip.sources.base import SourceInterface
from euro_aip.sources.france_eaip import FranceEAIPSource
from euro_aip.sources.uk_eaip import UKEAIPSource
from euro_aip.sources.autorouter import AutorouterSource
from euro_aip.sources.worldairports import WorldAirportsSource

def test_source_names():
    """Test that source names are generated correctly."""
    
    print("=== Testing Source Name Generation ===\n")
    
    # Create instances with minimal initialization for testing
    import tempfile
    temp_dir = tempfile.mkdtemp()
    
    try:
        france_source = FranceEAIPSource(temp_dir, temp_dir)
        uk_source = UKEAIPSource(temp_dir, temp_dir)
        autorouter_source = AutorouterSource(temp_dir)
        worldairports_source = WorldAirportsSource(temp_dir)
        
        # Test cases
        test_cases = [
            (france_source, "FranceEAIPSource", "franceeaip"),
            (uk_source, "UKEAIPSource", "ukeaip"),
            (autorouter_source, "AutorouterSource", "autorouter"),
            (worldairports_source, "WorldAirportsSource", "worldairports"),
        ]
        
        print("Testing automatic source name generation:")
        print("Class Name -> Expected Source Name")
        print("-" * 50)
        
        all_passed = True
        
        for instance, class_name, expected in test_cases:
            actual = instance.get_source_name()
            status = "✅" if actual == expected else "❌"
            print(f"{status} {class_name} -> {actual}")
            
            if actual != expected:
                print(f"   Expected: {expected}")
                all_passed = False
        
        print(f"\nOverall Result: {'✅ PASSED' if all_passed else '❌ FAILED'}")
        
    finally:
        import shutil
        shutil.rmtree(temp_dir, ignore_errors=True)
    
    # Test edge cases
    print("\n=== Testing Edge Cases ===")
    
    class TestSource(SourceInterface):
        def update_model(self, model, airports=None):
            pass
    
    class NoSourceSuffix(SourceInterface):
        def update_model(self, model, airports=None):
            pass
    
    class MultipleWordsSource(SourceInterface):
        def update_model(self, model, airports=None):
            pass
    
    edge_cases = [
        (TestSource(), "TestSource", "test"),
        (NoSourceSuffix(), "NoSourceSuffix", "nosourcesuffix"),
        (MultipleWordsSource(), "MultipleWordsSource", "multiplewordssource"),
    ]
    
    print("\nTesting edge cases:")
    for instance, class_name, expected in edge_cases:
        actual = instance.get_source_name()
        status = "✅" if actual == expected else "❌"
        print(f"{status} {class_name} -> {actual}")
        
        if actual != expected:
            print(f"   Expected: {expected}")
            all_passed = False
    
    return all_passed

def test_camel_case_conversion():
    """Test camelCase to single lowercase word conversion (no underscores)."""
    
    print("\n=== Testing CamelCase to Lowercase Conversion ===")
    
    test_patterns = [
        ("SimpleSource", "simple"),
        ("TwoWordsSource", "twowords"),
        ("MultipleWordsHereSource", "multiplewordshere"),
        ("WithNumbers123Source", "withnumbers123"),
        ("UPPERCaseSource", "uppercase"),
        ("lowerCaseSource", "lowercase"),
        ("MixedCASEsource", "mixedcasesource"),
        ("EAIPSource", "eaip"),
        ("FranceEAIPSource", "franceeaip"),
        ("WorldAirportsSource", "worldairports"),
    ]
    
    print("Testing camelCase to lowercase conversion:")
    print("Input -> Expected Output")
    print("-" * 40)
    
    all_passed = True
    
    for input_name, expected in test_patterns:
        test_class = type(input_name, (SourceInterface,), {
            'update_model': lambda self, model, airports=None: None
        })
        
        instance = test_class()
        actual = instance.get_source_name()
        status = "✅" if actual == expected else "❌"
        print(f"{status} {input_name} -> {actual}")
        
        if actual != expected:
            print(f"   Expected: {expected}")
            all_passed = False
    
    return all_passed

if __name__ == "__main__":
    print("Testing Source Name Generation\n")
    
    test1_passed = test_source_names()
    test2_passed = test_camel_case_conversion()
    
    print(f"\n=== Final Results ===")
    print(f"Source Name Tests: {'✅ PASSED' if test1_passed else '❌ FAILED'}")
    print(f"CamelCase Tests: {'✅ PASSED' if test2_passed else '❌ FAILED'}")
    
    if test1_passed and test2_passed:
        print("\n🎉 All tests passed! The get_source_name method is working correctly.")
    else:
        print("\n❌ Some tests failed. Please check the implementation.") 