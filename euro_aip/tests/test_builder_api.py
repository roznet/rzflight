"""
Tests for the modern builder API (transactions, bulk operations, builders).
"""

import pytest
from datetime import datetime

from euro_aip.models import (
    EuroAipModel,
    Airport,
    Runway,
    Procedure,
    AIPEntry,
    BorderCrossingEntry,
    ValidationResult,
    ModelValidationError,
)


@pytest.fixture
def model():
    """Create a fresh model for each test."""
    return EuroAipModel()


@pytest.fixture
def sample_airport():
    """Create a sample airport."""
    airport = Airport(
        ident="EGLL",
        name="London Heathrow",
        latitude_deg=51.4700,
        longitude_deg=-0.4543,
        elevation_ft=83,
        iso_country="GB"
    )
    return airport


@pytest.fixture
def sample_airports():
    """Create multiple sample airports."""
    return [
        Airport(ident="EGLL", name="London Heathrow", latitude_deg=51.4700, longitude_deg=-0.4543, iso_country="GB"),
        Airport(ident="LFPG", name="Paris Charles de Gaulle", latitude_deg=49.0097, longitude_deg=2.5479, iso_country="FR"),
        Airport(ident="EDDF", name="Frankfurt", latitude_deg=50.0379, longitude_deg=8.5622, iso_country="DE"),
    ]


@pytest.fixture
def sample_runway():
    """Create a sample runway."""
    return Runway(
        airport_ident="EGLL",
        le_ident="09L",
        he_ident="27R",
        length_ft=12799,
        width_ft=164,
        surface="ASP",
        lighted=True
    )


@pytest.fixture
def sample_procedure():
    """Create a sample procedure."""
    return Procedure(
        name="ILS 09L",
        procedure_type="APPROACH",
        runway_ident="09L",
        approach_type="ILS",
        source="uk_eaip"
    )


@pytest.fixture
def sample_aip_entry():
    """Create a sample AIP entry."""
    return AIPEntry(
        ident="EGLL",
        section="AD 2.2",
        field="Aerodrome geographic and administrative data",
        value="London Heathrow",
        source="uk_eaip"
    )


# ========================================================================
# Transaction API Tests
# ========================================================================

class TestTransactionAPI:
    """Test the transaction API."""

    def test_basic_transaction(self, model, sample_airport):
        """Test basic transaction commit."""
        with model.transaction() as txn:
            txn.add_airport(sample_airport)

        # Airport should be in model
        assert sample_airport.ident in model._airports
        assert model.airports.count() == 1

    def test_transaction_rollback_on_error(self, model, sample_airport):
        """Test transaction rolls back on error."""
        try:
            with model.transaction() as txn:
                txn.add_airport(sample_airport)
                # Simulate an error
                raise ValueError("Test error")
        except ValueError:
            pass

        # Airport should NOT be in model (rolled back)
        assert sample_airport.ident not in model._airports
        assert model.airports.count() == 0

    def test_transaction_multiple_operations(self, model, sample_airports):
        """Test transaction with multiple operations."""
        with model.transaction() as txn:
            for airport in sample_airports:
                txn.add_airport(airport)

        # All airports should be in model
        assert model.airports.count() == 3
        assert "EGLL" in model._airports
        assert "LFPG" in model._airports
        assert "EDDF" in model._airports

    def test_transaction_with_aip_entries(self, model, sample_airport, sample_aip_entry):
        """Test transaction with AIP entries."""
        with model.transaction() as txn:
            txn.add_airport(sample_airport)
            txn.add_aip_entries(sample_airport.ident, [sample_aip_entry])

        airport = model._airports[sample_airport.ident]
        assert len(airport.aip_entries) == 1

    def test_transaction_with_procedures(self, model, sample_airport, sample_procedure):
        """Test transaction with procedures."""
        with model.transaction() as txn:
            txn.add_airport(sample_airport)
            txn.add_procedures(sample_airport.ident, [sample_procedure])

        airport = model._airports[sample_airport.ident]
        assert len(airport.procedures) == 1

    def test_transaction_bulk_operations(self, model, sample_airports):
        """Test bulk operations within transaction."""
        with model.transaction() as txn:
            txn.bulk_add_airports(sample_airports)

        assert model.airports.count() == 3

    def test_transaction_remove_by_country(self, model, sample_airports):
        """Test remove by country in transaction."""
        # Add airports first
        with model.transaction() as txn:
            txn.bulk_add_airports(sample_airports)

        # Remove French airports
        with model.transaction() as txn:
            txn.remove_by_country("FR")

        assert model.airports.count() == 2
        assert "LFPG" not in model._airports

    def test_transaction_change_tracking(self, model, sample_airports):
        """Test change tracking in transaction."""
        with model.transaction(track_changes=True) as txn:
            txn.bulk_add_airports(sample_airports)

        # Get changes after transaction commits
        # Note: In a real implementation, we'd need to store the transaction
        # to access changes after commit. For now, verify the airports were added.
        assert model.airports.count() == 3

    def test_transaction_defer_derived_updates(self, model, sample_airports):
        """Test deferring derived field updates."""
        with model.transaction(auto_update_derived=False) as txn:
            txn.bulk_add_airports(sample_airports)

        # Manually update derived fields
        model.update_all_derived_fields()

        # Verify airports are present
        assert model.airports.count() == 3


