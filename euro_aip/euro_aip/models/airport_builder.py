"""
Fluent builder for constructing Airport objects.

This module provides the AirportBuilder class that allows constructing
airports using a fluent, chainable API with built-in validation.
"""

from typing import TYPE_CHECKING, List, Dict, Any, Optional
import logging

from .validation import ValidationResult, ModelValidationError
from .airport import Airport
from .runway import Runway
from .aip_entry import AIPEntry
from .procedure import Procedure

if TYPE_CHECKING:
    from .euro_aip_model import EuroAipModel

logger = logging.getLogger(__name__)


class AirportBuilder:
    """
    Fluent builder for constructing airports with validation.

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

    def __init__(self, model: 'EuroAipModel', icao: str):
        """
        Initialize airport builder.

        Args:
            model: The EuroAipModel this builder is associated with
            icao: ICAO code for the airport
        """
        self.model = model
        self.icao = icao
        self._airport = Airport(ident=icao)
        self._runways: List[Runway] = []
        self._procedures: List[Procedure] = []
        self._aip_entries: List[AIPEntry] = []
        self._sources: set = set()

    def with_basic_info(
        self,
        name: Optional[str] = None,
        latitude_deg: Optional[float] = None,
        longitude_deg: Optional[float] = None,
        elevation_ft: Optional[int] = None,
        iso_country: Optional[str] = None,
        iso_region: Optional[str] = None,
        municipality: Optional[str] = None,
        iata_code: Optional[str] = None,
        **kwargs
    ) -> 'AirportBuilder':
        """
        Set basic airport information.

        Args:
            name: Airport name
            latitude_deg: Latitude in degrees
            longitude_deg: Longitude in degrees
            elevation_ft: Elevation in feet
            iso_country: ISO country code
            iso_region: ISO region code
            municipality: Municipality name
            iata_code: IATA code
            **kwargs: Additional fields to set

        Returns:
            Self for chaining
        """
        if name is not None:
            self._airport.name = name
        if latitude_deg is not None:
            self._airport.latitude_deg = latitude_deg
        if longitude_deg is not None:
            self._airport.longitude_deg = longitude_deg
        if elevation_ft is not None:
            self._airport.elevation_ft = elevation_ft
        if iso_country is not None:
            self._airport.iso_country = iso_country
        if iso_region is not None:
            self._airport.iso_region = iso_region
        if municipality is not None:
            self._airport.municipality = municipality
        if iata_code is not None:
            self._airport.iata_code = iata_code

        # Set any additional kwargs
        for key, value in kwargs.items():
            if hasattr(self._airport, key):
                setattr(self._airport, key, value)
            else:
                logger.warning(f"Airport has no attribute '{key}', ignoring")

        return self

    def with_runways(self, runways: List[Runway]) -> 'AirportBuilder':
        """
        Add runways to the airport.

        Args:
            runways: List of Runway objects

        Returns:
            Self for chaining
        """
        self._runways.extend(runways)
        return self

    def with_runway(self, runway: Runway) -> 'AirportBuilder':
        """
        Add a single runway to the airport.

        Args:
            runway: Runway object

        Returns:
            Self for chaining
        """
        self._runways.append(runway)
        return self

    def with_procedures(self, procedures: List[Procedure]) -> 'AirportBuilder':
        """
        Add procedures to the airport.

        Args:
            procedures: List of Procedure objects

        Returns:
            Self for chaining
        """
        self._procedures.extend(procedures)
        return self

    def with_procedure(self, procedure: Procedure) -> 'AirportBuilder':
        """
        Add a single procedure to the airport.

        Args:
            procedure: Procedure object

        Returns:
            Self for chaining
        """
        self._procedures.append(procedure)
        return self

    def with_aip_entries(self, entries: List[AIPEntry], standardize: bool = True) -> 'AirportBuilder':
        """
        Add AIP entries to the airport.

        Args:
            entries: List of AIPEntry objects
            standardize: Whether to standardize entries using field service

        Returns:
            Self for chaining
        """
        if standardize and self.model.field_service:
            entries = self.model.field_service.standardize_aip_entries(entries)
        self._aip_entries.extend(entries)
        return self

    def with_aip_entry(self, entry: AIPEntry, standardize: bool = True) -> 'AirportBuilder':
        """
        Add a single AIP entry to the airport.

        Args:
            entry: AIPEntry object
            standardize: Whether to standardize the entry

        Returns:
            Self for chaining
        """
        if standardize and self.model.field_service:
            entry = self.model.field_service.standardize_aip_entries([entry])[0]
        self._aip_entries.append(entry)
        return self

    def with_sources(self, sources: List[str]) -> 'AirportBuilder':
        """
        Add data sources to the airport.

        Args:
            sources: List of source names

        Returns:
            Self for chaining
        """
        self._sources.update(sources)
        return self

    def with_source(self, source: str) -> 'AirportBuilder':
        """
        Add a single data source to the airport.

        Args:
            source: Source name

        Returns:
            Self for chaining
        """
        self._sources.add(source)
        return self

    def validate(self) -> ValidationResult:
        """
        Validate the airport before building.

        Returns:
            ValidationResult with validation status and errors
        """
        result = ValidationResult()

        # Basic validation
        if not self.icao or len(self.icao) != 4:
            result.add_error("ident", "ICAO code must be 4 characters", self.icao)

        if not self._airport.latitude_deg or not self._airport.longitude_deg:
            result.add_error("coordinates", "Latitude and longitude are required")

        # Validate that coordinates are in valid range
        if self._airport.latitude_deg is not None:
            if not -90 <= self._airport.latitude_deg <= 90:
                result.add_error(
                    "latitude_deg",
                    "Latitude must be between -90 and 90",
                    self._airport.latitude_deg
                )

        if self._airport.longitude_deg is not None:
            if not -180 <= self._airport.longitude_deg <= 180:
                result.add_error(
                    "longitude_deg",
                    "Longitude must be between -180 and 180",
                    self._airport.longitude_deg
                )

        # Validate runways
        for i, runway in enumerate(self._runways):
            if not runway.le_ident:
                result.add_error(
                    f"runway[{i}]",
                    "Runway must have le_ident"
                )

        return result

    def build(self) -> Airport:
        """
        Build the airport object (does not add to model).

        Returns:
            Built Airport object

        Raises:
            ModelValidationError: If validation fails
        """
        # Validate first
        validation = self.validate()
        if not validation.is_valid:
            raise ModelValidationError(
                f"Cannot build airport {self.icao}: validation failed",
                validation_result=validation
            )

        # Add all components
        for runway in self._runways:
            self._airport.add_runway(runway)

        for procedure in self._procedures:
            self._airport.add_procedure(procedure)

        for entry in self._aip_entries:
            self._airport.add_aip_entry(entry)

        for source in self._sources:
            self._airport.add_source(source)

        logger.debug(f"Built airport {self.icao} with {len(self._runways)} runways, "
                    f"{len(self._procedures)} procedures, {len(self._aip_entries)} AIP entries")

        return self._airport

    def commit(self, update_derived: bool = True) -> Airport:
        """
        Build and add to model.

        Args:
            update_derived: Whether to update derived fields after adding

        Returns:
            Built and added Airport object

        Raises:
            ModelValidationError: If validation fails
        """
        airport = self.build()
        self.model.add_airport(airport)

        if update_derived:
            airport.update_all_derived_fields()

        logger.info(f"Committed airport {self.icao} to model")
        return airport
