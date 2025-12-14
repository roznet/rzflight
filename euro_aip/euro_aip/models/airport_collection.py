"""
Specialized queryable collection for Airport objects.

Provides domain-specific filtering methods for common airport queries
while maintaining the composability of the base QueryableCollection.
"""

from typing import Optional, List, Set, TYPE_CHECKING
from .queryable_collection import QueryableCollection

if TYPE_CHECKING:
    from .airport import Airport


class AirportCollection(QueryableCollection['Airport']):
    """
    Specialized collection for querying airports with domain-specific filters.

    Extends QueryableCollection with aviation-specific query methods while
    maintaining full composability through method chaining.

    Examples:
        # Simple filters
        collection.by_country("FR")
        collection.with_runways()
        collection.with_procedures()

        # Chaining
        collection.by_country("FR").with_hard_runway().with_fuel(avgas=True)

        # Combining domain and generic filters
        collection.by_country("GB").filter(lambda a: a.longest_runway_length_ft and a.longest_runway_length_ft > 5000)

        # Results
        .all()      # Get list of airports
        .first()    # Get first airport or None
        .count()    # Get count
        .exists()   # Check if any match
    """

    def by_country(self, country_code: str) -> 'AirportCollection':
        """
        Filter airports by ISO country code.

        Args:
            country_code: ISO country code (e.g., "GB", "FR", "DE")

        Returns:
            New AirportCollection with filtered airports

        Examples:
            # Get all French airports
            french = airports.by_country("FR").all()

            # Chain with other filters
            french_with_ils = airports.by_country("FR").with_procedures("approach")
        """
        return AirportCollection([
            a for a in self._items
            if a.iso_country == country_code
        ])

    def by_countries(self, country_codes: List[str]) -> 'AirportCollection':
        """
        Filter airports by multiple ISO country codes.

        Args:
            country_codes: List of ISO country codes

        Returns:
            New AirportCollection with airports from any of the countries

        Examples:
            # Get airports from multiple countries
            schengen = airports.by_countries(["FR", "DE", "ES", "IT"])
        """
        country_set = set(country_codes)
        return AirportCollection([
            a for a in self._items
            if a.iso_country in country_set
        ])

    def by_source(self, source: str) -> 'AirportCollection':
        """
        Filter airports by data source.

        Args:
            source: Source name (e.g., "uk_eaip", "worldairports")

        Returns:
            New AirportCollection with airports from the source

        Examples:
            # Get airports from UK eAIP
            uk_eaip = airports.by_source("uk_eaip")
        """
        return AirportCollection([
            a for a in self._items
            if source in a.sources
        ])

    def by_sources(self, sources: List[str]) -> 'AirportCollection':
        """
        Filter airports that have data from any of the specified sources.

        Args:
            sources: List of source names

        Returns:
            New AirportCollection with airports from any of the sources

        Examples:
            # Get airports from multiple sources
            eaip_airports = airports.by_sources(["uk_eaip", "france_eaip"])
        """
        source_set = set(sources)
        return AirportCollection([
            a for a in self._items
            if bool(a.sources & source_set)
        ])

    def with_runways(self) -> 'AirportCollection':
        """
        Filter to airports with runway information.

        Returns:
            New AirportCollection with airports that have runways

        Examples:
            # Get airports with runway data
            with_runways = airports.with_runways()

            # Chain with other filters
            french_with_runways = airports.by_country("FR").with_runways()
        """
        return AirportCollection([
            a for a in self._items
            if a.runways
        ])

    def with_procedures(self, procedure_type: Optional[str] = None) -> 'AirportCollection':
        """
        Filter to airports with procedures, optionally by type.

        Args:
            procedure_type: Optional procedure type filter ('approach', 'departure', 'arrival')

        Returns:
            New AirportCollection with airports that have procedures

        Examples:
            # All airports with any procedures
            with_procs = airports.with_procedures()

            # Airports with approach procedures
            with_approaches = airports.with_procedures("approach")

            # Chain: French airports with departure procedures
            french_sids = airports.by_country("FR").with_procedures("departure")
        """
        if procedure_type:
            proc_type_lower = procedure_type.lower()
            return AirportCollection([
                a for a in self._items
                if any(p.procedure_type.lower() == proc_type_lower for p in a.procedures)
            ])
        return AirportCollection([
            a for a in self._items
            if a.procedures
        ])

    def with_aip_data(self) -> 'AirportCollection':
        """
        Filter to airports with AIP data entries.

        Returns:
            New AirportCollection with airports that have AIP data

        Examples:
            # Airports with AIP data
            with_aip = airports.with_aip_data()
        """
        return AirportCollection([
            a for a in self._items
            if a.aip_entries
        ])

    def with_standardized_aip_data(self) -> 'AirportCollection':
        """
        Filter to airports with standardized AIP data.

        Returns:
            New AirportCollection with airports that have standardized AIP entries

        Examples:
            # Airports with standardized AIP data
            standardized = airports.with_standardized_aip_data()
        """
        return AirportCollection([
            a for a in self._items
            if a.get_standardized_entries()
        ])

    def with_hard_runway(self) -> 'AirportCollection':
        """
        Filter to airports with hard surface runways (concrete, asphalt).

        Returns:
            New AirportCollection with airports that have hard runways

        Examples:
            # Airports with paved runways
            paved = airports.with_hard_runway()

            # French airports with paved runways
            french_paved = airports.by_country("FR").with_hard_runway()
        """
        return AirportCollection([
            a for a in self._items
            if a.has_hard_runway
        ])

    def with_soft_runway(self) -> 'AirportCollection':
        """
        Filter to airports with soft surface runways (grass, dirt).

        Returns:
            New AirportCollection with airports that have soft runways
        """
        return AirportCollection([
            a for a in self._items
            if a.has_soft_runway
        ])

    def with_water_runway(self) -> 'AirportCollection':
        """
        Filter to airports with water runways.

        Returns:
            New AirportCollection with seaplane bases
        """
        return AirportCollection([
            a for a in self._items
            if a.has_water_runway
        ])

    def with_lighted_runway(self) -> 'AirportCollection':
        """
        Filter to airports with at least one lighted runway.

        Returns:
            New AirportCollection with airports that have lighted runways

        Examples:
            # Airports suitable for night operations
            night_ops = airports.with_lighted_runway()
        """
        return AirportCollection([
            a for a in self._items
            if a.has_lighted_runway
        ])

    def with_fuel(self, avgas: bool = False, jet_a: bool = False) -> 'AirportCollection':
        """
        Filter airports by fuel availability.

        Args:
            avgas: If True, filter to airports with AVGAS
            jet_a: If True, filter to airports with Jet A

        Returns:
            New AirportCollection with airports that have the specified fuel(s)

        Examples:
            # Airports with AVGAS
            with_avgas = airports.with_fuel(avgas=True)

            # Airports with Jet A
            with_jet = airports.with_fuel(jet_a=True)

            # Airports with both
            full_service = airports.with_fuel(avgas=True, jet_a=True)
        """
        result = list(self._items)
        if avgas:
            result = [a for a in result if a.avgas]
        if jet_a:
            result = [a for a in result if a.jet_a]
        return AirportCollection(result)

    def border_crossings(self) -> 'AirportCollection':
        """
        Filter to airports designated as border crossing points.

        Returns:
            New AirportCollection with border crossing airports

        Examples:
            # Get all points of entry
            entry_points = airports.border_crossings()

            # Points of entry in France
            french_entry = airports.by_country("FR").border_crossings()
        """
        return AirportCollection([
            a for a in self._items
            if a.point_of_entry
        ])

    def with_min_runway_length(self, min_length_ft: int) -> 'AirportCollection':
        """
        Filter to airports with runway length at least min_length_ft.

        Args:
            min_length_ft: Minimum runway length in feet

        Returns:
            New AirportCollection with airports meeting the runway length requirement

        Examples:
            # Airports suitable for jets (5000+ ft)
            jet_capable = airports.with_min_runway_length(5000)

            # Large aircraft capable (8000+ ft)
            heavy_capable = airports.with_min_runway_length(8000)
        """
        return AirportCollection([
            a for a in self._items
            if a.longest_runway_length_ft and a.longest_runway_length_ft >= min_length_ft
        ])

    def with_approach_type(self, approach_type: str) -> 'AirportCollection':
        """
        Filter to airports with specific approach type.

        Args:
            approach_type: Approach type (e.g., "ILS", "RNAV", "VOR")

        Returns:
            New AirportCollection with airports that have the approach type

        Examples:
            # Airports with ILS
            with_ils = airports.with_approach_type("ILS")

            # French airports with RNAV approaches
            french_rnav = airports.by_country("FR").with_approach_type("RNAV")
        """
        approach_upper = approach_type.upper()
        return AirportCollection([
            a for a in self._items
            if any(
                p.is_approach() and p.approach_type and p.approach_type.upper() == approach_upper
                for p in a.procedures
            )
        ])

    def in_region(self, region_code: str) -> 'AirportCollection':
        """
        Filter airports by ISO region code.

        Args:
            region_code: ISO region code (e.g., "GB-ENG", "FR-IDF")

        Returns:
            New AirportCollection with airports in the region

        Examples:
            # Airports in England
            england = airports.in_region("GB-ENG")
        """
        return AirportCollection([
            a for a in self._items
            if a.iso_region == region_code
        ])

    def with_coordinates(self) -> 'AirportCollection':
        """
        Filter to airports with valid coordinates.

        Returns:
            New AirportCollection with airports that have lat/lon data
        """
        return AirportCollection([
            a for a in self._items
            if a.latitude_deg is not None and a.longitude_deg is not None
        ])

    def with_scheduled_service(self) -> 'AirportCollection':
        """
        Filter to airports with scheduled airline service.

        Returns:
            New AirportCollection with airports that have scheduled service
        """
        return AirportCollection([
            a for a in self._items
            if a.scheduled_service == 'yes'
        ])

    def by_continent(self, continent: str) -> 'AirportCollection':
        """
        Filter airports by continent code.

        Args:
            continent: Continent code (e.g., "EU", "NA", "AS")

        Returns:
            New AirportCollection with airports on the continent

        Examples:
            # All European airports
            europe = airports.by_continent("EU")
        """
        return AirportCollection([
            a for a in self._items
            if a.continent == continent
        ])

    # Grouping methods that return dictionaries

    def group_by_country(self) -> dict:
        """
        Group airports by country.

        Returns:
            Dictionary mapping country codes to lists of airports

        Examples:
            by_country = airports.group_by_country()
            french_airports = by_country.get("FR", [])
        """
        return self.group_by(lambda a: a.iso_country or 'unknown')

    def group_by_source(self) -> dict:
        """
        Group airports by their primary source (first source in set).

        Returns:
            Dictionary mapping source names to lists of airports

        Note:
            Airports may appear in multiple groups if they have multiple sources.
        """
        result = {}
        for airport in self._items:
            for source in airport.sources:
                if source not in result:
                    result[source] = []
                result[source].append(airport)
        return result

    def group_by_continent(self) -> dict:
        """
        Group airports by continent.

        Returns:
            Dictionary mapping continent codes to lists of airports
        """
        return self.group_by(lambda a: a.continent or 'unknown')

    def group_by_region(self) -> dict:
        """
        Group airports by ISO region.

        Returns:
            Dictionary mapping region codes to lists of airports
        """
        return self.group_by(lambda a: a.iso_region or 'unknown')