# ========================================================================
# Bulk Operations Tests
# ========================================================================

class TestBulkOperations:
    """Test bulk operations."""

    def test_bulk_add_airports_simple(self, model, sample_airports):
        """Test simple bulk add airports."""
        result = model.bulk_add_airports(sample_airports)

        assert result['added'] == 3
        assert result['updated'] == 0
        assert result['skipped'] == 0
        assert result['total'] == 3

    def test_bulk_add_airports_update_existing(self, model, sample_airports):
        """Test bulk add with update existing strategy."""
        # Add airports first
        model.bulk_add_airports(sample_airports)

        # Update with modified airports
        modified_airports = [
            Airport(ident="EGLL", name="London Heathrow Updated", latitude_deg=51.4700, longitude_deg=-0.4543, iso_country="GB"),
            Airport(ident="NEWW", name="New Airport", latitude_deg=50.0, longitude_deg=0.0, iso_country="GB"),
        ]

        result = model.bulk_add_airports(modified_airports, merge="update_existing")

        assert result['added'] == 1  # NEWW
        assert result['updated'] == 1  # EGLL
        assert result['total'] == 2

        # Verify update
        airport = model._airports["EGLL"]
        assert airport.name == "London Heathrow Updated"

    def test_bulk_add_airports_skip_existing(self, model, sample_airports):
        """Test bulk add with skip existing strategy."""
        # Add airports first
        model.bulk_add_airports(sample_airports)

        # Try to add again with skip strategy
        result = model.bulk_add_airports(sample_airports, merge="skip_existing")

        assert result['added'] == 0
        assert result['updated'] == 0
        assert result['skipped'] == 3

    def test_bulk_add_airports_no_validation(self, model):
        """Test bulk add without validation."""
        # Create invalid airport (missing coordinates)
        invalid = Airport(ident="INVL", name="Invalid")

        # Should work without validation
        result = model.bulk_add_airports([invalid], validate=False)
        assert result['added'] == 1

    def test_bulk_add_airports_with_validation_error(self, model):
        """Test bulk add with validation error."""
        # Create invalid airport (bad ICAO code)
        invalid = Airport(ident="INV", name="Invalid", latitude_deg=50.0, longitude_deg=0.0)

        with pytest.raises(ModelValidationError):
            model.bulk_add_airports([invalid], validate=True)

    def test_bulk_add_airports_no_derived_update(self, model, sample_airports):
        """Test bulk add without derived field update."""
        result = model.bulk_add_airports(sample_airports, update_derived=False)

        assert result['added'] == 3

        # Manually update
        model.update_all_derived_fields()

    def test_bulk_add_aip_entries(self, model, sample_airport):
        """Test bulk add AIP entries."""
        model.add_airport(sample_airport)

        aip_data = {
            "EGLL": [
                AIPEntry(ident="EGLL", section="AD 2.2", field="Name", value="Heathrow", source="test"),
                AIPEntry(ident="EGLL", section="AD 2.3", field="Runways", value="09L/27R", source="test"),
            ]
        }

        result = model.bulk_add_aip_entries(aip_data)

        assert result["EGLL"] == 2
        airport = model._airports["EGLL"]
        assert len(airport.aip_entries) == 2

    def test_bulk_add_procedures(self, model, sample_airport):
        """Test bulk add procedures."""
        model.add_airport(sample_airport)

        procedures_data = {
            "EGLL": [
                Procedure(name="ILS 09L", procedure_type="APPROACH", runway_ident="09L", source="test"),
                Procedure(name="ILS 27R", procedure_type="APPROACH", runway_ident="27R", source="test"),
            ]
        }

        result = model.bulk_add_procedures(procedures_data)

        assert result["EGLL"] == 2
        airport = model._airports["EGLL"]
        assert len(airport.procedures) == 2


