"""Route data models."""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional, Tuple, List, Dict

from euro_aip.models.navpoint import NavPoint


@dataclass
class RoutePoint:
    """
    A point along a route with coordinates.

    Attributes:
        name: Waypoint name or ICAO code
        latitude: Latitude in decimal degrees
        longitude: Longitude in decimal degrees
        point_type: Type of point (departure, destination, alternate, waypoint)
    """
    name: str
    latitude: float
    longitude: float
    point_type: str = "waypoint"  # "departure", "destination", "alternate", "waypoint"

    @property
    def navpoint(self) -> NavPoint:
        """Get NavPoint for distance calculations."""
        return NavPoint(
            latitude=self.latitude,
            longitude=self.longitude,
            name=self.name
        )

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            'name': self.name,
            'latitude': self.latitude,
            'longitude': self.longitude,
            'point_type': self.point_type,
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'RoutePoint':
        """Create from dictionary."""
        return cls(
            name=data['name'],
            latitude=data['latitude'],
            longitude=data['longitude'],
            point_type=data.get('point_type', 'waypoint'),
        )


@dataclass
class Route:
    """
    Flight route information with coordinates for spatial queries.

    Supports coordinate lookups for departure, destination, alternates,
    and waypoints. Integrates with NavPoint for distance calculations.

    Attributes:
        departure: Departure airport ICAO code
        destination: Destination airport ICAO code
        alternates: List of alternate airport ICAO codes
        waypoints: List of waypoint names along the route
    """
    departure: str
    destination: str
    alternates: List[str] = field(default_factory=list)
    waypoints: List[str] = field(default_factory=list)

    # Coordinates for spatial queries
    departure_coords: Optional[Tuple[float, float]] = None
    destination_coords: Optional[Tuple[float, float]] = None
    alternate_coords: Dict[str, Tuple[float, float]] = field(default_factory=dict)
    waypoint_coords: List[RoutePoint] = field(default_factory=list)

    # Flight details
    aircraft_type: Optional[str] = None
    departure_time: Optional[datetime] = None
    arrival_time: Optional[datetime] = None
    flight_level: Optional[int] = None
    cruise_altitude_ft: Optional[int] = None

    def get_all_airports(self) -> List[str]:
        """
        Get all airports involved in the route.

        Returns:
            List of unique ICAO codes for departure, destination, and alternates.
        """
        airports = [self.departure, self.destination]
        airports.extend(self.alternates)
        return list(dict.fromkeys(airports))  # Preserve order, remove duplicates

    def get_all_coordinates(self) -> List[Tuple[float, float]]:
        """
        Get all route coordinates for spatial queries.

        Returns ordered list of coordinates from departure through waypoints
        to destination.
        """
        coords = []
        if self.departure_coords:
            coords.append(self.departure_coords)
        coords.extend([(wp.latitude, wp.longitude) for wp in self.waypoint_coords])
        if self.destination_coords:
            coords.append(self.destination_coords)
        return coords

    def get_airport_coordinates(self) -> Dict[str, Tuple[float, float]]:
        """
        Get coordinates for all airports in route.

        Returns:
            Dict mapping ICAO codes to (lat, lon) tuples.
        """
        coords = {}
        if self.departure_coords:
            coords[self.departure] = self.departure_coords
        if self.destination_coords:
            coords[self.destination] = self.destination_coords
        coords.update(self.alternate_coords)
        return coords

    def get_route_navpoints(self) -> List[NavPoint]:
        """
        Get NavPoints for the full route.

        Returns:
            List of NavPoints from departure through waypoints to destination.
        """
        points = []
        if self.departure_coords:
            points.append(NavPoint(
                latitude=self.departure_coords[0],
                longitude=self.departure_coords[1],
                name=self.departure
            ))
        points.extend([wp.navpoint for wp in self.waypoint_coords])
        if self.destination_coords:
            points.append(NavPoint(
                latitude=self.destination_coords[0],
                longitude=self.destination_coords[1],
                name=self.destination
            ))
        return points

    def get_flight_window(self, buffer_minutes: int = 60) -> Tuple[datetime, datetime]:
        """
        Get the time window for the flight.

        Args:
            buffer_minutes: Buffer time after arrival (default 60 minutes)

        Returns:
            Tuple of (departure_time, arrival_time + buffer)

        Raises:
            ValueError: If departure_time is not set
        """
        if not self.departure_time:
            raise ValueError("Departure time not set")

        end_time = self.arrival_time or self.departure_time
        return (self.departure_time, end_time + timedelta(minutes=buffer_minutes))

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            'departure': self.departure,
            'destination': self.destination,
            'alternates': self.alternates,
            'waypoints': self.waypoints,
            'departure_coords': list(self.departure_coords) if self.departure_coords else None,
            'destination_coords': list(self.destination_coords) if self.destination_coords else None,
            'alternate_coords': {k: list(v) for k, v in self.alternate_coords.items()},
            'waypoint_coords': [wp.to_dict() for wp in self.waypoint_coords],
            'aircraft_type': self.aircraft_type,
            'departure_time': self.departure_time.isoformat() if self.departure_time else None,
            'arrival_time': self.arrival_time.isoformat() if self.arrival_time else None,
            'flight_level': self.flight_level,
            'cruise_altitude_ft': self.cruise_altitude_ft,
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'Route':
        """Create from dictionary."""
        departure_time = None
        if data.get('departure_time'):
            departure_time = datetime.fromisoformat(data['departure_time'])

        arrival_time = None
        if data.get('arrival_time'):
            arrival_time = datetime.fromisoformat(data['arrival_time'])

        departure_coords = None
        if data.get('departure_coords'):
            departure_coords = tuple(data['departure_coords'])

        destination_coords = None
        if data.get('destination_coords'):
            destination_coords = tuple(data['destination_coords'])

        alternate_coords = {}
        if data.get('alternate_coords'):
            alternate_coords = {k: tuple(v) for k, v in data['alternate_coords'].items()}

        waypoint_coords = []
        if data.get('waypoint_coords'):
            waypoint_coords = [RoutePoint.from_dict(wp) for wp in data['waypoint_coords']]

        return cls(
            departure=data['departure'],
            destination=data['destination'],
            alternates=data.get('alternates', []),
            waypoints=data.get('waypoints', []),
            departure_coords=departure_coords,
            destination_coords=destination_coords,
            alternate_coords=alternate_coords,
            waypoint_coords=waypoint_coords,
            aircraft_type=data.get('aircraft_type'),
            departure_time=departure_time,
            arrival_time=arrival_time,
            flight_level=data.get('flight_level'),
            cruise_altitude_ft=data.get('cruise_altitude_ft'),
        )

    def __repr__(self) -> str:
        return f"Route({self.departure} -> {self.destination})"
