"""
European AIP (Aeronautical Information Publication) data processing library.

This package provides tools for parsing and processing European AIP documents
and airport data.

The main public API includes:
- Airport: Core airport data model
- NavPoint: Navigation point with coordinate calculations
- DatabaseSource: Direct access to precomputed airport database
- AIPParserFactory: Factory for creating AIP document parsers
- ProcedureParserFactory: Factory for creating procedure parsers
"""

from typing import List, Optional
from datetime import datetime

from .core.models import Airport
from .sources.autorouter import AutorouterSource
from .sources.france_eaip import FranceEAIPSource
from .models.navpoint import NavPoint
from .sources.database import DatabaseSource
from .parsers.aip_factory import AIPParserFactory
from .parsers.procedure_factory import ProcedureParserFactory

__version__ = '0.1.0'
__all__ = [
    'Airport',
    'NavPoint',
    'DatabaseSource',
    'AIPParserFactory',
    'ProcedureParserFactory'
]


