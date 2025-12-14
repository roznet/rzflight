"""
Specialized queryable collection for Procedure objects.

Provides domain-specific filtering methods for common procedure queries
while maintaining the composability of the base QueryableCollection.
"""

from typing import Optional, TYPE_CHECKING
from .queryable_collection import QueryableCollection

if TYPE_CHECKING:
    from .procedure import Procedure
    from .runway import Runway


class ProcedureCollection(QueryableCollection['Procedure']):
    """
    Specialized collection for querying procedures with domain-specific filters.

    Extends QueryableCollection with aviation-specific query methods for
    approaches, departures, and arrivals.

    Examples:
        # Filter by type
        collection.approaches()
        collection.departures()
        collection.arrivals()

        # Filter by approach type
        collection.approaches().by_type("ILS")

        # Filter by runway
        collection.by_runway("09L")

        # Chaining
        collection.approaches().by_type("ILS").by_runway("09L")

        # Get most precise
        collection.approaches().by_runway("09L").most_precise()
    """

    def approaches(self) -> 'ProcedureCollection':
        """
        Filter to approach procedures.

        Returns:
            New ProcedureCollection with only approach procedures

        Examples:
            # Get all approaches
            approaches = procedures.approaches()

            # Get all ILS approaches
            ils_approaches = procedures.approaches().by_type("ILS")
        """
        return ProcedureCollection([
            p for p in self._items if p.is_approach()
        ])

    def departures(self) -> 'ProcedureCollection':
        """
        Filter to departure procedures (SIDs).

        Returns:
            New ProcedureCollection with only departure procedures

        Examples:
            # Get all departures
            sids = procedures.departures()

            # Get departures for specific runway
            rwy_09l_sids = procedures.departures().by_runway("09L")
        """
        return ProcedureCollection([
            p for p in self._items if p.is_departure()
        ])

    def arrivals(self) -> 'ProcedureCollection':
        """
        Filter to arrival procedures (STARs).

        Returns:
            New ProcedureCollection with only arrival procedures

        Examples:
            # Get all arrivals
            stars = procedures.arrivals()
        """
        return ProcedureCollection([
            p for p in self._items if p.is_arrival()
        ])

    def by_type(self, approach_type: str) -> 'ProcedureCollection':
        """
        Filter procedures by approach type (ILS, VOR, RNAV, etc.).

        Args:
            approach_type: Approach type to filter by (case-insensitive)

        Returns:
            New ProcedureCollection with matching procedures

        Examples:
            # Get all ILS procedures
            ils = procedures.by_type("ILS")

            # Get ILS approaches only
            ils_approaches = procedures.approaches().by_type("ILS")

            # Get RNAV approaches
            rnav = procedures.approaches().by_type("RNAV")
        """
        approach_upper = approach_type.upper()
        return ProcedureCollection([
            p for p in self._items
            if p.approach_type and p.approach_type.upper() == approach_upper
        ])

    def by_runway(self, runway_ident: str) -> 'ProcedureCollection':
        """
        Filter procedures by runway identifier.

        Args:
            runway_ident: Runway identifier (e.g., "09L", "27R", "24")

        Returns:
            New ProcedureCollection with procedures for the runway

        Examples:
            # Get all procedures for runway 09L
            rwy_09l = procedures.by_runway("09L")

            # Get approaches for runway 09L
            rwy_09l_approaches = procedures.approaches().by_runway("09L")
        """
        return ProcedureCollection([
            p for p in self._items
            if p.runway_ident == runway_ident
        ])

    def for_runway(self, runway: 'Runway') -> 'ProcedureCollection':
        """
        Filter procedures by Runway object (matches either end).

        Args:
            runway: Runway object to match

        Returns:
            New ProcedureCollection with procedures for the runway

        Examples:
            # Get procedures for a runway object
            rwy_procs = procedures.for_runway(runway)
        """
        return ProcedureCollection([
            p for p in self._items
            if p.matches_runway(runway)
        ])

    def by_source(self, source: str) -> 'ProcedureCollection':
        """
        Filter procedures by data source.

        Args:
            source: Source name (e.g., "uk_eaip", "france_eaip")

        Returns:
            New ProcedureCollection with procedures from the source

        Examples:
            # Get procedures from UK eAIP
            uk_procs = procedures.by_source("uk_eaip")
        """
        return ProcedureCollection([
            p for p in self._items
            if p.source == source
        ])

    def by_authority(self, authority: str) -> 'ProcedureCollection':
        """
        Filter procedures by authority code.

        Args:
            authority: Authority code (e.g., "EGC", "LFC", "EDC")

        Returns:
            New ProcedureCollection with procedures from the authority

        Examples:
            # Get procedures from UK authority
            uk_auth = procedures.by_authority("EGC")
        """
        return ProcedureCollection([
            p for p in self._items
            if p.authority == authority
        ])

    def most_precise(self) -> Optional['Procedure']:
        """
        Get the most precise approach procedure from the collection.

        Returns:
            Most precise procedure, or None if collection is empty

        Examples:
            # Get most precise approach for a runway
            best = procedures.approaches().by_runway("09L").most_precise()

            # Check if it's ILS
            if best and best.approach_type == "ILS":
                print("ILS available")
        """
        approaches = [p for p in self._items if p.is_approach()]
        if not approaches:
            return None
        return min(approaches, key=lambda p: p.get_approach_precision())

    def by_precision_order(self) -> 'ProcedureCollection':
        """
        Sort approaches by precision (most precise first).

        Returns:
            New ProcedureCollection sorted by precision

        Examples:
            # Get approaches in order of precision
            ordered = procedures.approaches().by_precision_order()

            # Get top 3 most precise
            top_3 = procedures.approaches().by_precision_order().take(3)
        """
        return ProcedureCollection(
            sorted(
                [p for p in self._items if p.is_approach()],
                key=lambda p: p.get_approach_precision()
            )
        )

    def with_precision_better_than(self, approach_type: str) -> 'ProcedureCollection':
        """
        Filter to approaches with precision better than the specified type.

        Args:
            approach_type: Approach type to compare against

        Returns:
            New ProcedureCollection with more precise approaches

        Examples:
            # Get approaches better than VOR
            better_than_vor = procedures.approaches().with_precision_better_than("VOR")
            # Returns: ILS, RNP, RNAV
        """
        from .procedure import Procedure
        # Create a reference procedure to get the precision threshold
        reference = Procedure(name="ref", procedure_type="approach", approach_type=approach_type)
        threshold = reference.get_approach_precision()

        return ProcedureCollection([
            p for p in self._items
            if p.is_approach() and p.get_approach_precision() < threshold
        ])

    def precision_approaches(self) -> 'ProcedureCollection':
        """
        Filter to precision approaches (ILS).

        Returns:
            New ProcedureCollection with precision approaches

        Examples:
            # Get all precision approaches
            precision = procedures.precision_approaches()
        """
        return ProcedureCollection([
            p for p in self._items
            if p.is_approach() and p.approach_type and p.approach_type.upper() == 'ILS'
        ])

    def rnp_approaches(self) -> 'ProcedureCollection':
        """
        Filter to RNP/RNAV approaches.

        Returns:
            New ProcedureCollection with RNP/RNAV approaches

        Examples:
            # Get all satellite-based approaches
            satellite_approaches = procedures.rnp_approaches()
        """
        return ProcedureCollection([
            p for p in self._items
            if p.is_approach() and p.approach_type and p.approach_type.upper() in ['RNP', 'RNAV']
        ])

    def non_precision_approaches(self) -> 'ProcedureCollection':
        """
        Filter to non-precision approaches (VOR, NDB, LOC, etc.).

        Returns:
            New ProcedureCollection with non-precision approaches

        Examples:
            # Get all non-precision approaches
            non_precision = procedures.non_precision_approaches()
        """
        precision_types = {'ILS', 'RNP', 'RNAV'}
        return ProcedureCollection([
            p for p in self._items
            if p.is_approach() and p.approach_type and p.approach_type.upper() not in precision_types
        ])

    # Grouping methods

    def group_by_runway(self) -> dict:
        """
        Group procedures by runway identifier.

        Returns:
            Dictionary mapping runway identifiers to lists of procedures

        Examples:
            by_runway = procedures.group_by_runway()
            rwy_09l_procs = by_runway.get("09L", [])
        """
        return self.group_by(lambda p: p.runway_ident or 'unknown')

    def group_by_type(self) -> dict:
        """
        Group procedures by procedure type.

        Returns:
            Dictionary mapping procedure types to lists of procedures

        Examples:
            by_type = procedures.group_by_type()
            approaches = by_type.get("approach", [])
            departures = by_type.get("departure", [])
        """
        return self.group_by(lambda p: p.procedure_type.lower())

    def group_by_approach_type(self) -> dict:
        """
        Group approach procedures by approach type.

        Returns:
            Dictionary mapping approach types to lists of procedures

        Examples:
            by_approach_type = procedures.approaches().group_by_approach_type()
            ils_approaches = by_approach_type.get("ILS", [])
        """
        return self.group_by(lambda p: p.approach_type.upper() if p.approach_type else 'unknown')

    def group_by_source(self) -> dict:
        """
        Group procedures by data source.

        Returns:
            Dictionary mapping source names to lists of procedures
        """
        return self.group_by(lambda p: p.source or 'unknown')

    def group_by_authority(self) -> dict:
        """
        Group procedures by authority.

        Returns:
            Dictionary mapping authority codes to lists of procedures
        """
        return self.group_by(lambda p: p.authority or 'unknown')
