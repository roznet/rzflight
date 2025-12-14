from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Any, Callable, Union, TYPE_CHECKING
from datetime import datetime
import logging
from pathlib import Path
import json
import warnings

from .airport import Airport
from .runway import Runway
from .aip_entry import AIPEntry
from .procedure import Procedure
from .border_crossing_entry import BorderCrossingEntry
from .navpoint import NavPoint
from .airport_collection import AirportCollection
from .procedure_collection import ProcedureCollection
from .model_transaction import ModelTransaction
from .airport_builder import AirportBuilder
from .validation import ValidationResult, ModelValidationError

if TYPE_CHECKING:
    from ..interp.base import BaseInterpreter, InterpretationResult
    from ..utils.field_standardization_service import FieldStandardizationService

import math

logger = logging.getLogger(__name__)

@dataclass
class EuroAipModel:
    """
    Main model class that maintains the overall model of all airports and their derived information.
    
    This class serves as the central data store for all airport information collected from
    various sources. It provides methods for adding, updating, and querying airport data.
    """
    
    # Main data store: map from ICAO code to Airport object
    # Internal storage - use the .airports property for querying
    _airports: Dict[str, Airport] = field(default_factory=dict)
    
    # Border crossing data: map from country ISO to airport name to entry
    border_crossing_points: Dict[str, Dict[str, BorderCrossingEntry]] = field(default_factory=dict)
    
    # Metadata
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    sources_used: Set[str] = field(default_factory=set)
    
    # Field standardization service
    field_service: Optional['FieldStandardizationService'] = None
    
    def __post_init__(self):
        """Initialize field standardization service if not provided."""
        if self.field_service is None:
            from ..utils.field_standardization_service import FieldStandardizationService
            self.field_service = FieldStandardizationService()

    # ========================================================================
    # Modern Query API - Queryable Collections
    # ========================================================================

    @property
    def airports(self) -> AirportCollection:
        """
        Get queryable collection of all airports.

        The airports property returns an AirportCollection that provides a fluent,
        composable API for querying airports with domain-specific filters.

        Returns:
            AirportCollection with all airports in the model

        Examples:
            # Simple filters
            french_airports = model.airports.by_country("FR").all()
            airports_with_runways = model.airports.with_runways().all()

            # Chaining filters
            suitable = model.airports.by_country("FR") \\
                                    .with_hard_runway() \\
                                    .with_fuel(avgas=True) \\
                                    .with_procedures("approach") \\
                                    .all()

            # Using functional filters
            long_runways = model.airports.filter(
                lambda a: a.longest_runway_length_ft and a.longest_runway_length_ft > 5000
            ).all()

            # Grouping
            by_country = model.airports.with_procedures().group_by_country()

            # Convenience methods
            first_french = model.airports.by_country("FR").first()
            count = model.airports.with_runways().count()
            has_ils = model.airports.with_approach_type("ILS").exists()
        """
        return AirportCollection(list(self._airports.values()))

    @property
    def procedures(self) -> ProcedureCollection:
        """
        Get queryable collection of all procedures across all airports.

        The procedures property returns a ProcedureCollection that provides
        domain-specific filters for querying approaches, departures, and arrivals.

        Returns:
            ProcedureCollection with all procedures from all airports

        Examples:
            # Filter by type
            all_approaches = model.procedures.approaches().all()
            all_departures = model.procedures.departures().all()

            # Filter by approach type
            ils_approaches = model.procedures.approaches().by_type("ILS").all()

            # Filter by runway
            rwy_09l = model.procedures.approaches().by_runway("09L").all()

            # Chaining
            ils_09l = model.procedures.approaches() \\
                                     .by_type("ILS") \\
                                     .by_runway("09L") \\
                                     .all()

            # Get most precise approach
            best = model.procedures.approaches().by_runway("09L").most_precise()

            # Grouping
            by_type = model.procedures.group_by_approach_type()
            by_runway = model.procedures.approaches().group_by_runway()
        """
        all_procedures = []
        for airport in self._airports.values():
            all_procedures.extend(airport.procedures)
        return ProcedureCollection(all_procedures)

    # ========================================================================
    # Legacy Query API - Maintained for Backward Compatibility
    # ========================================================================

    def add_airport(self, airport: Airport) -> None:
        """
        Add or update an airport in the model.
        
        Args:
            airport: Airport object to add or update
        """
        if airport.ident in self._airports:
            # Update existing airport
            existing = self._airports[airport.ident]
            
            # Update basic fields if new data is available
            for field_name, value in airport.__dict__.items():
                if value is not None and field_name not in ['runways', 'aip_entries', 'procedures', 'sources', 'created_at', 'updated_at']:
                    setattr(existing, field_name, value)
            
            # Add runways
            for runway in airport.runways:
                existing.add_runway(runway)
            
            # Add AIP entries
            for entry in airport.aip_entries:
                existing.add_aip_entry(entry)
            
            # Add procedures
            for procedure in airport.procedures:
                existing.add_procedure(procedure)
            
            # Add sources
            for source in airport.sources:
                existing.add_source(source)
                self.sources_used.add(source)
            
            existing.updated_at = datetime.now()
            logger.debug(f"Updated airport {airport.ident} with data from {list(airport.sources)}")
        else:
            # Add new airport
            self._airports[airport.ident] = airport
            for source in airport.sources:
                self.sources_used.add(source)
            logger.debug(f"Added new airport {airport.ident} with data from {list(airport.sources)}")
        
        self.updated_at = datetime.now()
    
    def add_aip_entries_to_airport(self, icao: str, entries: List[AIPEntry], standardize: bool = True) -> None:
        """
        Add AIP entries to a specific airport with optional standardization.
        
        Args:
            icao: ICAO airport code
            entries: List of AIPEntry objects to add
            standardize: Whether to standardize the entries using field service
        """
        if icao not in self._airports:
            logger.warning(f"Airport {icao} not found in model, creating new airport")
            airport = Airport(ident=icao)
            self._airports[icao] = airport
        
        airport = self._airports[icao]
        
        if standardize and self.field_service:
            entries = self.field_service.standardize_aip_entries(entries)
        
        airport.add_aip_entries(entries)
        logger.debug(f"Added {len(entries)} AIP entries to {icao}")
    
    def get_airports_with_standardized_aip_data(self) -> List[Airport]:
        """
        Get all airports that have standardized AIP data.

        .. deprecated::
            Use :meth:`model.airports.with_standardized_aip_data().all()` instead.

        Returns:
            List of airports with standardized AIP data
        """
        warnings.warn(
            "get_airports_with_standardized_aip_data() is deprecated. "
            "Use model.airports.with_standardized_aip_data().all() instead.",
            DeprecationWarning,
            stacklevel=2
        )
        return [airport for airport in self._airports.values()
                if airport.get_standardized_entries()]
    
    def get_field_mapping_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about field mapping across all airports.
        
        Returns:
            Dictionary with field mapping statistics
        """
        all_entries = []
        for airport in self._airports.values():
            all_entries.extend(airport.aip_entries)
        
        if self.field_service:
            return self.field_service.get_mapping_statistics(all_entries)
        else:
            return {
                'total_fields': len(all_entries),
                'mapped_fields': 0,
                'unmapped_fields': len(all_entries),
                'mapping_rate': 0.0,
                'average_mapping_score': 0.0,
                'section_counts': {}
            }
    
    def get_airport(self, icao: str) -> Optional[Airport]:
        """
        Get an airport by ICAO code.

        .. deprecated::
            Use :meth:`model.airports['ICAO']` or :meth:`model.airports.where(ident=icao).first()` instead.

            This method is maintained for backward compatibility but will be removed
            in a future version. The new collection API provides more powerful
            query capabilities.

        Args:
            icao: ICAO airport code

        Returns:
            Airport object or None if not found

        Examples:
            # Old way
            airport = model.get_airport("EGLL")

            # New way (preferred - dict-style)
            airport = model.airports['EGLL']

            # Or query API
            airport = model.airports.where(ident="EGLL").first()
        """
        warnings.warn(
            "get_airport() is deprecated. "
            "Use model.airports['ICAO'] or model.airports.where(ident=icao).first() instead.",
            DeprecationWarning,
            stacklevel=2
        )
        return self._airports.get(icao)
    
    def get_airports_by_country(self, country_code: str) -> List[Airport]:
        """
        Get all airports in a specific country.

        .. deprecated::
            Use :meth:`model.airports.by_country(code).all()` instead.

        Args:
            country_code: ISO country code

        Returns:
            List of airports in the country

        Examples:
            # Old way
            french = model.get_airports_by_country("FR")

            # New way (preferred)
            french = model.airports.by_country("FR").all()
        """
        warnings.warn(
            "get_airports_by_country() is deprecated. "
            "Use model.airports.by_country(code).all() instead.",
            DeprecationWarning,
            stacklevel=2
        )
        return [airport for airport in self._airports.values()
                if airport.iso_country == country_code]
    
    def remove_airports_by_country(self, country_code: str) -> None:
        """
        Remove all airports for a specific country from the model.
        
        Args:
            country_code: ISO country code
        """
        # Find all airports for this country
        airports_to_remove = [
            icao for icao, airport in self._airports.items()
            if airport.iso_country == country_code
        ]
        
        if airports_to_remove:
            removed_count = len(airports_to_remove)
            for icao in airports_to_remove:
                del self._airports[icao]
            self.updated_at = datetime.now()
            logger.info(f"Removed {removed_count} airports for country {country_code}")
        else:
            logger.debug(f"No airports found for country {country_code}")
    
    def get_airports_by_source(self, source_name: str) -> List[Airport]:
        """
        Get all airports that have data from a specific source.

        .. deprecated::
            Use :meth:`model.airports.by_source(source).all()` instead.

        Args:
            source_name: Name of the source

        Returns:
            List of airports with data from the source

        Examples:
            # New way (preferred)
            uk_airports = model.airports.by_source("uk_eaip").all()
        """
        warnings.warn(
            "get_airports_by_source() is deprecated. "
            "Use model.airports.by_source(source).all() instead.",
            DeprecationWarning,
            stacklevel=2
        )
        return [airport for airport in self._airports.values()
                if source_name in airport.sources]
    
    def get_airports_with_procedures(self, procedure_type: Optional[str] = None) -> List[Airport]:
        """
        Get all airports that have procedures.

        .. deprecated::
            Use :meth:`model.airports.with_procedures(type).all()` instead.

        Args:
            procedure_type: Optional procedure type filter

        Returns:
            List of airports with procedures

        Examples:
            # New way (preferred)
            with_procedures = model.airports.with_procedures().all()
            with_approaches = model.airports.with_procedures("approach").all()
        """
        warnings.warn(
            "get_airports_with_procedures() is deprecated. "
            "Use model.airports.with_procedures(type).all() instead.",
            DeprecationWarning,
            stacklevel=2
        )
        if procedure_type:
            return [airport for airport in self._airports.values()
                    if airport.get_procedures_by_type(procedure_type)]
        else:
            return [airport for airport in self._airports.values()
                    if airport.procedures]
    
    def get_airports_with_runways(self) -> List[Airport]:
        """
        Get all airports that have runway information.

        .. deprecated::
            Use :meth:`model.airports.with_runways().all()` instead.

        Returns:
            List of airports with runways
        """
        warnings.warn(
            "get_airports_with_runways() is deprecated. "
            "Use model.airports.with_runways().all() instead.",
            DeprecationWarning,
            stacklevel=2
        )
        return [airport for airport in self._airports.values()
                if airport.runways]
    
    def get_airports_with_aip_data(self) -> List[Airport]:
        """
        Get all airports that have AIP data.

        .. deprecated::
            Use :meth:`model.airports.with_aip_data().all()` instead.

        Returns:
            List of airports with AIP data
        """
        warnings.warn(
            "get_airports_with_aip_data() is deprecated. "
            "Use model.airports.with_aip_data().all() instead.",
            DeprecationWarning,
            stacklevel=2
        )
        return [airport for airport in self._airports.values()
                if airport.aip_entries]
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about the model.
        
        Returns:
            Dictionary with model statistics
        """
        total_airports = len(self._airports)
        airports_with_runways = len(self.get_airports_with_runways())
        airports_with_procedures = len(self.get_airports_with_procedures())
        airports_with_aip_data = len(self.get_airports_with_aip_data())
        airports_with_border_crossing = len(self.get_border_crossing_airports())
        
        total_runways = sum(len(airport.runways) for airport in self._airports.values())
        total_procedures = sum(len(airport.procedures) for airport in self._airports.values())
        total_aip_entries = sum(len(airport.aip_entries) for airport in self._airports.values())
        total_border_crossing_points = len(self.get_all_border_crossing_points())
        
        # Count procedures by type
        procedure_types = {}
        for airport in self._airports.values():
            for procedure in airport.procedures:
                proc_type = procedure.procedure_type.lower()
                procedure_types[proc_type] = procedure_types.get(proc_type, 0) + 1
        
        # Get border crossing statistics
        border_crossing_stats = self.get_border_crossing_statistics()
        
        return {
            'total_airports': total_airports,
            'airports_with_runways': airports_with_runways,
            'airports_with_procedures': airports_with_procedures,
            'airports_with_aip_data': airports_with_aip_data,
            'airports_with_border_crossing': airports_with_border_crossing,
            'total_runways': total_runways,
            'total_procedures': total_procedures,
            'total_aip_entries': total_aip_entries,
            'total_border_crossing_points': total_border_crossing_points,
            'procedure_types': procedure_types,
            'border_crossing': border_crossing_stats,
            'sources_used': list(self.sources_used),
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }
    
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the model to a dictionary for JSON serialization.
        
        Returns:
            Dictionary representation of the model
        """
        return {
            'airports': {icao: airport.to_dict() for icao, airport in self._airports.items()},
            'border_crossing_points': {
                country_iso: {
                    icao_code: entry.to_dict() 
                    for icao_code, entry in country_entries.items()
                }
                for country_iso, country_entries in self.border_crossing_points.items()
            },
            'statistics': self.get_statistics()
        }
    
    
    
    def __repr__(self):
        return f"EuroAipModel(airports={len(self._airports)}, sources={list(self.sources_used)})"
    
    def __str__(self):
        stats = self.get_statistics()
        return f"""EuroAipModel:
