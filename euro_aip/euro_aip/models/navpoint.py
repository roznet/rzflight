#!/usr/bin/env python3

import math
from typing import Optional, Tuple, Union
from dataclasses import dataclass

@dataclass
class NavPoint:
    """
    A navigation point with coordinates and optional name.
    
    All coordinates are stored in decimal degrees:
    - Latitude: -90 to +90 degrees (negative for South, positive for North)
    - Longitude: -180 to +180 degrees (negative for West, positive for East)
    
    All distance calculations use nautical miles (1 nautical mile = 1.852 kilometers)
    All bearing calculations use degrees (0-360, where 0/360 is North, 90 is East, etc.)
    """
    
    latitude: float  # Decimal degrees, -90 to +90
    longitude: float  # Decimal degrees, -180 to +180
    name: Optional[str] = None  # Optional identifier for the point

    def __post_init__(self):
        """Validate coordinates after initialization."""
        if not -90 <= self.latitude <= 90:
            raise ValueError(f"Latitude must be between -90 and 90 degrees, got {self.latitude}")
        if not -180 <= self.longitude <= 180:
            raise ValueError(f"Longitude must be between -180 and 180 degrees, got {self.longitude}")

    def point_from_bearing_distance(self, bearing: float, distance: float, name: Optional[str] = None) -> 'NavPoint':
        """
        Create a new NavPoint from this point's position, bearing, and distance.
        
        Args:
            bearing: Bearing in degrees (0-360, where 0/360 is North, 90 is East, etc.)
            distance: Distance in nautical miles
            name: Optional name for the new point
            
        Returns:
            A new NavPoint at the calculated position
            
        Note:
            Uses the great circle calculation for accurate navigation distances
        """
        R = 3440  # Earth's radius in nautical miles

        # Convert to radians
        lat1 = math.radians(self.latitude)
        lon1 = math.radians(self.longitude)
        bearing_rad = math.radians(bearing)

        # Calculate new latitude
        lat2 = math.asin(
            math.sin(lat1) * math.cos(distance / R) +
            math.cos(lat1) * math.sin(distance / R) * math.cos(bearing_rad)
        )

        # Calculate new longitude
        lon2 = lon1 + math.atan2(
            math.sin(bearing_rad) * math.sin(distance / R) * math.cos(lat1),
            math.cos(distance / R) - math.sin(lat1) * math.sin(lat2)
        )

        return NavPoint(
            latitude=math.degrees(lat2),
            longitude=math.degrees(lon2),
            name=name
        )

    def haversine_distance(self, other: 'NavPoint') -> Tuple[float, float]:
        """
        Calculate the bearing and distance to another NavPoint using the Haversine formula.
        
        Args:
            other: The target NavPoint
            
        Returns:
            Tuple of (bearing in degrees, distance in nautical miles)
            - bearing: 0-360 degrees (0/360 is North, 90 is East, etc.)
            - distance: Distance in nautical miles
            
        Note:
            Uses the Haversine formula for accurate great circle calculations
        """
        # Convert to radians
        lat1 = math.radians(self.latitude)
        lon1 = math.radians(self.longitude)
        lat2 = math.radians(other.latitude)
        lon2 = math.radians(other.longitude)
        
        # Calculate differences
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        
        # Haversine formula
        a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        distance = 3440 * c  # Earth radius in nautical miles
        
        # Calculate bearing
        y = math.sin(dlon) * math.cos(lat2)
        x = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(dlon)
        bearing = math.degrees(math.atan2(y, x))
        bearing = (bearing + 360) % 360  # Normalize to [0, 360)
        
        return bearing, distance

    def to_dms(self) -> Tuple[str, str]:
        """
        Convert coordinates to Degrees, Minutes, Seconds format.
        
        Returns:
            Tuple of (latitude string, longitude string)
            Format: "DD° MM' SS\" [N/S]" for latitude
                   "DD° MM' SS\" [E/W]" for longitude
            Example: ("48° 51' 24\" N", "2° 21' 8\" E")
        """
        def decimal_to_dms(decimal_degrees: float, is_longitude: bool) -> str:
            direction = 'E' if is_longitude and decimal_degrees >= 0 else 'W' if is_longitude else 'N' if decimal_degrees >= 0 else 'S'
            decimal_degrees = abs(decimal_degrees)
            degrees = int(decimal_degrees)
            decimal_minutes = (decimal_degrees - degrees) * 60
            minutes = int(decimal_minutes)
            seconds = round((decimal_minutes - minutes) * 60, 2)
            return f"{degrees}° {minutes}' {seconds}\" {direction}"

        return (
            decimal_to_dms(self.latitude, False),
            decimal_to_dms(self.longitude, True)
        )

    def to_dm(self) -> Tuple[str, str]:
        """
        Convert coordinates to Degrees, Decimal Minutes format.
        
        Returns:
            Tuple of (latitude string, longitude string)
            Format: "DD° MM.MM' [N/S]" for latitude
                   "DD° MM.MM' [E/W]" for longitude
            Example: ("48° 51.40' N", "2° 21.13' E")
        """
        def decimal_to_dm(decimal_degrees: float, is_longitude: bool) -> str:
            direction = 'E' if is_longitude and decimal_degrees >= 0 else 'W' if is_longitude else 'N' if decimal_degrees >= 0 else 'S'
            decimal_degrees = abs(decimal_degrees)
            degrees = int(decimal_degrees)
            minutes = round((decimal_degrees - degrees) * 60, 2)
            return f"{degrees}° {minutes}' {direction}"

        return (
            decimal_to_dm(self.latitude, False),
            decimal_to_dm(self.longitude, True)
        )

    def to_csv(self) -> str:
        """
        Convert to CSV format.
        
        Returns:
            String in format: "name,description,latitude,longitude"
            where latitude and longitude are in decimal degrees
        """
        return f'{self.name or ""},"",{self.latitude},{self.longitude}'

    def __str__(self) -> str:
        """String representation of the NavPoint."""
        name_str = f"{self.name} " if self.name else ""
        return f"{name_str}({self.latitude}, {self.longitude})"

    def __repr__(self) -> str:
        """Detailed string representation of the NavPoint."""
        return f"NavPoint(name={self.name!r}, latitude={self.latitude}, longitude={self.longitude})" 
    

    def distance_to_segment(self, line_start: 'NavPoint', line_end: 'NavPoint') -> float:
        """
        Compute distance from this point to a segment defined by two NavPoints.
        Returns distance in nautical miles.
        """
        R = 3440.065  # Earth radius in nautical miles

        # Compute distances
        _, dist_AP = line_start.haversine_distance(self)
        _, dist_AB = line_start.haversine_distance(line_end)
        _, dist_BP = line_end.haversine_distance(self)

        # If segment is very short, just return distance to closest endpoint
        if dist_AB < 0.1:  # Less than 0.1nm
            return min(dist_AP, dist_BP)

        # Compute bearings
        bearing_AB, _ = line_start.haversine_distance(line_end)
        bearing_AP, _ = line_start.haversine_distance(self)

        # Convert to radians
        δ13 = dist_AP / R
        θ13 = math.radians(bearing_AP)
        θ12 = math.radians(bearing_AB)

        # Compute cross-track distance
        d_xt = math.asin(math.sin(δ13) * math.sin(θ13 - θ12)) * R

        # Handle numerical instability when point is very close to line
        if abs(d_xt) < 0.001:  # Point is very close to the great circle line
            # Calculate along-track distance more carefully
            cos_ratio = math.cos(δ13) / max(math.cos(d_xt / R), 0.0001)
            cos_ratio = max(min(cos_ratio, 1.0), -1.0)  # Clamp to valid range
            d_at_magnitude = math.acos(cos_ratio) * R
        else:
            # Standard along-track calculation
            cos_ratio = math.cos(δ13) / math.cos(d_xt / R)
            cos_ratio = max(min(cos_ratio, 1.0), -1.0)  # Clamp to valid range
            d_at_magnitude = math.acos(cos_ratio) * R

        # Determine the sign of along-track distance
        # If the bearing from start to point is more than 90° different from start to end,
        # then the projection is "behind" the start point
        bearing_diff = abs(bearing_AP - bearing_AB)
        if bearing_diff > 180:
            bearing_diff = 360 - bearing_diff
        
        if bearing_diff > 90:
            d_at = -d_at_magnitude  # Projection is behind start point
        else:
            d_at = d_at_magnitude   # Projection is in front of start point

        # Check if projection falls within the segment
        if d_at < 0:
            return dist_AP  # closest to start
        elif d_at > dist_AB:
            return dist_BP  # closest to end
        else:
            return abs(d_xt)