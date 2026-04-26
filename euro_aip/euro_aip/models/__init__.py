"""
Data models for the euro_aip library.

This package contains the data models used throughout the library
for representing airports, runways, AIP entries, procedures, and
the overall EuroAipModel.

The package also provides modern queryable collections for fluent,
composable querying of the data model.
"""

from .airport import Airport
from .runway import Runway
from .aip_entry import AIPEntry
from .procedure import Procedure
from .euro_aip_model import EuroAipModel
from .queryable_collection import QueryableCollection
from .airport_collection import AirportCollection
from .procedure_collection import ProcedureCollection
from .navpoint import NavPoint
from .waypoint import Waypoint
from .waypoint_collection import WaypointCollection
from .fir import FIR
from .fir_collection import FIRCollection
from .border_crossing_entry import BorderCrossingEntry
from .validation import ValidationResult, ValidationError, ModelValidationError
from .model_transaction import ModelTransaction
from .airport_builder import AirportBuilder
from .field15 import (
    TokenKind,
    RouteToken,
    parse_field15,
    waypoints_of,
    annotations_of,
)

__all__ = [
    # Core models
    'Airport',
    'Runway',
    'AIPEntry',
    'Procedure',
    'EuroAipModel',
    'NavPoint',
    'Waypoint',
    'WaypointCollection',
    'FIR',
    'FIRCollection',
    'RouteResolver',
    'BorderCrossingEntry',
    # Queryable collections
    'QueryableCollection',
    'AirportCollection',
    'ProcedureCollection',
    # Builder API
    'ValidationResult',
    'ValidationError',
    'ModelValidationError',
    'ModelTransaction',
    'AirportBuilder',
    # Field-15 tokenizer
    'TokenKind',
    'RouteToken',
    'parse_field15',
    'waypoints_of',
    'annotations_of',
]

def __getattr__(name):
    """Lazy import for RouteResolver to avoid circular import with briefing.models."""
    if name == "RouteResolver":
        from .route_resolver import RouteResolver
        return RouteResolver
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
