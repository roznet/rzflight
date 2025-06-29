"""
Tests for field standardization functionality.

This module tests the FieldStandardizationService and related functionality
for standardizing AIP field names across different sources.
"""

import json
import unittest
from pathlib import Path
from typing import List, Dict, Any

from euro_aip.models import EuroAipModel, Airport, AIPEntry
from euro_aip.utils.field_standardization_service import FieldStandardizationService


class TestFieldStandardization(unittest.TestCase):
    """Test cases for field standardization functionality."""
    
    @classmethod
    def setUpClass(cls):
        """Set up test data once for all tests."""
        cls.assets_dir = Path(__file__).parent.parent / "assets"
        
        # Load test data
        with open(cls.assets_dir / "test_field_standardization_data.json") as f:
            cls.test_data = json.load(f)
        
        with open(cls.assets_dir / "test_field_standardization_edge_cases.json") as f:
            cls.edge_case_data = json.load(f)
        
        # Create field standardization service
        cls.field_service = FieldStandardizationService()
    
    def setUp(self):
        """Set up each test case."""
        self.model = EuroAipModel()
    
    def test_field_standardization_service_creation(self):
        """Test that FieldStandardizationService can be created."""
        service = FieldStandardizationService()
        self.assertIsNotNone(service)
        self.assertIsInstance(service, FieldStandardizationService)
    
    def test_basic_field_standardization(self):
        """Test basic field standardization with known fields."""
        # Create test entries from test data
        test_entries = []
        for entry_data in self.test_data["test_entries"]:
            entry = AIPEntry(
                ident=entry_data["ident"],
                section=entry_data["section"],
                field=entry_data["field"],
                value=entry_data["value"]
            )
            test_entries.append(entry)
        
        # Standardize entries
        standardized_entries = self.field_service.standardize_aip_entries(test_entries)
        
        # Verify results
        self.assertEqual(len(standardized_entries), len(test_entries))
        
        for i, entry in enumerate(standardized_entries):
            expected_data = self.test_data["test_entries"][i]
            
            if expected_data["expected_std_field"]:
                # Should be standardized
                self.assertTrue(entry.is_standardized())
                self.assertEqual(entry.std_field, expected_data["expected_std_field"])
                self.assertGreaterEqual(entry.mapping_score, expected_data["expected_score"])
            else:
                # Should not be standardized
                self.assertFalse(entry.is_standardized())
                self.assertIsNone(entry.std_field)
                self.assertIsNone(entry.mapping_score)
    
    def test_field_standardization_statistics(self):
        """Test field standardization statistics calculation."""
        # Create test entries
        test_entries = []
        for entry_data in self.test_data["test_entries"]:
            entry = AIPEntry(
                ident=entry_data["ident"],
                section=entry_data["section"],
                field=entry_data["field"],
                value=entry_data["value"]
            )
            test_entries.append(entry)
        
        # Standardize entries
        standardized_entries = self.field_service.standardize_aip_entries(test_entries)
        
        # Get statistics
        stats = self.field_service.get_mapping_statistics(standardized_entries)
        expected_stats = self.test_data["expected_statistics"]
        
        # Verify statistics
        self.assertEqual(stats["total_fields"], expected_stats["total_fields"])
        self.assertEqual(stats["mapped_fields"], expected_stats["mapped_fields"])
        self.assertEqual(stats["unmapped_fields"], expected_stats["unmapped_fields"])
        self.assertAlmostEqual(stats["mapping_rate"], expected_stats["mapping_rate"], places=3)
        self.assertAlmostEqual(stats["average_mapping_score"], expected_stats["average_mapping_score"], places=2)
    
    def test_edge_case_field_standardization(self):
        """Test field standardization with edge cases."""
        # Create test entries from edge case data
        test_entries = []
        for entry_data in self.edge_case_data["edge_case_entries"]:
            entry = AIPEntry(
                ident=entry_data["ident"],
                section=entry_data["section"],
                field=entry_data["field"],
                value=entry_data["value"]
            )
            test_entries.append(entry)
        
        # Standardize entries
        standardized_entries = self.field_service.standardize_aip_entries(test_entries)
        
        # Verify results
        self.assertEqual(len(standardized_entries), len(test_entries))
        
        for i, entry in enumerate(standardized_entries):
            expected_data = self.edge_case_data["edge_case_entries"][i]
            
            if expected_data["expected_std_field"]:
                # Should be standardized
                self.assertTrue(entry.is_standardized(), 
                              f"Field '{entry.field}' should be standardized: {expected_data['description']}")
                self.assertEqual(entry.std_field, expected_data["expected_std_field"])
                self.assertGreaterEqual(entry.mapping_score, expected_data["expected_score"])
            else:
                # Should not be standardized
                self.assertFalse(entry.is_standardized(),
                               f"Field '{entry.field}' should not be standardized: {expected_data['description']}")
                self.assertIsNone(entry.std_field)
                self.assertIsNone(entry.mapping_score)
    
    def test_airport_field_standardization_integration(self):
        """Test field standardization integration with Airport model."""
        # Create test entries
        test_entries = []
        for entry_data in self.test_data["test_entries"]:
            entry = AIPEntry(
                ident=entry_data["ident"],
                section=entry_data["section"],
                field=entry_data["field"],
                value=entry_data["value"]
            )
            test_entries.append(entry)
        
        # Standardize entries
        standardized_entries = self.field_service.standardize_aip_entries(test_entries)
        
        # Create airport and add entries
        airport = Airport(ident="LFAT")
        airport.add_aip_entries(standardized_entries)
        airport.add_source("test")
        
        # Verify airport methods
        self.assertEqual(len(airport.aip_entries), len(test_entries))
        self.assertEqual(len(airport.get_standardized_entries()), 
                        self.test_data["expected_statistics"]["mapped_fields"])
        self.assertEqual(len(airport.get_unstandardized_entries()), 
                        self.test_data["expected_statistics"]["unmapped_fields"])
        
        # Test getting standardized data
        std_data = airport.get_standardized_aip_data()
        self.assertIsInstance(std_data, dict)
        self.assertGreater(len(std_data), 0)
    
    def test_model_field_standardization_integration(self):
        """Test field standardization integration with EuroAipModel."""
        # Create test entries
        test_entries = []
        for entry_data in self.test_data["test_entries"]:
            entry = AIPEntry(
                ident=entry_data["ident"],
                section=entry_data["section"],
                field=entry_data["field"],
                value=entry_data["value"]
            )
            test_entries.append(entry)
        
        # Standardize entries
        standardized_entries = self.field_service.standardize_aip_entries(test_entries)
        
        # Create airport and add to model
        airport = Airport(ident="LFAT")
        airport.add_aip_entries(standardized_entries)
        airport.add_source("test")
        
        self.model.add_airport(airport)
        
        # Test model statistics
        model_stats = self.model.get_field_mapping_statistics()
        expected_stats = self.test_data["expected_statistics"]
        
        self.assertEqual(model_stats["total_fields"], expected_stats["total_fields"])
        self.assertEqual(model_stats["mapped_fields"], expected_stats["mapped_fields"])
        self.assertEqual(model_stats["unmapped_fields"], expected_stats["unmapped_fields"])
        self.assertAlmostEqual(model_stats["mapping_rate"], expected_stats["mapping_rate"], places=3)
    
    def test_empty_entries_standardization(self):
        """Test standardization with empty entries list."""
        empty_entries = []
        standardized_entries = self.field_service.standardize_aip_entries(empty_entries)
        
        self.assertEqual(len(standardized_entries), 0)
        
        # Test statistics with empty list
        stats = self.field_service.get_mapping_statistics(standardized_entries)
        self.assertEqual(stats["total_fields"], 0)
        self.assertEqual(stats["mapped_fields"], 0)
        self.assertEqual(stats["unmapped_fields"], 0)
        self.assertEqual(stats["mapping_rate"], 0.0)
        self.assertEqual(stats["average_mapping_score"], 0.0)
    
    def test_single_entry_standardization(self):
        """Test standardization with a single entry."""
        entry = AIPEntry(
            ident="LFAT",
            section="admin",
            field="AD Administration",
            value="Le Touquet-Paris-Plage Administration"
        )
        
        standardized_entries = self.field_service.standardize_aip_entries([entry])
        
        self.assertEqual(len(standardized_entries), 1)
        standardized_entry = standardized_entries[0]
        
        self.assertTrue(standardized_entry.is_standardized())
        self.assertEqual(standardized_entry.std_field, "AD Administration")
        self.assertGreater(standardized_entry.mapping_score, 0.0)
    
    def test_field_standardization_persistence(self):
        """Test that standardized fields persist through serialization."""
        # Create and standardize entry
        entry = AIPEntry(
            ident="LFAT",
            section="admin",
            field="AD Administration",
            value="Le Touquet-Paris-Plage Administration"
        )
        
        standardized_entries = self.field_service.standardize_aip_entries([entry])
        standardized_entry = standardized_entries[0]
        
        # Serialize and deserialize
        entry_dict = standardized_entry.to_dict()
        deserialized_entry = AIPEntry.from_dict(entry_dict)
        
        # Verify standardization persists
        self.assertEqual(deserialized_entry.std_field, standardized_entry.std_field)
        self.assertEqual(deserialized_entry.mapping_score, standardized_entry.mapping_score)
        self.assertEqual(deserialized_entry.is_standardized(), standardized_entry.is_standardized())


class TestFieldStandardizationPerformance(unittest.TestCase):
    """Performance tests for field standardization."""
    
    def setUp(self):
        """Set up each test case."""
        self.field_service = FieldStandardizationService()
    
    def test_large_batch_standardization(self):
        """Test standardization performance with large batch of entries."""
        # Create a large batch of test entries
        large_batch = []
        for i in range(100):
            entry = AIPEntry(
                ident=f"TEST{i:03d}",
                section="admin",
                field=f"Test Field {i}",
                value=f"Test Value {i}"
            )
            large_batch.append(entry)
        
        # Time the standardization
        import time
        start_time = time.time()
        standardized_entries = self.field_service.standardize_aip_entries(large_batch)
        end_time = time.time()
        
        # Verify results
        self.assertEqual(len(standardized_entries), len(large_batch))
        
        # Performance assertion (should complete within reasonable time)
        processing_time = end_time - start_time
        self.assertLess(processing_time, 1.0, f"Standardization took {processing_time:.3f}s, should be under 1s")


if __name__ == '__main__':
    unittest.main() 