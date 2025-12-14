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
from .border_crossing_entry import BorderCrossingEntry
from .validation import ValidationResult, ValidationError, ModelValidationError
from .model_transaction import ModelTransaction
from .airport_builder import AirportBuilder

__all__ = [
    # Core models
    'Airport',
    'Runway',
    'AIPEntry',
    'Procedure',
    'EuroAipModel',
    'NavPoint',
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
] 