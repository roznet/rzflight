"""
Model transaction support for safe, atomic updates.

This module provides the ModelTransaction context manager that allows
batch operations on the EuroAipModel with automatic rollback on failure
and automatic derived field updates on success.
"""

from typing import TYPE_CHECKING, List, Dict, Any, Optional
import logging
import copy

from .validation import ValidationResult, ModelValidationError
from .airport import Airport
from .aip_entry import AIPEntry
from .procedure import Procedure
from .border_crossing_entry import BorderCrossingEntry

if TYPE_CHECKING:
    from .euro_aip_model import EuroAipModel

logger = logging.getLogger(__name__)


class ModelTransaction:
    """
    Context manager for safe, atomic model updates.

    Provides transaction safety with automatic rollback on error and
    automatic derived field updates on success.

    Examples:
        Basic transaction:
        >>> with model.transaction() as txn:
        ...     txn.add_airport(airport)
        ...     txn.add_aip_entries("EGLL", entries)

        Multiple operations:
        >>> with model.transaction() as txn:
        ...     for airport in airports:
        ...         txn.add_airport(airport)
        ...     txn.remove_by_country("XX")

        Without auto-update of derived fields:
        >>> with model.transaction(auto_update_derived=False) as txn:
        ...     txn.bulk_add_airports(many_airports)
        ... model.update_all_derived_fields()  # Manual update later
    """

    def __init__(self, model: 'EuroAipModel', auto_update_derived: bool = True, track_changes: bool = False):
        """
        Initialize transaction.

        Args:
            model: The EuroAipModel to operate on
            auto_update_derived: Whether to automatically update derived fields on commit
            track_changes: Whether to track changes for reporting
        """
        self.model = model
        self.auto_update_derived = auto_update_derived
        self.track_changes = track_changes
        self._snapshot = None
        self._changes: List[Dict[str, Any]] = []
        self._change_summary = {
            'added_airports': [],
            'updated_airports': [],
            'removed_airports': [],
            'added_procedures': 0,
            'added_aip_entries': 0,
            'added_border_crossings': 0
        }

    def __enter__(self):
        """Enter transaction context."""
        self._snapshot = self._create_snapshot()
        logger.debug("Started transaction")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit transaction context."""
        if exc_type is not None:
            # Exception occurred - rollback
            logger.error(f"Transaction failed: {exc_val}, rolling back")
            self._rollback()
            return False  # Re-raise exception
        else:
            # Success - commit
            try:
                self._commit()
                logger.debug("Transaction committed successfully")
                return True
            except Exception as e:
                logger.error(f"Commit failed: {e}, rolling back")
                self._rollback()
                raise

    def add_airport(self, airport: Airport, merge: str = "update_existing") -> None:
        """
        Add airport to transaction.

        Args:
            airport: Airport to add
            merge: Merge strategy - "update_existing", "skip_existing", "replace"
        """
        self._changes.append({
            "operation": "add_airport",
            "airport": airport,
            "merge": merge
        })

    def add_aip_entries(self, icao: str, entries: List[AIPEntry], standardize: bool = True) -> None:
        """
        Add AIP entries to transaction.

        Args:
            icao: Airport ICAO code
            entries: List of AIP entries to add
            standardize: Whether to standardize entries
        """
        self._changes.append({
            "operation": "add_aip_entries",
            "icao": icao,
            "entries": entries,
            "standardize": standardize
        })

    def add_procedures(self, icao: str, procedures: List[Procedure]) -> None:
        """
        Add procedures to transaction.

        Args:
            icao: Airport ICAO code
            procedures: List of procedures to add
        """
        self._changes.append({
            "operation": "add_procedures",
            "icao": icao,
            "procedures": procedures
        })

    def bulk_add_airports(self, airports: List[Airport], merge: str = "update_existing") -> None:
        """
        Bulk add airports to transaction.

        Args:
            airports: List of airports to add
            merge: Merge strategy
        """
        self._changes.append({
            "operation": "bulk_add_airports",
            "airports": airports,
            "merge": merge
        })

    def bulk_add_aip_entries(self, entries_by_icao: Dict[str, List[AIPEntry]], standardize: bool = True) -> None:
        """
        Bulk add AIP entries to transaction.

        Args:
            entries_by_icao: Dict mapping ICAO codes to lists of AIP entries
            standardize: Whether to standardize entries
        """
        self._changes.append({
            "operation": "bulk_add_aip_entries",
            "entries_by_icao": entries_by_icao,
            "standardize": standardize
        })

    def bulk_add_procedures(self, procedures_by_icao: Dict[str, List[Procedure]]) -> None:
        """
        Bulk add procedures to transaction.

        Args:
            procedures_by_icao: Dict mapping ICAO codes to lists of procedures
        """
        self._changes.append({
            "operation": "bulk_add_procedures",
            "procedures_by_icao": procedures_by_icao
        })

    def add_border_crossing_entry(self, entry: BorderCrossingEntry) -> None:
        """
        Add border crossing entry to transaction.

        Args:
            entry: Border crossing entry to add
        """
        self._changes.append({
            "operation": "add_border_crossing_entry",
            "entry": entry
        })

    def remove_by_country(self, country_code: str) -> None:
        """
        Remove airports by country in transaction.

        Args:
            country_code: ISO country code
        """
        self._changes.append({
            "operation": "remove_by_country",
            "country_code": country_code
        })

    def get_changes(self) -> Dict[str, Any]:
        """
        Get summary of changes in this transaction.

        Returns:
            Dictionary with change summary
        """
        return {
            "total_operations": len(self._changes),
            "operations": [c["operation"] for c in self._changes],
            "summary": self._change_summary
        }

    def _create_snapshot(self) -> Dict[str, Any]:
        """Create snapshot of current model state for rollback."""
        return {
            '_airports': copy.deepcopy(self.model._airports),
            'border_crossing_points': copy.deepcopy(self.model.border_crossing_points),
            'sources_used': copy.copy(self.model.sources_used),
            'updated_at': self.model.updated_at
        }

    def _restore_snapshot(self, snapshot: Dict[str, Any]) -> None:
        """Restore model to snapshot state."""
        self.model._airports = snapshot['_airports']
        self.model.border_crossing_points = snapshot['border_crossing_points']
        self.model.sources_used = snapshot['sources_used']
        self.model.updated_at = snapshot['updated_at']
        logger.debug("Restored model to snapshot")

    def _rollback(self) -> None:
        """Rollback to snapshot."""
        if self._snapshot:
            self._restore_snapshot(self._snapshot)

    def _commit(self) -> None:
        """Apply all changes atomically."""
        # Validate all changes first
        validation_errors = self._validate_all()
        if validation_errors:
            raise ModelValidationError(
                f"Validation failed with {len(validation_errors)} errors",
                details=validation_errors
            )

        # Apply all changes
        for change in self._changes:
            self._apply_change(change)

        # Update derived fields once at end if requested
        if self.auto_update_derived:
            self.model.update_all_derived_fields()

    def _validate_all(self) -> List[str]:
        """
        Validate all pending changes.

        Returns:
            List of validation error messages (empty if valid)
        """
        errors = []

        for change in self._changes:
            operation = change["operation"]

            if operation == "add_airport":
                airport = change["airport"]
                result = self._validate_airport(airport)
                if not result.is_valid:
                    errors.extend([
                        f"Airport {airport.ident}: {error}"
                        for error in result.get_error_messages()
                    ])

            elif operation == "bulk_add_airports":
                for airport in change["airports"]:
                    result = self._validate_airport(airport)
                    if not result.is_valid:
                        errors.extend([
                            f"Airport {airport.ident}: {error}"
                            for error in result.get_error_messages()
                        ])

        return errors

    def _validate_airport(self, airport: Airport) -> ValidationResult:
        """
        Validate an airport before adding.

        Args:
            airport: Airport to validate

        Returns:
            ValidationResult
        """
        result = ValidationResult()

        # Basic validation
        if not airport.ident or len(airport.ident) != 4:
            result.add_error("ident", "ICAO code must be 4 characters", airport.ident)

        # Optionally add more validation rules here

        return result

    def _apply_change(self, change: Dict[str, Any]) -> None:
        """Apply a single change to the model."""
        operation = change["operation"]

        if operation == "add_airport":
            self._apply_add_airport(change["airport"], change["merge"])

        elif operation == "add_aip_entries":
            self._apply_add_aip_entries(
                change["icao"],
                change["entries"],
                change["standardize"]
            )

        elif operation == "add_procedures":
            self._apply_add_procedures(
                change["icao"],
                change["procedures"]
            )

        elif operation == "bulk_add_airports":
            self._apply_bulk_add_airports(
                change["airports"],
                change["merge"]
            )

        elif operation == "bulk_add_aip_entries":
            self._apply_bulk_add_aip_entries(
                change["entries_by_icao"],
                change["standardize"]
            )

        elif operation == "bulk_add_procedures":
            self._apply_bulk_add_procedures(
                change["procedures_by_icao"]
            )

        elif operation == "add_border_crossing_entry":
            self._apply_add_border_crossing_entry(change["entry"])

        elif operation == "remove_by_country":
            self._apply_remove_by_country(change["country_code"])

    def _apply_add_airport(self, airport: Airport, merge: str) -> None:
        """Apply add_airport operation."""
        if merge == "skip_existing" and airport.ident in self.model._airports:
            return

        exists = airport.ident in self.model._airports
        self.model.add_airport(airport)

        if self.track_changes:
            if exists:
                self._change_summary['updated_airports'].append(airport.ident)
            else:
                self._change_summary['added_airports'].append(airport.ident)

    def _apply_add_aip_entries(self, icao: str, entries: List[AIPEntry], standardize: bool) -> None:
        """Apply add_aip_entries operation."""
        self.model.add_aip_entries_to_airport(icao, entries, standardize)

        if self.track_changes:
            self._change_summary['added_aip_entries'] += len(entries)

    def _apply_add_procedures(self, icao: str, procedures: List[Procedure]) -> None:
        """Apply add_procedures operation."""
        if icao not in self.model._airports:
            logger.warning(f"Airport {icao} not found, skipping procedures")
            return

        airport = self.model._airports[icao]
        for procedure in procedures:
            airport.add_procedure(procedure)

        if self.track_changes:
            self._change_summary['added_procedures'] += len(procedures)

    def _apply_bulk_add_airports(self, airports: List[Airport], merge: str) -> None:
        """Apply bulk_add_airports operation."""
        for airport in airports:
            self._apply_add_airport(airport, merge)

    def _apply_bulk_add_aip_entries(self, entries_by_icao: Dict[str, List[AIPEntry]], standardize: bool) -> None:
        """Apply bulk_add_aip_entries operation."""
        for icao, entries in entries_by_icao.items():
            self._apply_add_aip_entries(icao, entries, standardize)

    def _apply_bulk_add_procedures(self, procedures_by_icao: Dict[str, List[Procedure]]) -> None:
        """Apply bulk_add_procedures operation."""
        for icao, procedures in procedures_by_icao.items():
            self._apply_add_procedures(icao, procedures)

    def _apply_add_border_crossing_entry(self, entry: BorderCrossingEntry) -> None:
        """Apply add_border_crossing_entry operation."""
        self.model.add_border_crossing_entry(entry)

        if self.track_changes:
            self._change_summary['added_border_crossings'] += 1

    def _apply_remove_by_country(self, country_code: str) -> None:
        """Apply remove_by_country operation."""
        # Track which airports are being removed
        if self.track_changes:
            airports_to_remove = [
                icao for icao, airport in self.model._airports.items()
                if airport.iso_country == country_code
            ]
            self._change_summary['removed_airports'].extend(airports_to_remove)

        self.model.remove_airports_by_country(country_code)
