from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional, Tuple

@dataclass
class Airport:
    """Represents an airport with its basic information."""
    icao: str
    name: str
    location: Tuple[float, float]  # (latitude, longitude)
    elevation_ft: float
    country: str
    city: str
    continent: str
    type: str
    last_updated: datetime
    version: int  # For tracking changes

@dataclass
class Runway:
    """Represents a runway at an airport."""
    airport_icao: str
    ident: str
    length_ft: float
    width_ft: float
    surface_type: str
    heading_deg: float
    last_updated: datetime
    version: int

@dataclass
class Procedure:
    """Represents an airport procedure (approach, departure, arrival)."""
    airport_icao: str
    runway_ident: str
    type: str  # approach, departure, arrival
    name: str
    last_updated: datetime
    version: int 