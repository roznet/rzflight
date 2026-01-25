"""Pre-configured filter combinations for common use cases."""

from typing import TYPE_CHECKING

from euro_aip.briefing.models.notam import NotamCategory

if TYPE_CHECKING:
    from euro_aip.briefing.collections.notam_collection import NotamCollection
    from euro_aip.briefing.models.route import Route


class NotamFilterPresets:
    """
    Pre-configured filter combinations for common use cases.

    Provides convenient methods for filtering NOTAMs by operational relevance.

    Example:
        # Get critical NOTAMs for departure
        departure_notams = NotamFilterPresets.departure_critical(
            briefing.notams_query,
            "LFPG"
        )

        # Get VFR-relevant NOTAMs
        vfr_notams = NotamFilterPresets.vfr_relevant(
            briefing.notams_query,
            "EGLL"
        )
    """

    @staticmethod
    def departure_critical(
        collection: 'NotamCollection',
        icao: str
    ) -> 'NotamCollection':
        """
        NOTAMs critical for departure from an airport.

        Includes: runway, taxiway, lighting, procedures, obstacles

        Args:
            collection: NotamCollection to filter
            icao: Departure airport ICAO code

        Returns:
            Filtered NotamCollection
        """
        airport_notams = collection.for_airport(icao).active_now()

        critical_categories = (
            collection.runway_related() |
            collection.by_category(NotamCategory.AGA_MOVEMENT) |
            collection.by_category(NotamCategory.AGA_LIGHTING) |
            collection.by_category(NotamCategory.OTHER_INFO) |
            collection.procedure_related()
        )

        return airport_notams & critical_categories

    @staticmethod
    def arrival_critical(
        collection: 'NotamCollection',
        icao: str
    ) -> 'NotamCollection':
        """
        NOTAMs critical for arrival at an airport.

        Includes: runway, navigation aids, procedures, lighting

        Args:
            collection: NotamCollection to filter
            icao: Arrival airport ICAO code

        Returns:
            Filtered NotamCollection
        """
        airport_notams = collection.for_airport(icao).active_now()

        critical_categories = (
            collection.runway_related() |
            collection.navigation_related() |
            collection.procedure_related() |
            collection.by_category(NotamCategory.AGA_LIGHTING)
        )

        return airport_notams & critical_categories

    @staticmethod
    def enroute_relevant(
        collection: 'NotamCollection',
        route: 'Route',
        flight_level: int
    ) -> 'NotamCollection':
        """
        NOTAMs relevant for enroute portion of flight.

        Includes: airspace restrictions at relevant altitudes

        Args:
            collection: NotamCollection to filter
            route: Route object
            flight_level: Cruise flight level (e.g., 350 for FL350)

        Returns:
            Filtered NotamCollection
        """
        altitude_ft = flight_level * 100
        altitude_band = 2000  # +/- 2000ft

        return (
            collection
            .airspace_related()
            .active_now()
            .in_altitude_range(altitude_ft - altitude_band, altitude_ft + altitude_band)
        )

    @staticmethod
    def vfr_relevant(
        collection: 'NotamCollection',
        icao: str
    ) -> 'NotamCollection':
        """
        NOTAMs relevant for VFR operations.

        Focuses on visual elements and low-altitude concerns.

        Args:
            collection: NotamCollection to filter
            icao: Airport ICAO code

        Returns:
            Filtered NotamCollection
        """
        airport_notams = collection.for_airport(icao).active_now()

        vfr_categories = (
            collection.runway_related() |
            collection.airspace_related() |
            collection.by_category(NotamCategory.OTHER_INFO) |
            collection.by_custom_category('wildlife')
        )

        # VFR typically below 10,000ft
        low_altitude = collection.below_altitude(10000)

        return airport_notams & vfr_categories & low_altitude

    @staticmethod
    def ifr_relevant(
        collection: 'NotamCollection',
        icao: str
    ) -> 'NotamCollection':
        """
        NOTAMs relevant for IFR operations.

        Focuses on navigation and instrument procedures.

        Args:
            collection: NotamCollection to filter
            icao: Airport ICAO code

        Returns:
            Filtered NotamCollection
        """
        airport_notams = collection.for_airport(icao).active_now()

        ifr_categories = (
            collection.runway_related() |
            collection.navigation_related() |
            collection.procedure_related() |
            collection.by_category(NotamCategory.AGA_LIGHTING) |
            collection.by_category(NotamCategory.CNS_COMMUNICATIONS)
        )

        return airport_notams & ifr_categories

    @staticmethod
    def obstacles_along_route(
        collection: 'NotamCollection',
        route: 'Route',
        corridor_nm: float = 10
    ) -> 'NotamCollection':
        """
        Obstacle NOTAMs along a route corridor.

        Args:
            collection: NotamCollection to filter
            route: Route object
            corridor_nm: Corridor width in nautical miles

        Returns:
            Filtered NotamCollection
        """
        return (
            collection
            .obstacle_related()
            .active_now()
            .along_route(route, corridor_nm=corridor_nm)
        )

    @staticmethod
    def airspace_along_route(
        collection: 'NotamCollection',
        route: 'Route',
        corridor_nm: float = 25
    ) -> 'NotamCollection':
        """
        Airspace NOTAMs along a route corridor.

        Args:
            collection: NotamCollection to filter
            route: Route object
            corridor_nm: Corridor width in nautical miles

        Returns:
            Filtered NotamCollection
        """
        return (
            collection
            .airspace_related()
            .active_now()
            .along_route(route, corridor_nm=corridor_nm)
        )

    @staticmethod
    def full_route(
        collection: 'NotamCollection',
        route: 'Route',
        flight_level: int = 0
    ) -> 'NotamCollection':
        """
        All NOTAMs relevant to a complete flight.

        Combines departure, enroute, and arrival NOTAMs.

        Args:
            collection: NotamCollection to filter
            route: Route object
            flight_level: Cruise flight level (0 = include all altitudes)

        Returns:
            Filtered NotamCollection
        """
        # Departure airport
        departure = NotamFilterPresets.departure_critical(collection, route.departure)

        # Destination airport
        arrival = NotamFilterPresets.arrival_critical(collection, route.destination)

        # Alternates
        alternate_notams = collection.for_airports(route.alternates).active_now()

        # Combine
        result = departure | arrival | alternate_notams

        # Add enroute if flight level specified
        if flight_level > 0:
            enroute = NotamFilterPresets.enroute_relevant(collection, route, flight_level)
            result = result | enroute

        return result

    @staticmethod
    def services_affected(collection: 'NotamCollection', icao: str) -> 'NotamCollection':
        """
        NOTAMs affecting airport services.

        Includes: ATC, fuel, fire services, etc.

        Args:
            collection: NotamCollection to filter
            icao: Airport ICAO code

        Returns:
            Filtered NotamCollection
        """
        return (
            collection
            .for_airport(icao)
            .active_now()
            .by_category(NotamCategory.ATM_SERVICES)
        )

    @staticmethod
    def communication_affected(
        collection: 'NotamCollection',
        icao: str
    ) -> 'NotamCollection':
        """
        NOTAMs affecting communications.

        Args:
            collection: NotamCollection to filter
            icao: Airport ICAO code

        Returns:
            Filtered NotamCollection
        """
        return (
            collection
            .for_airport(icao)
            .active_now()
            .by_category(NotamCategory.CNS_COMMUNICATIONS)
        )