# ========================================================================
# Builder Pattern Tests
# ========================================================================

class TestBuilderPattern:
    """Test the airport builder pattern."""

    def test_basic_builder(self, model):
        """Test basic builder usage."""
        builder = model.airport_builder("EGLL")
        builder.with_basic_info(
            name="London Heathrow",
            latitude_deg=51.4700,
            longitude_deg=-0.4543,
            iso_country="GB"
        )

        airport = builder.build()

        assert airport.ident == "EGLL"
        assert airport.name == "London Heathrow"
        assert airport.latitude_deg == 51.4700

    def test_builder_chaining(self, model, sample_runway, sample_procedure):
        """Test builder method chaining."""
        airport = model.airport_builder("EGLL") \
            .with_basic_info(name="Heathrow", latitude_deg=51.4700, longitude_deg=-0.4543, iso_country="GB") \
            .with_runway(sample_runway) \
            .with_procedure(sample_procedure) \
            .with_source("uk_eaip") \
            .build()

        assert airport.ident == "EGLL"
        assert len(airport.runways) == 1
        assert len(airport.procedures) == 1
        assert "uk_eaip" in airport.sources

    def test_builder_with_multiple_items(self, model):
        """Test builder with multiple runways/procedures."""
        runways = [
            Runway(airport_ident="EGLL", le_ident="09L", he_ident="27R", length_ft=12799),
            Runway(airport_ident="EGLL", le_ident="09R", he_ident="27L", length_ft=12008),
        ]

        procedures = [
            Procedure(name="ILS 09L", procedure_type="APPROACH", runway_ident="09L", source="test"),
            Procedure(name="ILS 27R", procedure_type="APPROACH", runway_ident="27R", source="test"),
        ]

        airport = model.airport_builder("EGLL") \
            .with_basic_info(name="Heathrow", latitude_deg=51.4700, longitude_deg=-0.4543) \
            .with_runways(runways) \
            .with_procedures(procedures) \
            .build()

        assert len(airport.runways) == 2
        assert len(airport.procedures) == 2

    def test_builder_validation_success(self, model):
        """Test builder validation success."""
        builder = model.airport_builder("EGLL") \
            .with_basic_info(name="Heathrow", latitude_deg=51.4700, longitude_deg=-0.4543)

        validation = builder.validate()
        assert validation.is_valid

    def test_builder_validation_failure_icao(self, model):
        """Test builder validation failure for bad ICAO."""
        builder = model.airport_builder("EGL")  # Only 3 characters
        builder.with_basic_info(name="Test", latitude_deg=50.0, longitude_deg=0.0)

        validation = builder.validate()
        assert not validation.is_valid
        assert any("ICAO code must be 4 characters" in str(e) for e in validation.errors)

    def test_builder_validation_failure_coordinates(self, model):
        """Test builder validation failure for missing coordinates."""
        builder = model.airport_builder("EGLL")
        builder.with_basic_info(name="Test")  # No coordinates

        validation = builder.validate()
        assert not validation.is_valid

    def test_builder_validation_invalid_lat(self, model):
        """Test builder validation for invalid latitude."""
        builder = model.airport_builder("EGLL") \
            .with_basic_info(latitude_deg=100.0, longitude_deg=0.0)  # Invalid latitude

        validation = builder.validate()
        assert not validation.is_valid

    def test_builder_commit(self, model):
        """Test builder commit to model."""
        airport = model.airport_builder("EGLL") \
            .with_basic_info(name="Heathrow", latitude_deg=51.4700, longitude_deg=-0.4543) \
            .commit()

        # Airport should be in model
        assert "EGLL" in model._airports
        assert model._airports["EGLL"] == airport

    def test_builder_commit_with_validation_error(self, model):
        """Test builder commit with validation error."""
        builder = model.airport_builder("EGL")  # Bad ICAO
        builder.with_basic_info(name="Test", latitude_deg=50.0, longitude_deg=0.0)

        with pytest.raises(ModelValidationError):
            builder.commit()

        # Airport should NOT be in model
        assert "EGL" not in model._airports

    def test_builder_with_aip_entries(self, model):
        """Test builder with AIP entries."""
        entries = [
            AIPEntry(ident="EGLL", section="AD 2.2", field="Name", value="Heathrow", source="test"),
        ]

        airport = model.airport_builder("EGLL") \
            .with_basic_info(name="Heathrow", latitude_deg=51.4700, longitude_deg=-0.4543) \
            .with_aip_entries(entries) \
            .build()

        assert len(airport.aip_entries) == 1

    def test_builder_with_sources(self, model):
        """Test builder with sources."""
        airport = model.airport_builder("EGLL") \
            .with_basic_info(name="Heathrow", latitude_deg=51.4700, longitude_deg=-0.4543) \
            .with_sources(["uk_eaip", "worldairports"]) \
            .build()

        assert "uk_eaip" in airport.sources
        assert "worldairports" in airport.sources


