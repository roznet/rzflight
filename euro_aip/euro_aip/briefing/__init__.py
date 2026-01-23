"""
Briefing module for parsing and filtering flight briefing data.

This module provides tools for:
- Parsing NOTAMs from ForeFlight PDFs and other sources
- Filtering and categorizing NOTAMs by location, time, category, and spatial criteria
- Integrating with euro_aip for airport coordinate lookups

Example usage:
    from euro_aip.briefing import ForeFlightSource, NotamCollection
    from euro_aip.briefing.categorization import CategorizationPipeline

    # Parse a ForeFlight briefing PDF
    source = ForeFlightSource(cache_dir="./cache")
    briefing = source.parse("path/to/briefing.pdf")

    # Apply categorization
    pipeline = CategorizationPipeline()
    pipeline.categorize_all(briefing.notams)

    # Query NOTAMs
    departure_notams = (
        briefing.notams_query
        .for_airport("LFPG")
        .active_now()
        .runway_related()
        .all()
    )
"""

from euro_aip.briefing.models.notam import Notam, NotamCategory
from euro_aip.briefing.models.route import Route, RoutePoint
from euro_aip.briefing.models.briefing import Briefing
from euro_aip.briefing.collections.notam_collection import NotamCollection
from euro_aip.briefing.sources.foreflight import ForeFlightSource
from euro_aip.briefing.parsers.notam_parser import NotamParser
from euro_aip.briefing.categorization.pipeline import CategorizationPipeline

__all__ = [
    # Models
    'Notam',
    'NotamCategory',
    'Route',
    'RoutePoint',
    'Briefing',
    # Collections
    'NotamCollection',
    # Sources
    'ForeFlightSource',
    # Parsers
    'NotamParser',
    # Categorization
    'CategorizationPipeline',
]