- Total airports: {stats['total_airports']}
- Airports with runways: {stats['airports_with_runways']}
- Airports with procedures: {stats['airports_with_procedures']}
- Airports with AIP data: {stats['airports_with_aip_data']}
- Airports with border crossing: {stats['airports_with_border_crossing']}
- Total runways: {stats['total_runways']}
- Total procedures: {stats['total_procedures']}
- Total AIP entries: {stats['total_aip_entries']}
- Total border crossing entries: {stats['total_border_crossing_points']}
- Sources used: {', '.join(stats['sources_used'])}
- Created: {stats['created_at']}
- Updated: {stats['updated_at']}"""
    
    def get_procedures_by_runway(self, airport_icao: str, runway_ident: str) -> List['Procedure']:
        """
        Get all procedures for a specific runway at an airport.

        .. deprecated::
            Use :meth:`model.airports[icao].procedures_query.by_runway(runway).all()` instead.
        """
        warnings.warn(
            "get_procedures_by_runway() is deprecated. "
            "Use model.airports[icao].procedures_query.by_runway(runway).all() instead.",
            DeprecationWarning,
            stacklevel=2
        )
        airport = self.get_airport(airport_icao)
        if not airport:
            return []
        return airport.get_procedures_by_runway(runway_ident)
    
    def get_approaches_by_runway(self, airport_icao: str, runway_ident: str) -> List['Procedure']:
        """Get all approach procedures for a specific runway at an airport."""
        airport = self.get_airport(airport_icao)
        if not airport:
            return []
        return airport.get_approaches_by_runway(runway_ident)
    
    def get_departures_by_runway(self, airport_icao: str, runway_ident: str) -> List['Procedure']:
        """Get all departure procedures for a specific runway at an airport."""
        airport = self.get_airport(airport_icao)
        if not airport:
            return []
        return airport.get_departures_by_runway(runway_ident)
    
    def get_arrivals_by_runway(self, airport_icao: str, runway_ident: str) -> List['Procedure']:
        """Get all arrival procedures for a specific runway at an airport."""
        airport = self.get_airport(airport_icao)
        if not airport:
            return []
        return airport.get_arrivals_by_runway(runway_ident)
    
    def get_all_approaches(self) -> Dict[str, List['Procedure']]:
        """Get all approach procedures across all airports."""
        result = {}
        for icao, airport in self._airports.items():
            approaches = airport.get_approaches()
            if approaches:
                result[icao] = approaches
        return result
    
    def get_all_departures(self) -> Dict[str, List['Procedure']]:
        """Get all departure procedures across all airports."""
        result = {}
        for icao, airport in self._airports.items():
            departures = airport.get_departures()
            if departures:
                result[icao] = departures
        return result
    
    def get_all_arrivals(self) -> Dict[str, List['Procedure']]:
        """Get all arrival procedures across all airports."""
        result = {}
        for icao, airport in self._airports.items():
            arrivals = airport.get_arrivals()
            if arrivals:
                result[icao] = arrivals
        return result
    
    def get_procedures_by_source(self, source: str) -> Dict[str, List['Procedure']]:
        """
        Get all procedures from a specific source across all airports.

        .. deprecated::
            Use :meth:`model.procedures.by_source(source).all()` and group by airport instead.
        """
        warnings.warn(
            "get_procedures_by_source() is deprecated. "
            "Use model.procedures.by_source(source).all() and group by airport instead.",
            DeprecationWarning,
            stacklevel=2
        )
        result = {}
        for icao, airport in self._airports.items():
            procedures = airport.get_procedures_by_source(source)
            if procedures:
                result[icao] = procedures
        return result
    
    def get_procedures_by_authority(self, authority: str) -> Dict[str, List['Procedure']]:
        """
        Get all procedures from a specific authority across all airports.

        .. deprecated::
            Use custom filtering with :meth:`model.procedures.where()` instead.
        """
        warnings.warn(
            "get_procedures_by_authority() is deprecated. "
            "Use custom filtering with model.procedures.where() instead.",
            DeprecationWarning,
            stacklevel=2
        )
        result = {}
        for icao, airport in self._airports.items():
            procedures = airport.get_procedures_by_authority(authority)
            if procedures:
                result[icao] = procedures
        return result
    
    def get_runway_procedures_summary(self, airport_icao: str) -> Dict[str, Dict[str, List[str]]]:
        """Get a summary of procedures by runway and type for a specific airport."""
        airport = self.get_airport(airport_icao)
        if not airport:
            return {}
        return airport.get_runway_procedures_summary()

    def get_all_runway_procedures_summary(self) -> Dict[str, Dict[str, Dict[str, List[str]]]]:
        """Get a summary of procedures by runway and type for all airports."""
        result = {}
        for icao, airport in self._airports.items():
            summary = airport.get_runway_procedures_summary()
            if summary:
                result[icao] = summary
        return result

    # ========================================================================
    # Modern Builder API - Transactions and Bulk Operations
    # ========================================================================

    def transaction(self, auto_update_derived: bool = True, track_changes: bool = False) -> ModelTransaction:
        """
        Create a transaction context for safe, atomic model updates.

        The transaction provides rollback-on-error safety and automatic derived field
        updates on success. All changes are applied atomically - if any operation fails,
        all changes are rolled back.

        Args:
            auto_update_derived: Whether to automatically update derived fields on commit
            track_changes: Whether to track changes for reporting

        Returns:
            ModelTransaction context manager

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

            Bulk operations in transaction:
            >>> with model.transaction() as txn:
            ...     txn.bulk_add_airports(airports)
            ...     txn.bulk_add_aip_entries(aip_data_by_icao)

            Without auto-update of derived fields:
            >>> with model.transaction(auto_update_derived=False) as txn:
            ...     txn.bulk_add_airports(many_airports)
            ... model.update_all_derived_fields()  # Manual update later

            Track changes:
            >>> with model.transaction(track_changes=True) as txn:
            ...     txn.bulk_add_airports(airports)
            ...     changes = txn.get_changes()
        """
        return ModelTransaction(self, auto_update_derived, track_changes)

    def airport_builder(self, icao: str) -> AirportBuilder:
        """
        Create a builder for constructing airports with fluent API.

        The airport builder provides a chainable interface for constructing
        complete airport objects with validation before adding to the model.

        Args:
            icao: ICAO code for the airport

        Returns:
            AirportBuilder instance

        Examples:
            Basic usage:
            >>> builder = model.airport_builder("EGLL")
            >>> builder.with_basic_info(
            ...     name="London Heathrow",
            ...     latitude_deg=51.4700,
            ...     longitude_deg=-0.4543,
            ...     iso_country="GB"
            ... )
            >>> builder.with_runways([runway1, runway2])
            >>> airport = builder.build()

            Chaining:
            >>> airport = model.airport_builder("EGLL") \\
            ...     .with_basic_info(name="Heathrow", ...) \\
            ...     .with_runways(runways) \\
            ...     .with_procedures(procedures) \\
            ...     .build()

            Direct commit to model:
            >>> model.airport_builder("EGLL") \\
            ...     .with_basic_info(...) \\
            ...     .with_runways(runways) \\
            ...     .commit()  # Validates, builds, and adds to model
        """
        return AirportBuilder(self, icao)

    def bulk_add_airports(
        self,
        airports: List[Airport],
        merge: str = "update_existing",
        validate: bool = True,
        update_derived: bool = True
    ) -> Dict[str, Any]:
        """
        Bulk add airports efficiently with single validation and update pass.

        Args:
            airports: List of airports to add
            merge: Merge strategy - "update_existing", "skip_existing", "replace"
            validate: Whether to validate before adding
            update_derived: Whether to update derived fields after

        Returns:
            Summary dictionary with added, updated, skipped counts

        Raises:
            ModelValidationError: If validation fails

        Examples:
            Simple bulk add:
            >>> result = model.bulk_add_airports([airport1, airport2, airport3])
            >>> print(f"Added: {result['added']}, Updated: {result['updated']}")

            Skip existing:
            >>> result = model.bulk_add_airports(
            ...     airports,
            ...     merge="skip_existing"
            ... )

            Without derived field update (for performance):
            >>> result = model.bulk_add_airports(
            ...     airports,
            ...     update_derived=False
            ... )
            >>> model.update_all_derived_fields()  # Update once at end
        """
        added = 0
        updated = 0
        skipped = 0
        errors = []

        # Validate all first if requested
        if validate:
            for airport in airports:
                validation = self._validate_airport(airport)
                if not validation.is_valid:
                    errors.append({
                        "icao": airport.ident,
                        "errors": validation.get_error_messages()
                    })

            if errors:
                raise ModelValidationError(
                    f"Validation failed for {len(errors)} airports",
                    details=errors
                )

        # Add all airports
        for airport in airports:
            if merge == "skip_existing" and airport.ident in self._airports:
                skipped += 1
                continue

            exists = airport.ident in self._airports
            self.add_airport(airport)

            if exists:
                updated += 1
            else:
                added += 1

        # Update derived fields once at end
        if update_derived:
            self.update_all_derived_fields()

        logger.info(f"Bulk added airports: {added} added, {updated} updated, {skipped} skipped")

        return {
            "added": added,
            "updated": updated,
            "skipped": skipped,
            "total": len(airports)
        }

    def bulk_add_aip_entries(
        self,
        entries_by_icao: Dict[str, List[AIPEntry]],
        standardize: bool = True
    ) -> Dict[str, int]:
        """
        Bulk add AIP entries for multiple airports.

        Args:
            entries_by_icao: Dict mapping ICAO codes to lists of AIP entries
            standardize: Whether to standardize entries using field service

        Returns:
            Summary dictionary mapping ICAO codes to count of entries added

        Examples:
            >>> aip_data = {
            ...     "EGLL": egll_entries,
            ...     "LFPG": lfpg_entries,
            ...     "EDDF": eddf_entries
            ... }
            >>> result = model.bulk_add_aip_entries(aip_data)
            >>> print(f"Added {sum(result.values())} total entries")
        """
        summary = {}

        for icao, entries in entries_by_icao.items():
            self.add_aip_entries_to_airport(icao, entries, standardize)
            summary[icao] = len(entries)

        logger.info(f"Bulk added AIP entries to {len(summary)} airports, "
                   f"{sum(summary.values())} total entries")

        return summary

    def bulk_add_procedures(
        self,
        procedures_by_icao: Dict[str, List[Procedure]]
    ) -> Dict[str, int]:
        """
        Bulk add procedures for multiple airports.

        Args:
            procedures_by_icao: Dict mapping ICAO codes to lists of procedures

        Returns:
            Summary dictionary mapping ICAO codes to count of procedures added

        Examples:
            >>> procedures_data = {
            ...     "EGLL": egll_procedures,
            ...     "LFPG": lfpg_procedures
            ... }
            >>> result = model.bulk_add_procedures(procedures_data)
            >>> print(f"Added procedures to {len(result)} airports")
        """
        summary = {}

        for icao, procedures in procedures_by_icao.items():
            if icao not in self._airports:
                logger.warning(f"Airport {icao} not found, skipping {len(procedures)} procedures")
                continue

            airport = self._airports[icao]
            for procedure in procedures:
                airport.add_procedure(procedure)

            summary[icao] = len(procedures)

        logger.info(f"Bulk added procedures to {len(summary)} airports, "
                   f"{sum(summary.values())} total procedures")

        return summary

    def _validate_airport(self, airport: Airport) -> ValidationResult:
        """
        Validate an airport before adding.

        Args:
            airport: Airport to validate

        Returns:
            ValidationResult with validation status and errors
        """
        result = ValidationResult()

        # Basic validation
        if not airport.ident or len(airport.ident) != 4:
            result.add_error("ident", "ICAO code must be 4 characters", airport.ident)

        # Add more validation rules as needed

        return result

    # ========================================================================
    # Border crossing methods
    # ========================================================================
    
    def add_border_crossing_entry(self, entry: BorderCrossingEntry) -> None:
        """
        Add a border crossing entry to the model.
        
        Args:
            entry: BorderCrossingEntry to add
        """
        country_iso = entry.country_iso
        icao_code = entry.icao_code or entry.matched_airport_icao

        # the model only stores airports
        # If is_airport is None but we have an ICAO code, treat it as an airport
        if entry.is_airport is False:
            return

        if not icao_code:
            logger.warning(f"Border crossing entry for {entry.airport_name} has no ICAO code, skipping")
            return

        # Only add border crossing entries for airports that are in the model
        if icao_code not in self._airports:
            return
        if country_iso not in self.border_crossing_points:
            self.border_crossing_points[country_iso] = {}

        
        # Check if there's already an entry with this ICAO code
        if icao_code in self.border_crossing_points[country_iso]:
            existing_entry = self.border_crossing_points[country_iso][icao_code]
            
            # Use is_more_complete_than logic to decide which entry to keep
            if entry.is_more_complete_than(existing_entry):
                # New entry is more complete, replace the existing one
                self.border_crossing_points[country_iso][icao_code] = entry
                logger.debug(f"Replaced border crossing entry for {entry.airport_name} ({icao_code}) in {country_iso} with more complete entry")
            else:
                # Existing entry is more complete or equal, keep the existing one
                logger.debug(f"Kept existing border crossing entry for {existing_entry.airport_name} ({icao_code}) in {country_iso} as it is more complete")
        else:
            # No existing entry, add the new one
            self.border_crossing_points[country_iso][icao_code] = entry
            logger.debug(f"Added border crossing entry for {entry.airport_name} ({icao_code}) in {country_iso}")
        
        self.sources_used.add(entry.source)
        self.updated_at = datetime.now()
    
    def add_border_crossing_points(self, entries: List[BorderCrossingEntry]) -> None:
        """
        Add multiple border crossing entries to the model.
        
        Args:
            entries: List of BorderCrossingEntry objects to add
        """
        for entry in entries:
            self.add_border_crossing_entry(entry)
        
        logger.info(f"Added {len(entries)} border crossing entries to model")
    
    def get_border_crossing_points_by_country(self, country_iso: str) -> List[BorderCrossingEntry]:
        """
        Get all border crossing entries for a specific country.
        
        Args:
            country_iso: ISO country code
            
        Returns:
            List of border crossing entries for the country
        """
        if country_iso not in self.border_crossing_points:
            return []
        
        return list(self.border_crossing_points[country_iso].values())
    
    def get_border_crossing_entry(self, country_iso: str, icao_code: str) -> Optional[BorderCrossingEntry]:
        """
        Get a specific border crossing entry.
        
        Args:
            country_iso: ISO country code
            icao_code: ICAO code of the airport
            
        Returns:
            BorderCrossingEntry if found, None otherwise
        """
        if country_iso not in self.border_crossing_points:
            return None
        
        return self.border_crossing_points[country_iso].get(icao_code)
    
    def get_border_crossing_entry_by_name(self, country_iso: str, airport_name: str) -> Optional[BorderCrossingEntry]:
        """
        Get a border crossing entry by airport name (for backward compatibility).
        
        Args:
            country_iso: ISO country code
            airport_name: Name of the airport
            
        Returns:
            BorderCrossingEntry if found, None otherwise
        """
        if country_iso not in self.border_crossing_points:
            return None
        
        for entry in self.border_crossing_points[country_iso].values():
            if entry.airport_name == airport_name:
                return entry
        
        return None
    
    def get_all_border_crossing_points(self) -> List[BorderCrossingEntry]:
        """
        Get all border crossing entries in the model.
        
        Returns:
            List of all border crossing entries
        """
        all_entries = []
        for country_entries in self.border_crossing_points.values():
            all_entries.extend(country_entries.values())
        return all_entries
    
    def get_border_crossing_countries(self) -> List[str]:
        """
        Get list of countries that have border crossing entries.
        
        Returns:
            List of ISO country codes
        """
        return list(self.border_crossing_points.keys())
    
    def remove_border_crossing_points_by_country(self, country_iso: str) -> None:
        """
        Remove all border crossing entries for a specific country.
        
        Args:
            country_iso: ISO country code
        """
        if country_iso in self.border_crossing_points:
            removed_count = len(self.border_crossing_points[country_iso])
            del self.border_crossing_points[country_iso]
            self.updated_at = datetime.now()
            logger.info(f"Removed {removed_count} border crossing entries for country {country_iso}")
        else:
            logger.debug(f"No border crossing entries found for country {country_iso}")
    
    def get_border_crossing_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about border crossing entries.
        
        Returns:
            Dictionary with border crossing statistics
        """
        total_entries = len(self.get_all_border_crossing_points())
        countries_count = len(self.border_crossing_points)
        
        # Count matched vs unmatched
        matched_count = 0
        unmatched_count = 0
        for entry in self.get_all_border_crossing_points():
            if entry.matched_airport_icao:
                matched_count += 1
            else:
                unmatched_count += 1
        
        # Count by source
        source_counts = {}
        for entry in self.get_all_border_crossing_points():
            source = entry.source or 'unknown'
            source_counts[source] = source_counts.get(source, 0) + 1
        
        # Count by country
        country_counts = {}
        for country_iso, entries in self.border_crossing_points.items():
            country_counts[country_iso] = len(entries)
        
        return {
            'total_entries': total_entries,
            'countries_count': countries_count,
            'matched_count': matched_count,
            'unmatched_count': unmatched_count,
            'match_rate': matched_count / total_entries if total_entries > 0 else 0,
            'by_source': source_counts,
            'by_country': country_counts
        }
    
    def get_border_crossing_airports(self) -> List[Airport]:
        """
        Get all airports that are border crossing points.

        .. deprecated::
            Use :meth:`model.airports.border_crossings().all()` instead.

        Returns:
            List of airports that are border crossing points
        """
        warnings.warn(
            "get_border_crossing_airports() is deprecated. "
            "Use model.airports.border_crossings().all() instead.",
            DeprecationWarning,
            stacklevel=2
        )
        border_airports = []
        for entry in self.get_all_border_crossing_points():
            if entry.icao_code in self._airports:
                border_airports.append(self._airports[entry.icao_code])

        return border_airports
    
    def update_all_derived_fields(self) -> None:
        """
        Update all calculated/derived fields across the model.
        This should be called after loading the model to ensure all
        connections and derived information are properly set.
        """
        logger.info("Updating all derived fields...")
        
        # Step 1: Update model-level derived fields (requires access to model data)
        self._update_border_crossing_airports()
        
        # Step 2: Update airport-level derived fields (delegated to Airport class)
        updated_count = 0
        for airport in self._airports.values():
            airport.update_all_derived_fields()
            updated_count += 1
        
        logger.info(f"Updated {updated_count} airports with all derived fields")
        logger.info("All derived fields updated successfully")
    
    def _update_border_crossing_airports(self) -> None:
        """
        Update airport objects with border crossing information.
        This is a model-level update that requires access to border_crossing_points.
        """
        updated_count = 0
        for entry in self.get_all_border_crossing_points():
            # Use the same logic as add_border_crossing_entry
            icao_code = entry.icao_code or entry.matched_airport_icao
            if icao_code and icao_code in self._airports:
                airport = self._airports[icao_code]
                airport.point_of_entry = True
                airport.add_source('border_crossing')
                updated_count += 1
        
        logger.info(f"Updated {updated_count} airports with border crossing information")
    
    def update_border_crossing_airports(self) -> None:
        """
        Legacy method - now calls the centralized update function.
        Kept for backward compatibility.
        """
        self._update_border_crossing_airports() 

    def find_airports_near_route(self, route_airports: List[Union[str, NavPoint]], distance_nm: float = 50.0) -> List[Dict[str, Any]]:
        """
        Find all airports within a specified distance from a route defined by airport ICAO codes
        or precomputed NavPoints.
        For single airports, treats them as a point search within the specified distance.
        
        Args:
            route_airports: List of ICAO airport codes or NavPoint objects defining the route
            distance_nm: Distance in nautical miles from the route (default: 50.0)
            
        Returns:
            List of dictionaries containing airport data and distance information, including:
            - airport: Airport object
            - segment_distance_nm: Perpendicular distance to the route in nautical miles
            - enroute_distance_nm: Distance along the route to the closest point in nautical miles
            - closest_segment: Tuple of (start_airport_name, end_airport_name) for the closest segment
        """
        if len(route_airports) < 1:
            logger.warning("Route must contain at least 1 airport")
            return []
        
        # Convert route inputs to NavPoints
        route_points = []
        for item in route_airports:
            if isinstance(item, NavPoint):
                route_points.append(item)
                continue
            # Assume string ICAO
            icao = str(item).upper()
            airport = self.get_airport(icao)
            if not airport or not airport.latitude_deg or not airport.longitude_deg:
                logger.warning(f"Airport {icao} not found or missing coordinates, skipping")
                continue
            if airport.navpoint:
                route_points.append(airport.navpoint)
        
        if len(route_points) < 1:
            logger.warning("No valid airports in route")
            return []
        
        # Calculate cumulative distances along the route (distance from start to each segment start)
        cumulative_distances = [0.0]  # Start at 0
        for i in range(len(route_points) - 1):
            _, segment_length = route_points[i].haversine_distance(route_points[i + 1])
            cumulative_distances.append(cumulative_distances[-1] + segment_length)
        
        # Find airports near the route
        nearby_airports = []
        
        for airport in self._airports.values():
            
            airport_point = airport.navpoint
            if not airport_point:
                continue  # Skip airports without coordinates
            
            # Calculate minimum distance to the route
            min_distance = float('inf')
            closest_segment = None
            enroute_distance = None
            
            if len(route_points) == 1:
                # Single airport: calculate direct distance to the point
                _, min_distance = airport_point.haversine_distance(route_points[0])
                closest_segment = (route_points[0].name, route_points[0].name)
                enroute_distance = 0.0  # At the starting point
            else:
                # Multiple airports: calculate minimum distance to any segment of the route
                for i in range(len(route_points) - 1):
                    segment_start = route_points[i]
                    segment_end = route_points[i + 1]
                    
                    # Calculate perpendicular distance to segment
                    segment_distance = airport_point.distance_to_segment(
                        segment_start, segment_end
                    )
                    
                    if segment_distance < min_distance:
                        min_distance = segment_distance
                        closest_segment = (segment_start.name, segment_end.name)
                        closest_segment_index = i
                        
                        # Calculate along-track distance within this segment
                        _, dist_AP = segment_start.haversine_distance(airport_point)
                        enroute_distance = cumulative_distances[i] + dist_AP  # At segment start
                        
            
            # Check if airport is within the specified distance
            if min_distance <= distance_nm:
                nearby_airports.append({
                    'airport': airport,
                    'segment_distance_nm': round(min_distance, 2),
                    'enroute_distance_nm': round(enroute_distance, 2) if enroute_distance is not None else None,
                    'closest_segment': closest_segment
                })
        
        # Sort by distance
        nearby_airports.sort(key=lambda x: x['segment_distance_nm'])
        
        logger.info(f"Found {len(nearby_airports)} airports within {distance_nm}nm of route")
        return nearby_airports
    
    def analyze_fields_with_interpreters(
        self, 
        interpreters: List['BaseInterpreter'], 
        country_filter: Optional[str] = None,
        airport_filter: Optional[List[str]] = None,
        custom_filter: Optional[Callable[['Airport'], bool]] = None
    ) -> Dict[str, 'InterpretationResult']:
        """
        Analyze multiple field types across airports using interpreters.
        
        Args:
            interpreters: List of interpreters to use for field analysis
            country_filter: Optional ISO country code to filter airports
            airport_filter: Optional list of specific airport ICAO codes
            custom_filter: Optional custom filter function taking Airport and returning bool
            
        Returns:
            Dictionary mapping interpreter names to InterpretationResult
        """
        from ..interp.base import InterpretationResult
        
        # Start with all airports
        candidate_airports = list(self._airports.keys())
        
        # Apply filters in intersection (all must pass)
        if country_filter:
            country_airports = [
                icao for icao, airport in self._airports.items()
                if airport.iso_country == country_filter
            ]
            candidate_airports = list(set(candidate_airports) & set(country_airports))
            logger.info(f"Country filter '{country_filter}': {len(candidate_airports)} airports")
        
        if airport_filter:
            airport_airports = [
                icao for icao in candidate_airports
                if icao in airport_filter
            ]
            candidate_airports = airport_airports
            logger.info(f"Airport filter: {len(candidate_airports)} airports")
        
        if custom_filter:
            custom_airports = [
                icao for icao in candidate_airports
                if custom_filter(self._airports[icao])
            ]
            candidate_airports = custom_airports
            logger.info(f"Custom filter: {len(candidate_airports)} airports")
        
        logger.info(f"Final candidate airports: {len(candidate_airports)}")
        
        # Process each interpreter
        results = {}
        
        for interpreter in interpreters:
            interpreter_name = interpreter.get_interpreter_name()
            field_id = interpreter.get_standard_field_id()
            
            logger.info(f"Processing {interpreter_name} interpreter for field {field_id}")
            
            successful = {}
            failed = []
            missing = []
            
            # Find airports with this field
            airports_with_field = []
            for icao in candidate_airports:
                airport = self._airports[icao]
                entry = airport.get_aip_entry_for_field(field_id)
                if entry and entry.value:
                    airports_with_field.append(icao)
            
            logger.info(f"Found {len(airports_with_field)} airports with field {field_id}")
            
            # Process each airport with the field
            for icao in airports_with_field:
                airport = self._airports[icao]
                entry = airport.get_aip_entry_for_field(field_id)
                
                if not entry or not entry.value:
                    missing.append(icao)
                    continue
                
                # Try to interpret the field value
                try:
                    interpreted_data = interpreter.interpret_field_value(entry.value, airport)
                    if interpreted_data:
                        successful[icao] = interpreted_data
                    else:
                        failed.append({
                            'airport_icao': icao,
                            'field_value': entry.value,
                            'reason': 'No structured data extracted',
                            'interpreter': interpreter_name
                        })
                except Exception as e:
                    failed.append({
                        'airport_icao': icao,
                        'field_value': entry.value,
                        'reason': f'Exception: {str(e)}',
                        'interpreter': interpreter_name
                    })
            
            # Create result for this interpreter
            results[interpreter_name] = InterpretationResult(
                successful=successful,
                failed=failed,
                missing=missing
            )
            
            logger.info(f"{interpreter_name}: {len(successful)} successful, {len(failed)} failed, {len(missing)} missing")
        
        return results