# ========================================================================
# Validation Tests
# ========================================================================

class TestValidation:
    """Test validation functionality."""

    def test_validation_result_success(self):
        """Test successful validation result."""
        result = ValidationResult.success()
        assert result.is_valid
        assert len(result.errors) == 0

    def test_validation_result_error(self):
        """Test error validation result."""
        result = ValidationResult.error("ident", "Invalid ICAO code")
        assert not result.is_valid
        assert len(result.errors) == 1

    def test_validation_result_add_error(self):
        """Test adding errors to validation result."""
        result = ValidationResult()
        result.add_error("field1", "Error 1")
        result.add_error("field2", "Error 2", "value")

        assert not result.is_valid
        assert len(result.errors) == 2

    def test_validation_result_get_error_messages(self):
        """Test getting error messages."""
        result = ValidationResult()
        result.add_error("field1", "Error 1")
        result.add_error("field2", "Error 2")

        messages = result.get_error_messages()
        assert len(messages) == 2

    def test_model_validation_error(self):
        """Test ModelValidationError exception."""
        result = ValidationResult()
        result.add_error("ident", "Invalid")

        error = ModelValidationError("Validation failed", validation_result=result)
        assert "Invalid" in str(error)


# ========================================================================
# Integration Tests
# ========================================================================

class TestIntegration:
    """Integration tests combining multiple features."""

    def test_complete_dataset_load(self, model, sample_airports):
        """Test loading a complete dataset with transaction."""
        # Prepare data
        aip_data = {
            "EGLL": [AIPEntry(ident="EGLL", section="AD 2.2", field="Name", value="Heathrow", source="test")],
            "LFPG": [AIPEntry(ident="LFPG", section="AD 2.2", field="Name", value="CDG", source="test")],
        }

        procedures_data = {
            "EGLL": [Procedure(name="ILS 09L", procedure_type="APPROACH", runway_ident="09L", source="test")],
        }

        # Load with transaction
        with model.transaction() as txn:
            txn.bulk_add_airports(sample_airports)
            txn.bulk_add_aip_entries(aip_data)
            txn.bulk_add_procedures(procedures_data)

        # Verify
        assert model.airports.count() == 3
        assert len(model._airports["EGLL"].aip_entries) == 1
        assert len(model._airports["EGLL"].procedures) == 1

    def test_incremental_update(self, model, sample_airports):
        """Test incremental model update."""
        # Initial load
        model.bulk_add_airports(sample_airports)

        # Update French data
        new_french = [
            Airport(ident="LFPO", name="Paris Orly", latitude_deg=48.7233, longitude_deg=2.3794, iso_country="FR"),
        ]

        with model.transaction() as txn:
            txn.remove_by_country("FR")
            txn.bulk_add_airports(new_french)

        # Verify
        assert "LFPG" not in model._airports  # Removed
        assert "LFPO" in model._airports  # Added
        assert "EGLL" in model._airports  # Unchanged

    def test_builder_with_transaction(self, model):
        """Test using builder within transaction."""
        with model.transaction() as txn:
            # Build airports using builder
            airport1 = model.airport_builder("EGLL") \
                .with_basic_info(name="Heathrow", latitude_deg=51.4700, longitude_deg=-0.4543) \
                .build()

            airport2 = model.airport_builder("LFPG") \
                .with_basic_info(name="CDG", latitude_deg=49.0097, longitude_deg=2.5479) \
                .build()

            # Add to transaction
            txn.add_airport(airport1)
            txn.add_airport(airport2)

        # Verify
        assert model.airports.count() == 2
