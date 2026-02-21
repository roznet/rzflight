# Briefing Feature Design Document

**Version:** 1.0 Draft
**Date:** January 2026
**Status:** Historical - Superseded by implemented code

> **Warning**: This is the initial design proposal. The implemented code differs significantly.
> For current architecture, see: [briefing.md](./briefing.md), [briefing_models.md](./briefing_models.md), [briefing_weather.md](./briefing_weather.md).
> Key differences: NotamCategory uses ICAO-standard names (AGA_MOVEMENT, ATM_AIRSPACE, etc.),
> weather uses unified WeatherReport (not separate Metar/Taf), architecture differs.

---

## Overview

This document describes the design for a new **Briefing** module in the `euro_aip` Python library. The briefing feature will allow users to:

1. **Import** flight briefing data from multiple sources (ForeFlight PDFs, online APIs, etc.)
2. **Parse** and extract structured information (NOTAMs, METARs, TAFs, routes)
3. **Filter, categorize, and query** the extracted data using flexible, extensible tools
4. **Use** the briefing data from different applications (CLI, web app, iOS app)

---

## Table of Contents

1. [Goals & Non-Goals](#goals--non-goals)
2. [Core Concepts](#core-concepts)
3. [Architecture Overview](#architecture-overview)
4. [Data Models](#data-models)
5. [Sources & Parsers](#sources--parsers)
6. [Filtering & Categorization](#filtering--categorization)
7. [API Design](#api-design)
8. [Integration with euro_aip](#integration-with-euro_aip)
9. [Implementation Phases](#implementation-phases)
10. [Future Extensions](#future-extensions)

---

## Goals & Non-Goals

### Goals

- Extract NOTAMs, METARs, and TAFs from ForeFlight briefing PDFs
- Provide flexible NOTAM filtering/categorization that works across platforms
- Follow existing euro_aip patterns (CachedSource, QueryableCollection, dataclasses)
- Be extensible for future briefing sources (AVWX API, FAA NOTAM API, EuroControl)
- Support serialization (JSON) for cross-platform use

### Non-Goals (for v1)

- Real-time NOTAM streaming/push notifications
- Full NOTAM database with historical queries
- Flight plan filing
- Weather radar/imagery

---

## Core Concepts

### Briefing

A **Briefing** is a container for all flight-related information for a specific route/time. It contains:

- **Route**: Departure, destination, alternates, waypoints
- **Weather**: METARs and TAFs for relevant airports
- **NOTAMs**: Notices to airmen affecting the route
- **Metadata**: Briefing time, validity period, source

### NOTAM

A **NOTAM** (Notice to Airmen) contains:

- **Identifier**: Unique NOTAM ID (e.g., `A1234/24`)
- **Location**: ICAO code(s) or FIR affected
- **Type/Category**: Aerodrome, navigation, airspace, obstacle, etc.
- **Schedule**: Effective from/to, permanent/temporary
- **Raw text**: Original NOTAM text
- **Parsed fields**: Q-line decoded, coordinates, altitudes

### METAR/TAF

Weather reports with:

- **Station**: ICAO code
- **Time**: Observation/validity time
- **Raw text**: Original encoded report
- **Decoded fields**: Wind, visibility, clouds, etc.

---

## Architecture Overview

```
euro_aip/
├── briefing/                    # New briefing module
│   ├── __init__.py
│   ├── models/                  # Data models
│   │   ├── __init__.py
│   │   ├── briefing.py          # Briefing container
│   │   ├── notam.py             # NOTAM model
│   │   ├── metar.py             # METAR model
│   │   ├── taf.py               # TAF model
│   │   └── route.py             # Route model
│   ├── collections/             # Queryable collections
│   │   ├── __init__.py
│   │   ├── notam_collection.py  # NOTAM filtering
│   │   └── weather_collection.py
│   ├── sources/                 # Briefing data sources
│   │   ├── __init__.py
│   │   ├── base.py              # BriefingSource interface
│   │   ├── foreflight.py        # ForeFlight PDF parser
│   │   ├── avwx.py              # AVWX API source
│   │   └── faa_notam.py         # FAA NOTAM API (future)
│   ├── parsers/                 # Parsing utilities
│   │   ├── __init__.py
│   │   ├── notam_parser.py      # NOTAM text parser
│   │   ├── metar_parser.py      # METAR decoder
│   │   └── pdf_extractor.py     # PDF text extraction
│   ├── filters/                 # NOTAM categorization
│   │   ├── __init__.py
│   │   ├── base.py              # Filter interface
│   │   ├── category.py          # Category-based filters
│   │   ├── relevance.py         # Relevance scoring
│   │   └── presets.py           # Common filter presets
│   └── utils/
│       ├── __init__.py
│       └── icao_decode.py       # ICAO Q-line decoder
```

---

## Data Models

### Briefing

```python
@dataclass
class Briefing:
    """Container for flight briefing data."""

    # Identity
    id: str                              # Unique briefing ID
    created_at: datetime
    source: str                          # e.g., "foreflight", "avwx"

    # Route information
    route: Optional[Route] = None

    # Weather
    metars: List[Metar] = field(default_factory=list)
    tafs: List[Taf] = field(default_factory=list)

    # NOTAMs
    notams: List[Notam] = field(default_factory=list)

    # Metadata
    valid_from: Optional[datetime] = None
    valid_to: Optional[datetime] = None
    raw_data: Optional[Dict[str, Any]] = None

    @property
    def notams_query(self) -> 'NotamCollection':
        """Get queryable collection of NOTAMs."""
        return NotamCollection(self.notams)

    @property
    def weather_query(self) -> 'WeatherCollection':
        """Get queryable collection of weather reports."""
        return WeatherCollection(self.metars, self.tafs)

    def to_dict(self) -> dict:
        """Serialize to dictionary for JSON export."""
        ...

    @classmethod
    def from_dict(cls, data: dict) -> 'Briefing':
        """Deserialize from dictionary."""
        ...
```

### Notam

```python
@dataclass
class Notam:
    """NOTAM data model."""

    # Identity
    id: str                              # e.g., "A1234/24"
    series: Optional[str] = None         # A, B, C, etc.
    number: Optional[int] = None
    year: Optional[int] = None

    # Location
    location: str                        # Primary ICAO (from A) line)
    fir: Optional[str] = None            # FIR code
    affected_locations: List[str] = field(default_factory=list)

    # Q-line decoded
    q_code: Optional[str] = None         # e.g., "QMXLC"
    traffic_type: Optional[str] = None   # I, V, IV
    purpose: Optional[str] = None        # N, B, O, M, K
    scope: Optional[str] = None          # A, E, W, AE, AW
    lower_limit: Optional[int] = None    # In feet
    upper_limit: Optional[int] = None    # In feet
    coordinates: Optional[Tuple[float, float]] = None  # lat, lon
    radius_nm: Optional[float] = None

    # Category (derived from Q-code)
    category: Optional[NotamCategory] = None
    subcategory: Optional[str] = None

    # Schedule
    effective_from: Optional[datetime] = None
    effective_to: Optional[datetime] = None
    is_permanent: bool = False
    schedule_text: Optional[str] = None  # e.g., "SR-SS"

    # Content
    raw_text: str = ""                   # Full NOTAM text
    message: str = ""                    # E) line - main message

    # Parsing metadata
    source: Optional[str] = None
    parsed_at: datetime = field(default_factory=datetime.now)
    parse_confidence: float = 1.0        # 0-1 confidence score

    # Custom categorization (populated by CategorizationPipeline)
    primary_category: Optional[str] = None
    custom_categories: Set[str] = field(default_factory=set)
    custom_tags: Set[str] = field(default_factory=set)


class NotamCategory(Enum):
    """NOTAM categories based on Q-code first two letters."""

    MOVEMENT_AREA = "MX"           # Taxiway, apron, movement area
    LIGHTING = "LX"                # Lighting systems
    NAVIGATION = "NA"              # Navigation aids
    COMMUNICATION = "CO"           # Communication facilities
    AIRSPACE = "AR"                # Airspace restrictions
    RUNWAY = "RW"                  # Runway related
    OBSTACLE = "OB"                # Obstacles
    PROCEDURE = "PI"               # Instrument procedures
    SERVICES = "SE"                # Services
    WARNING = "WA"                 # Warnings
    OTHER = "XX"                   # Other/unknown
```

### Metar

```python
@dataclass
class Metar:
    """METAR weather observation."""

    station: str                         # ICAO code
    observation_time: datetime
    raw_text: str

    # Decoded fields
    wind_direction: Optional[int] = None      # Degrees
    wind_speed: Optional[int] = None          # Knots
    wind_gust: Optional[int] = None           # Knots
    wind_variable_from: Optional[int] = None
    wind_variable_to: Optional[int] = None

    visibility_sm: Optional[float] = None     # Statute miles
    visibility_m: Optional[int] = None        # Meters

    clouds: List[CloudLayer] = field(default_factory=list)

    temperature_c: Optional[int] = None
    dewpoint_c: Optional[int] = None
    altimeter_inhg: Optional[float] = None
    altimeter_hpa: Optional[int] = None

    flight_category: Optional[str] = None     # VFR, MVFR, IFR, LIFR

    # Metadata
    source: Optional[str] = None


@dataclass
class CloudLayer:
    """Cloud layer information."""
    coverage: str                        # FEW, SCT, BKN, OVC
    altitude_ft: int                     # AGL
    cloud_type: Optional[str] = None     # CB, TCU
```

### Route

```python
@dataclass
class RoutePoint:
    """A point along a route with coordinates."""

    name: str                            # Waypoint name or ICAO code
    latitude: float
    longitude: float
    point_type: str = "waypoint"         # "departure", "destination", "alternate", "waypoint"


@dataclass
class Route:
    """Flight route information with coordinates for spatial queries."""

    departure: str                       # ICAO code
    destination: str                     # ICAO code
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
    arrival_time: Optional[datetime] = None       # Estimated arrival
    flight_level: Optional[int] = None
    cruise_altitude_ft: Optional[int] = None

    def get_all_airports(self) -> List[str]:
        """Get all airports involved in the route."""
        airports = [self.departure, self.destination]
        airports.extend(self.alternates)
        return list(set(airports))

    def get_all_coordinates(self) -> List[Tuple[float, float]]:
        """Get all route coordinates for spatial queries."""
        coords = []
        if self.departure_coords:
            coords.append(self.departure_coords)
        coords.extend([(wp.latitude, wp.longitude) for wp in self.waypoint_coords])
        if self.destination_coords:
            coords.append(self.destination_coords)
        return coords

    def get_airport_coordinates(self) -> Dict[str, Tuple[float, float]]:
        """Get coordinates for all airports in route."""
        coords = {}
        if self.departure_coords:
            coords[self.departure] = self.departure_coords
        if self.destination_coords:
            coords[self.destination] = self.destination_coords
        coords.update(self.alternate_coords)
        return coords

    def get_flight_window(self, buffer_minutes: int = 60) -> Tuple[datetime, datetime]:
        """
        Get the time window for the flight.

        Args:
            buffer_minutes: Buffer time after arrival

        Returns:
            (departure_time, arrival_time + buffer)
        """
        if not self.departure_time:
            raise ValueError("Departure time not set")

        end_time = self.arrival_time or self.departure_time
        from datetime import timedelta
        return (self.departure_time, end_time + timedelta(minutes=buffer_minutes))
```

---

## Sources & Parsers

### Separation of Concerns

The parsing architecture separates concerns for all data types (NOTAMs, METARs, TAFs):

1. **Source Extraction**: Getting raw text/data from a source (PDF, API, file)
2. **Format Parsing**: Parsing standard formats (ICAO NOTAM, METAR, TAF) into structured data
3. **Enrichment**: Categorization, decoding, augmentation

This separation allows:
- The same parsers to work on any source
- Easy addition of new sources without changing parsing logic
- Consistent data structures regardless of origin
- Unit testing of parsers independent of sources

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  BriefingSource │     │    Parsers      │     │   Enrichment    │
│  (ForeFlight,   │────▶│  (standalone)   │────▶│   (optional)    │
│   AVWX, FAA)    │     │                 │     │                 │
└─────────────────┘     └─────────────────┘     └─────────────────┘
        │                       │                       │
        ▼                       ▼                       ▼
   Raw text             ┌─────────────┐          ┌─────────────┐
   extraction           │NotamParser  │          │Categorizer  │
                        │MetarParser  │          │WeatherDecode│
                        │TafParser    │          │             │
                        └─────────────┘          └─────────────┘
```

### Standalone Parsers

Each parser works independently on raw text:

```python
from euro_aip.briefing.parsers import NotamParser, MetarParser, TafParser

# Parse from any text source
notam = NotamParser.parse(notam_text)
metar = MetarParser.parse(metar_text)
taf = TafParser.parse(taf_text)

# Parse multiple from a block
notams = NotamParser.parse_many(text_block)
metars = MetarParser.parse_many(text_block)
```

Sources extract raw text and delegate to these parsers:

```python
class ForeFlightSource(BriefingSource):
    def parse(self, pdf_path) -> Briefing:
        text = self._extract_text(pdf_path)

        # Delegate to standalone parsers
        notams = NotamParser.parse_many(self._extract_notam_section(text))
        metars = MetarParser.parse_many(self._extract_metar_section(text))
        tafs = TafParser.parse_many(self._extract_taf_section(text))

        return Briefing(notams=notams, metars=metars, tafs=tafs, ...)
```

### BriefingSource Interface

```python
class BriefingSource(ABC):
    """Base interface for briefing data sources."""

    @abstractmethod
    def parse(self, data: Any) -> Briefing:
        """Parse source data into a Briefing object."""
        pass

    @abstractmethod
    def get_supported_formats(self) -> List[str]:
        """Get list of supported input formats."""
        pass
```

### ForeFlight PDF Source (Priority)

```python
class ForeFlightSource(BriefingSource, CachedSource):
    """
    Parse ForeFlight briefing PDFs.

    ForeFlight briefings contain:
    - Route summary
    - METARs/TAFs for departure, destination, alternates
    - NOTAMs organized by location
    - TFRs and other advisories
    """

    def __init__(self, cache_dir: str):
        super().__init__(cache_dir)

    def parse(self, pdf_path: Union[str, Path, bytes]) -> Briefing:
        """
        Parse a ForeFlight briefing PDF.

        Args:
            pdf_path: Path to PDF file or raw PDF bytes

        Returns:
            Briefing object with extracted data
        """
        ...

    def _extract_route(self, text: str) -> Optional[Route]:
        """Extract route information from briefing header."""
        ...

    def _extract_metars(self, text: str) -> List[Metar]:
        """Extract and parse METAR sections."""
        ...

    def _extract_tafs(self, text: str) -> List[Taf]:
        """Extract and parse TAF sections."""
        ...

    def _extract_notams(self, text: str) -> List[Notam]:
        """Extract and parse NOTAM sections."""
        ...

    def get_supported_formats(self) -> List[str]:
        return ['pdf']
```

### NOTAM Parser

```python
class NotamParser:
    """
    Parser for ICAO NOTAM format.

    Handles both full NOTAM format and abbreviated formats
    found in briefing documents.
    """

    # Regex patterns for NOTAM parsing
    NOTAM_ID_PATTERN = re.compile(r'([A-Z])(\d{4})/(\d{2})')
    Q_LINE_PATTERN = re.compile(r'Q\)([A-Z]{4})/([A-Z]+)/([A-Z]+)/([A-Z]+)/(\d{3})/(\d{3})/(\d{4}[NS]\d{5}[EW])(\d{3})')

    @classmethod
    def parse(cls, text: str, source: str = None) -> Optional[Notam]:
        """
        Parse a single NOTAM from text.

        Args:
            text: Raw NOTAM text
            source: Source identifier

        Returns:
            Parsed Notam object or None if parsing fails
        """
        ...

    @classmethod
    def parse_q_code(cls, q_code: str) -> Dict[str, Any]:
        """
        Decode ICAO Q-code into category and meaning.

        Args:
            q_code: 5-letter Q-code (e.g., "QMXLC")

        Returns:
            Dictionary with decoded information
        """
        ...

    @classmethod
    def parse_many(cls, text: str, source: str = None) -> List[Notam]:
        """Parse multiple NOTAMs from a text block."""
        ...
```

---

## Filtering & Categorization

### Design Principles

The filtering and categorization system is designed with these principles:

1. **Source-agnostic**: NOTAM parsing and categorization work on any NOTAM text, regardless of where it came from (ForeFlight PDF, API, manual input)

2. **Pluggable categorizers**: Multiple categorization strategies can be combined (Q-code based, text rules, LLM analysis)

3. **Spatial awareness**: Filter by distance to route, waypoints, or arbitrary coordinates

4. **Flexible time windows**: Query NOTAMs active during any time range (past, present, or future flight windows)

### NotamCollection (QueryableCollection)

Following the euro_aip pattern, `NotamCollection` provides fluent filtering:

```python
class NotamCollection(QueryableCollection[Notam]):
    """
    Queryable collection for NOTAM filtering.

    Supports fluent chaining, set operations, and iteration.
    """

    # --- Location filters ---

    def for_airport(self, icao: str) -> 'NotamCollection':
        """Filter NOTAMs affecting a specific airport."""
        icao_upper = icao.upper()
        return NotamCollection([
            n for n in self._items
            if n.location == icao_upper or icao_upper in n.affected_locations
        ])

    def for_airports(self, icaos: List[str]) -> 'NotamCollection':
        """Filter NOTAMs affecting any of the specified airports."""
        icaos_upper = {i.upper() for i in icaos}
        return NotamCollection([
            n for n in self._items
            if n.location in icaos_upper or any(loc in icaos_upper for loc in n.affected_locations)
        ])

    def for_fir(self, fir: str) -> 'NotamCollection':
        """Filter NOTAMs for a specific FIR."""
        return NotamCollection([
            n for n in self._items
            if n.fir and n.fir.upper() == fir.upper()
        ])

    # --- Category filters ---

    def by_category(self, category: NotamCategory) -> 'NotamCollection':
        """Filter by NOTAM category."""
        return NotamCollection([
            n for n in self._items
            if n.category == category
        ])

    def runway_related(self) -> 'NotamCollection':
        """Filter NOTAMs related to runways."""
        return NotamCollection([
            n for n in self._items
            if n.category in (NotamCategory.RUNWAY, NotamCategory.LIGHTING)
            or (n.q_code and n.q_code.startswith('QMR'))
        ])

    def navigation_related(self) -> 'NotamCollection':
        """Filter NOTAMs related to navigation aids."""
        return NotamCollection([
            n for n in self._items
            if n.category == NotamCategory.NAVIGATION
        ])

    def airspace_related(self) -> 'NotamCollection':
        """Filter NOTAMs related to airspace."""
        return NotamCollection([
            n for n in self._items
            if n.category == NotamCategory.AIRSPACE
        ])

    def procedure_related(self) -> 'NotamCollection':
        """Filter NOTAMs related to procedures."""
        return NotamCollection([
            n for n in self._items
            if n.category == NotamCategory.PROCEDURE
        ])

    # --- Time filters ---

    def active_at(self, dt: datetime) -> 'NotamCollection':
        """Filter NOTAMs active at a specific time."""
        return NotamCollection([
            n for n in self._items
            if self._is_active_at(n, dt)
        ])

    def active_now(self) -> 'NotamCollection':
        """Filter NOTAMs currently active."""
        return self.active_at(datetime.utcnow())

    def active_during(self, start: datetime, end: datetime) -> 'NotamCollection':
        """
        Filter NOTAMs active during any part of a time window.

        Use this for flight planning - pass departure and arrival times
        to get all NOTAMs that could affect the flight.

        Args:
            start: Window start time (e.g., departure time)
            end: Window end time (e.g., arrival time + buffer)

        Example:
            # NOTAMs for a flight departing in 2 hours, 3 hour flight
            dep_time = datetime.utcnow() + timedelta(hours=2)
            arr_time = dep_time + timedelta(hours=3)
            relevant = notams.active_during(dep_time, arr_time)
        """
        return NotamCollection([
            n for n in self._items
            if self._overlaps_window(n, start, end)
        ])

    def effective_after(self, dt: datetime) -> 'NotamCollection':
        """Filter NOTAMs that become effective after a given time."""
        return NotamCollection([
            n for n in self._items
            if n.effective_from and n.effective_from > dt
        ])

    def expiring_before(self, dt: datetime) -> 'NotamCollection':
        """Filter NOTAMs that expire before a given time."""
        return NotamCollection([
            n for n in self._items
            if n.effective_to and n.effective_to < dt and not n.is_permanent
        ])

    def permanent(self) -> 'NotamCollection':
        """Filter permanent NOTAMs."""
        return NotamCollection([
            n for n in self._items
            if n.is_permanent
        ])

    def temporary(self) -> 'NotamCollection':
        """Filter temporary NOTAMs."""
        return NotamCollection([
            n for n in self._items
            if not n.is_permanent
        ])

    @staticmethod
    def _is_active_at(notam: Notam, dt: datetime) -> bool:
        """Check if NOTAM is active at a specific time."""
        if notam.is_permanent:
            return notam.effective_from is None or notam.effective_from <= dt
        from_ok = notam.effective_from is None or notam.effective_from <= dt
        to_ok = notam.effective_to is None or notam.effective_to >= dt
        return from_ok and to_ok

    @staticmethod
    def _overlaps_window(notam: Notam, start: datetime, end: datetime) -> bool:
        """Check if NOTAM is active during any part of time window."""
        # Permanent NOTAMs that have started are always relevant
        if notam.is_permanent:
            return notam.effective_from is None or notam.effective_from <= end

        # Get NOTAM bounds (None means unbounded)
        n_start = notam.effective_from
        n_end = notam.effective_to

        # Check for overlap: NOT (notam ends before window OR notam starts after window)
        if n_end and n_end < start:
            return False
        if n_start and n_start > end:
            return False
        return True

    # --- Spatial filters (distance to route/point) ---

    def within_radius(self, lat: float, lon: float, radius_nm: float) -> 'NotamCollection':
        """
        Filter NOTAMs within a radius of a point.

        Args:
            lat: Latitude in degrees
            lon: Longitude in degrees
            radius_nm: Radius in nautical miles

        Example:
            # NOTAMs within 50nm of Paris
            nearby = notams.within_radius(48.8566, 2.3522, 50)
        """
        return NotamCollection([
            n for n in self._items
            if n.coordinates and self._distance_nm(lat, lon, n.coordinates[0], n.coordinates[1]) <= radius_nm
        ])

    def along_route(self, route: 'Route', corridor_nm: float = 25) -> 'NotamCollection':
        """
        Filter NOTAMs along a route corridor.

        Checks if NOTAM coordinates fall within corridor_nm of any route segment.

        Args:
            route: Route object with waypoints
            corridor_nm: Corridor width in nautical miles (default 25nm each side)

        Example:
            # NOTAMs within 25nm of the planned route
            enroute = notams.along_route(briefing.route, corridor_nm=25)
        """
        return NotamCollection([
            n for n in self._items
            if self._is_along_route(n, route, corridor_nm)
        ])

    def near_airports(self, icaos: List[str], radius_nm: float,
                      airport_coords: Dict[str, Tuple[float, float]]) -> 'NotamCollection':
        """
        Filter NOTAMs near specific airports by coordinates.

        Args:
            icaos: List of ICAO codes
            radius_nm: Radius around each airport
            airport_coords: Dict mapping ICAO to (lat, lon)

        Example:
            coords = {"LFPG": (49.0097, 2.5479), "EGLL": (51.4700, -0.4543)}
            nearby = notams.near_airports(["LFPG", "EGLL"], 30, coords)
        """
        relevant = []
        for n in self._items:
            if not n.coordinates:
                # Include NOTAMs without coords if they match airport by location field
                if n.location in icaos:
                    relevant.append(n)
                continue
            for icao in icaos:
                if icao in airport_coords:
                    apt_lat, apt_lon = airport_coords[icao]
                    if self._distance_nm(apt_lat, apt_lon, n.coordinates[0], n.coordinates[1]) <= radius_nm:
                        relevant.append(n)
                        break
        return NotamCollection(relevant)

    @staticmethod
    def _distance_nm(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Calculate great circle distance in nautical miles."""
        from math import radians, sin, cos, sqrt, atan2

        R = 3440.065  # Earth radius in nautical miles

        lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
        dlat = lat2 - lat1
        dlon = lon2 - lon1

        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
        c = 2 * atan2(sqrt(a), sqrt(1-a))

        return R * c

    @staticmethod
    def _is_along_route(notam: Notam, route: 'Route', corridor_nm: float) -> bool:
        """Check if NOTAM falls within route corridor."""
        if not notam.coordinates:
            return False
        # Simplified: check distance to each waypoint
        # Full implementation would check distance to route segments
        # For now, check if within corridor of any waypoint
        # TODO: Implement proper route segment distance calculation
        return False  # Placeholder - implement with proper geometry

    # --- Altitude filters ---

    def below_altitude(self, feet: int) -> 'NotamCollection':
        """Filter NOTAMs with upper limit below specified altitude."""
        return NotamCollection([
            n for n in self._items
            if n.upper_limit is not None and n.upper_limit <= feet
        ])

    def above_altitude(self, feet: int) -> 'NotamCollection':
        """Filter NOTAMs with lower limit above specified altitude."""
        return NotamCollection([
            n for n in self._items
            if n.lower_limit is not None and n.lower_limit >= feet
        ])

    def in_altitude_range(self, lower: int, upper: int) -> 'NotamCollection':
        """Filter NOTAMs affecting an altitude range."""
        return NotamCollection([
            n for n in self._items
            if self._affects_altitude_range(n, lower, upper)
        ])

    # --- Q-code filters (ICAO standard) ---

    def by_q_code(self, q_code: str) -> 'NotamCollection':
        """
        Filter by exact Q-code match.

        Args:
            q_code: 5-letter Q-code (e.g., "QMRLC" for runway closed)
        """
        q_upper = q_code.upper()
        return NotamCollection([
            n for n in self._items
            if n.q_code and n.q_code.upper() == q_upper
        ])

    def by_q_code_prefix(self, prefix: str) -> 'NotamCollection':
        """
        Filter by Q-code prefix (first 2-3 letters).

        Common prefixes:
        - QM: Movement area (runway, taxiway, apron)
        - QL: Lighting
        - QN: Navigation services
        - QO: Obstacles
        - QR: Instrument approach procedures
        - QA: Aerodrome

        Args:
            prefix: Q-code prefix (e.g., "QM" for movement area)
        """
        prefix_upper = prefix.upper()
        return NotamCollection([
            n for n in self._items
            if n.q_code and n.q_code.upper().startswith(prefix_upper)
        ])

    def by_traffic_type(self, traffic: str) -> 'NotamCollection':
        """
        Filter by traffic type from Q-line.

        Args:
            traffic: "I" (IFR), "V" (VFR), or "IV" (both)
        """
        return NotamCollection([
            n for n in self._items
            if n.traffic_type and traffic.upper() in n.traffic_type.upper()
        ])

    def by_purpose(self, purpose: str) -> 'NotamCollection':
        """
        Filter by NOTAM purpose from Q-line.

        Args:
            purpose: N (immediate), B (briefing), O (operations), M (misc), K (checklist)
        """
        purpose_upper = purpose.upper()
        return NotamCollection([
            n for n in self._items
            if n.purpose and purpose_upper in n.purpose.upper()
        ])

    def by_scope(self, scope: str) -> 'NotamCollection':
        """
        Filter by scope from Q-line.

        Args:
            scope: A (aerodrome), E (enroute), W (nav warning), AE, AW, etc.
        """
        scope_upper = scope.upper()
        return NotamCollection([
            n for n in self._items
            if n.scope and scope_upper in n.scope.upper()
        ])

    # --- Custom category filters ---

    def by_custom_category(self, category: str) -> 'NotamCollection':
        """
        Filter by custom-assigned category.

        Custom categories are assigned by categorizers (rule-based or LLM).

        Args:
            category: Custom category name
        """
        return NotamCollection([
            n for n in self._items
            if hasattr(n, 'custom_categories') and category in n.custom_categories
        ])

    def by_custom_tag(self, tag: str) -> 'NotamCollection':
        """
        Filter by custom tag.

        Tags are more granular than categories (e.g., "construction", "crane").
        """
        return NotamCollection([
            n for n in self._items
            if hasattr(n, 'custom_tags') and tag in n.custom_tags
        ])

    # --- Content filters ---

    def containing(self, text: str) -> 'NotamCollection':
        """Filter NOTAMs containing specific text (case-insensitive)."""
        text_upper = text.upper()
        return NotamCollection([
            n for n in self._items
            if text_upper in n.raw_text.upper() or text_upper in n.message.upper()
        ])

    def matching(self, pattern: str) -> 'NotamCollection':
        """Filter NOTAMs matching a regex pattern."""
        regex = re.compile(pattern, re.IGNORECASE)
        return NotamCollection([
            n for n in self._items
            if regex.search(n.raw_text) or regex.search(n.message)
        ])

    # --- Relevance scoring ---

    def scored(self, scorer: 'NotamScorer') -> 'ScoredNotamCollection':
        """
        Apply relevance scoring to NOTAMs.

        Returns a ScoredNotamCollection that can be sorted by score.
        """
        scored_items = [(n, scorer.score(n)) for n in self._items]
        return ScoredNotamCollection(scored_items)

    # --- Grouping ---

    def group_by_airport(self) -> Dict[str, 'NotamCollection']:
        """Group NOTAMs by primary airport."""
        return self.group_by(lambda n: n.location)

    def group_by_category(self) -> Dict[NotamCategory, 'NotamCollection']:
        """Group NOTAMs by category."""
        return self.group_by(lambda n: n.category)

    # --- Utility methods ---

    @staticmethod
    def _affects_altitude_range(notam: Notam, lower: int, upper: int) -> bool:
        """Check if NOTAM affects an altitude range."""
        if notam.lower_limit is None and notam.upper_limit is None:
            return True  # Assume it affects all altitudes
        n_lower = notam.lower_limit or 0
        n_upper = notam.upper_limit or 99999
        return n_lower <= upper and n_upper >= lower
```

### NotamScorer (Relevance Scoring)

```python
class NotamScorer(ABC):
    """Base class for NOTAM relevance scoring."""

    @abstractmethod
    def score(self, notam: Notam) -> float:
        """
        Calculate relevance score for a NOTAM.

        Returns:
            Score from 0.0 (irrelevant) to 1.0 (highly relevant)
        """
        pass


class RouteRelevanceScorer(NotamScorer):
    """Score NOTAMs based on relevance to a specific route."""

    def __init__(self, route: Route, flight_level: int = None):
        self.route = route
        self.flight_level = flight_level
        self.route_airports = set(route.get_all_airports())

    def score(self, notam: Notam) -> float:
        score = 0.0

        # High score for departure/destination
        if notam.location == self.route.departure:
            score += 0.5
        elif notam.location == self.route.destination:
            score += 0.5
        elif notam.location in self.route.alternates:
            score += 0.3
        elif notam.location in self.route_airports:
            score += 0.2

        # Category relevance
        if notam.category in (NotamCategory.RUNWAY, NotamCategory.PROCEDURE):
            score += 0.3
        elif notam.category == NotamCategory.AIRSPACE:
            score += 0.2

        # Altitude relevance
        if self.flight_level and self._affects_flight_level(notam):
            score += 0.2

        return min(score, 1.0)

    def _affects_flight_level(self, notam: Notam) -> bool:
        if notam.lower_limit is None and notam.upper_limit is None:
            return True
        fl_feet = self.flight_level * 100
        return (notam.lower_limit or 0) <= fl_feet <= (notam.upper_limit or 99999)


class CompositeScorer(NotamScorer):
    """Combine multiple scorers with weights."""

    def __init__(self, scorers: List[Tuple[NotamScorer, float]]):
        self.scorers = scorers

    def score(self, notam: Notam) -> float:
        total = sum(scorer.score(notam) * weight for scorer, weight in self.scorers)
        total_weight = sum(weight for _, weight in self.scorers)
        return total / total_weight if total_weight > 0 else 0.0
```

### Categorization Pipeline

The categorization system is designed to be:
- **Source-agnostic**: Works on any NOTAM text
- **Pluggable**: Multiple categorizers can be combined
- **Extensible**: Easy to add new rule-based or LLM categorizers

```python
from abc import ABC, abstractmethod
from typing import List, Set, Dict, Any
from dataclasses import dataclass, field


@dataclass
class CategorizationResult:
    """Result of NOTAM categorization."""

    # Primary category (most relevant)
    primary_category: Optional[str] = None

    # All applicable categories
    categories: Set[str] = field(default_factory=set)

    # Granular tags
    tags: Set[str] = field(default_factory=set)

    # Relevance hints
    relevance_hints: Dict[str, Any] = field(default_factory=dict)

    # Confidence score (0-1)
    confidence: float = 1.0

    # Which categorizer produced this
    source: Optional[str] = None


class NotamCategorizer(ABC):
    """
    Base interface for NOTAM categorizers.

    Categorizers analyze NOTAM text and assign categories/tags.
    Multiple categorizers can be chained in a pipeline.
    """

    @abstractmethod
    def categorize(self, notam: Notam) -> CategorizationResult:
        """
        Analyze a NOTAM and return categorization.

        Args:
            notam: NOTAM to categorize

        Returns:
            CategorizationResult with categories and tags
        """
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """Categorizer name for tracking."""
        pass


class QCodeCategorizer(NotamCategorizer):
    """
    Categorize based on ICAO Q-code.

    This is the most reliable categorizer when Q-code is available.
    """

    # Q-code to category mapping
    Q_CODE_CATEGORIES = {
        # Movement area
        'QMRLC': ('runway', {'closed'}),
        'QMRXX': ('runway', set()),
        'QMXLC': ('taxiway', {'closed'}),
        'QMXXX': ('taxiway', set()),
        'QMALC': ('apron', {'closed'}),
        # Lighting
        'QLLCL': ('lighting', {'runway', 'closed'}),
        'QLALS': ('lighting', {'approach'}),
        # Navigation
        'QNVAS': ('navaid', {'vor'}),
        'QNDAS': ('navaid', {'dme'}),
        'QNIAS': ('navaid', {'ils'}),
        # Procedures
        'QPICH': ('procedure', {'approach', 'changed'}),
        'QPIAU': ('procedure', {'approach', 'unavailable'}),
        'QPIDU': ('procedure', {'sid', 'unavailable'}),
        'QPSTU': ('procedure', {'star', 'unavailable'}),
        # Airspace
        'QARLC': ('airspace', {'restricted', 'closed'}),
        'QARAU': ('airspace', {'restricted', 'active'}),
        'QADAU': ('airspace', {'danger', 'active'}),
        'QWPLW': ('airspace', {'warning', 'parachuting'}),
        # Obstacles
        'QOBCE': ('obstacle', {'crane', 'erected'}),
        'QOBXX': ('obstacle', set()),
    }

    @property
    def name(self) -> str:
        return "q_code"

    def categorize(self, notam: Notam) -> CategorizationResult:
        result = CategorizationResult(source=self.name)

        if not notam.q_code:
            result.confidence = 0.0
            return result

        # Exact match
        if notam.q_code in self.Q_CODE_CATEGORIES:
            cat, tags = self.Q_CODE_CATEGORIES[notam.q_code]
            result.primary_category = cat
            result.categories.add(cat)
            result.tags.update(tags)
            result.confidence = 1.0
            return result

        # Prefix match (first 3 letters)
        prefix = notam.q_code[:3]
        for q_code, (cat, tags) in self.Q_CODE_CATEGORIES.items():
            if q_code.startswith(prefix):
                result.primary_category = cat
                result.categories.add(cat)
                result.confidence = 0.8
                return result

        return result


class TextRuleCategorizer(NotamCategorizer):
    """
    Categorize based on text pattern matching.

    Useful when Q-code is missing or incomplete.
    """

    # Text patterns to categories
    RULES = [
        # Runway closures
        (r'\bRWY\s*\d+[LRC]?\s*(CLSD|CLOSED)\b', 'runway', {'closed'}),
        (r'\bRUNWAY\s*(CLSD|CLOSED)\b', 'runway', {'closed'}),

        # Taxiway closures
        (r'\bTWY\s*[A-Z]+\d*\s*(CLSD|CLOSED)\b', 'taxiway', {'closed'}),

        # Lighting
        (r'\bALS\s*(U/S|UNSERVICEABLE|INOP)\b', 'lighting', {'approach', 'unserviceable'}),
        (r'\bPAPI\s*(U/S|UNSERVICEABLE|INOP)\b', 'lighting', {'papi', 'unserviceable'}),
        (r'\bRWY\s*\d+.*LGT.*INOP\b', 'lighting', {'runway', 'unserviceable'}),

        # Navigation aids
        (r'\bVOR\s*[A-Z]{3}\s*(U/S|UNSERVICEABLE)\b', 'navaid', {'vor', 'unserviceable'}),
        (r'\bILS\s*(U/S|UNSERVICEABLE|OUT OF SERVICE)\b', 'navaid', {'ils', 'unserviceable'}),
        (r'\bDME\s*(U/S|UNSERVICEABLE)\b', 'navaid', {'dme', 'unserviceable'}),
        (r'\bGLIDE\s*PATH\s*(U/S|UNSERVICEABLE)\b', 'navaid', {'ils', 'glidepath', 'unserviceable'}),

        # Procedures
        (r'\bIAP\s*.*\b(SUSPENDED|NOT AVAILABLE|NA)\b', 'procedure', {'approach', 'unavailable'}),
        (r'\bSID\s*.*\b(SUSPENDED|NOT AVAILABLE)\b', 'procedure', {'sid', 'unavailable'}),
        (r'\bSTAR\s*.*\b(SUSPENDED|NOT AVAILABLE)\b', 'procedure', {'star', 'unavailable'}),
        (r'\bMINIMUM\s*ALTITUDE\s*(CHANGED|RAISED)\b', 'procedure', {'minima', 'changed'}),

        # Obstacles
        (r'\bCRANE\s*(ERECTED|OPR|OPERATING)\b', 'obstacle', {'crane'}),
        (r'\bWIND\s*TURBINE\b', 'obstacle', {'wind_turbine'}),
        (r'\bTOWER\b.*\bFT\s*AGL\b', 'obstacle', {'tower'}),

        # Airspace
        (r'\bTEMPORARY\s*RESTRICTED\s*AREA\b', 'airspace', {'restricted', 'temporary'}),
        (r'\bPARA(CHUTE|CHUTING)\s*ACT(IVITY|IVITIES)?\b', 'airspace', {'parachuting'}),
        (r'\bUAS\s*ACT(IVITY|IVITIES)?\b|DRONE', 'airspace', {'drone'}),
        (r'\bAIRSHOW\b', 'airspace', {'airshow'}),
        (r'\bMILITARY\s*(EXERCISE|ACTIVITY)\b', 'airspace', {'military'}),

        # Services
        (r'\bFUEL\s*(NOT AVAILABLE|UNAVAILABLE|LIMITED)\b', 'services', {'fuel', 'limited'}),
        (r'\bTWR\s*(CLSD|CLOSED)\b', 'services', {'atc', 'tower', 'closed'}),
        (r'\bAPP\s*(CLSD|CLOSED)\b', 'services', {'atc', 'approach', 'closed'}),

        # Wildlife
        (r'\bBIRD\s*(ACTIVITY|CONCENTRATION|HAZARD)\b', 'wildlife', {'birds'}),
    ]

    def __init__(self):
        # Compile patterns for performance
        self._compiled_rules = [
            (re.compile(pattern, re.IGNORECASE), cat, tags)
            for pattern, cat, tags in self.RULES
        ]

    @property
    def name(self) -> str:
        return "text_rules"

    def categorize(self, notam: Notam) -> CategorizationResult:
        result = CategorizationResult(source=self.name)
        text = f"{notam.raw_text} {notam.message}"

        matches = []
        for pattern, cat, tags in self._compiled_rules:
            if pattern.search(text):
                matches.append((cat, tags))

        if matches:
            # Use most specific match (most tags)
            best_match = max(matches, key=lambda x: len(x[1]))
            result.primary_category = best_match[0]
            for cat, tags in matches:
                result.categories.add(cat)
                result.tags.update(tags)
            result.confidence = 0.7  # Lower confidence than Q-code

        return result


class LLMCategorizer(NotamCategorizer):
    """
    Categorize using LLM analysis.

    This is a placeholder for future LLM integration.
    Can use local models or API-based services.
    """

    def __init__(self, model_name: str = "default", api_key: str = None):
        self.model_name = model_name
        self.api_key = api_key

    @property
    def name(self) -> str:
        return f"llm_{self.model_name}"

    def categorize(self, notam: Notam) -> CategorizationResult:
        """
        Use LLM to categorize NOTAM.

        The LLM prompt should:
        1. Explain what the NOTAM means in plain English
        2. Assign relevant categories
        3. Extract key facts (runway, altitude, time, etc.)
        """
        # Placeholder - implement with actual LLM integration
        result = CategorizationResult(source=self.name)
        result.confidence = 0.0
        return result

    async def categorize_async(self, notam: Notam) -> CategorizationResult:
        """Async version for API-based LLMs."""
        # Implement async LLM call
        pass

    async def categorize_batch_async(self, notams: List[Notam]) -> List[CategorizationResult]:
        """Batch categorization for efficiency."""
        # Implement batch LLM call
        pass


class CategorizationPipeline:
    """
    Chain multiple categorizers together.

    Categorizers are run in order, with later results
    augmenting or overriding earlier ones based on confidence.
    """

    def __init__(self, categorizers: List[NotamCategorizer] = None):
        self.categorizers = categorizers or [
            QCodeCategorizer(),
            TextRuleCategorizer(),
        ]

    def categorize(self, notam: Notam) -> CategorizationResult:
        """
        Run all categorizers and merge results.

        Higher confidence results take precedence for primary category.
        All categories and tags are merged.
        """
        final = CategorizationResult()
        best_confidence = 0.0

        for categorizer in self.categorizers:
            result = categorizer.categorize(notam)

            # Merge categories and tags
            final.categories.update(result.categories)
            final.tags.update(result.tags)

            # Use highest confidence result for primary
            if result.confidence > best_confidence and result.primary_category:
                final.primary_category = result.primary_category
                best_confidence = result.confidence

            # Merge relevance hints
            final.relevance_hints.update(result.relevance_hints)

        final.confidence = best_confidence
        return final

    def categorize_all(self, notams: List[Notam]) -> List[Notam]:
        """
        Categorize all NOTAMs and attach results.

        Modifies NOTAMs in place, adding custom_categories and custom_tags.
        """
        for notam in notams:
            result = self.categorize(notam)
            notam.custom_categories = result.categories
            notam.custom_tags = result.tags
            notam.primary_category = result.primary_category
        return notams

    def add_categorizer(self, categorizer: NotamCategorizer) -> None:
        """Add a categorizer to the pipeline."""
        self.categorizers.append(categorizer)
```

### Filter Presets

```python
class NotamFilterPresets:
    """Pre-configured filter combinations for common use cases."""

    @staticmethod
    def departure_critical(collection: NotamCollection, icao: str) -> NotamCollection:
        """
        NOTAMs critical for departure from an airport.

        Includes: runway, taxiway, lighting, procedures, obstacles
        """
        return (
            collection
            .for_airport(icao)
            .active_now()
        ) & (
            collection.runway_related() |
            collection.by_category(NotamCategory.MOVEMENT_AREA) |
            collection.by_category(NotamCategory.LIGHTING) |
            collection.by_category(NotamCategory.OBSTACLE) |
            collection.procedure_related()
        )

    @staticmethod
    def arrival_critical(collection: NotamCollection, icao: str) -> NotamCollection:
        """NOTAMs critical for arrival at an airport."""
        return (
            collection
            .for_airport(icao)
            .active_now()
        ) & (
            collection.runway_related() |
            collection.navigation_related() |
            collection.procedure_related() |
            collection.by_category(NotamCategory.LIGHTING)
        )

    @staticmethod
    def enroute_relevant(collection: NotamCollection,
                         route: Route,
                         flight_level: int) -> NotamCollection:
        """NOTAMs relevant for enroute portion of flight."""
        return (
            collection
            .airspace_related()
            .active_now()
            .in_altitude_range(flight_level * 100 - 2000, flight_level * 100 + 2000)
        )

    @staticmethod
    def vfr_relevant(collection: NotamCollection, icao: str) -> NotamCollection:
        """NOTAMs relevant for VFR operations."""
        return (
            collection
            .for_airport(icao)
            .active_now()
            .below_altitude(10000)
        ) & (
            collection.runway_related() |
            collection.airspace_related() |
            collection.by_category(NotamCategory.OBSTACLE)
        )
```

---

## API Design

### High-Level Usage

```python
from euro_aip.briefing import Briefing, ForeFlightSource
from euro_aip.briefing.filters import NotamFilterPresets
from euro_aip.briefing.categorization import CategorizationPipeline
from datetime import datetime, timedelta

# Parse a ForeFlight briefing
source = ForeFlightSource(cache_dir="./cache")
briefing = source.parse("path/to/foreflight_briefing.pdf")

# Access route information
print(f"Route: {briefing.route.departure} -> {briefing.route.destination}")

# Apply categorization pipeline
pipeline = CategorizationPipeline()
pipeline.categorize_all(briefing.notams)

# Query weather
for metar in briefing.weather_query.for_airport("LFPG").all():
    print(f"{metar.station}: {metar.raw_text}")
```

### Time Window Filtering

```python
# Flight planning: get NOTAMs active during the flight
departure_time = datetime.utcnow() + timedelta(hours=2)
arrival_time = departure_time + timedelta(hours=3)

# NOTAMs active during any part of the flight window
flight_notams = (
    briefing.notams_query
    .active_during(departure_time, arrival_time)
    .all()
)

# NOTAMs that will become effective before arrival
new_notams = (
    briefing.notams_query
    .effective_after(datetime.utcnow())
    .expiring_before(arrival_time + timedelta(hours=6))
    .all()
)

# Using route's built-in time window
if briefing.route.departure_time:
    start, end = briefing.route.get_flight_window(buffer_minutes=60)
    relevant = briefing.notams_query.active_during(start, end).all()
```

### Spatial Filtering

```python
# NOTAMs within 50nm of Paris CDG
nearby = (
    briefing.notams_query
    .within_radius(49.0097, 2.5479, radius_nm=50)
    .all()
)

# NOTAMs along the route corridor (25nm each side)
enroute = (
    briefing.notams_query
    .along_route(briefing.route, corridor_nm=25)
    .all()
)

# NOTAMs near departure/destination/alternates
airport_coords = briefing.route.get_airport_coordinates()
terminal_notams = (
    briefing.notams_query
    .near_airports(
        briefing.route.get_all_airports(),
        radius_nm=30,
        airport_coords=airport_coords
    )
    .all()
)
```

### Q-Code and Category Filtering

```python
# Filter by ICAO Q-code
runway_closed = briefing.notams_query.by_q_code("QMRLC").all()
movement_area = briefing.notams_query.by_q_code_prefix("QM").all()
nav_aids = briefing.notams_query.by_q_code_prefix("QN").all()

# Filter by custom categories (after pipeline categorization)
obstacles = briefing.notams_query.by_custom_category("obstacle").all()
cranes = briefing.notams_query.by_custom_tag("crane").all()
ils_issues = briefing.notams_query.by_custom_tag("ils").all()

# Combine Q-code with custom tags
ils_outages = (
    briefing.notams_query
    .by_q_code_prefix("QNI")  # ILS related Q-codes
    .by_custom_tag("unserviceable")
    .all()
)
```

### Combined Filtering

```python
# Complex query: IFR-relevant NOTAMs for departure
departure_ifr = (
    briefing.notams_query
    .for_airport(briefing.route.departure)
    .active_during(*briefing.route.get_flight_window())
    .by_traffic_type("I")  # IFR traffic
    .by_scope("A")         # Aerodrome scope
) & (
    briefing.notams_query.runway_related() |
    briefing.notams_query.navigation_related() |
    briefing.notams_query.procedure_related()
)

# Use filter presets
departure_notams = NotamFilterPresets.departure_critical(
    briefing.notams_query,
    briefing.route.departure
)

# Score and sort by relevance
from euro_aip.briefing.filters import RouteRelevanceScorer

scorer = RouteRelevanceScorer(briefing.route, flight_level=350)
sorted_notams = (
    briefing.notams_query
    .active_during(*briefing.route.get_flight_window())
    .scored(scorer)
    .sorted_by_score()
    .all()
)

# Export for cross-platform use
briefing_dict = briefing.to_dict()
briefing_json = json.dumps(briefing_dict)
```

### Source-Agnostic NOTAM Processing

```python
from euro_aip.briefing.parsers import NotamParser
from euro_aip.briefing.categorization import CategorizationPipeline, TextRuleCategorizer

# Parse NOTAMs from any text source
raw_notam_text = """
A1234/24 NOTAMN
Q) LFFF/QMRLC/IV/NBO/A/000/999/4901N00225E005
A) LFPG B) 2401150800 C) 2401152000
E) RWY 09L/27R CLSD DUE TO MAINTENANCE
"""

# Parse single NOTAM
notam = NotamParser.parse(raw_notam_text, source="manual_input")

# Parse multiple NOTAMs from a block of text
notams = NotamParser.parse_many(some_text_with_multiple_notams)

# Apply categorization
pipeline = CategorizationPipeline()
pipeline.categorize_all(notams)

# Now NOTAMs have custom_categories and custom_tags
for notam in notams:
    print(f"{notam.id}: {notam.primary_category} - {notam.custom_tags}")
```

### Integration with EuroAipModel

```python
# Augment briefing with euro_aip airport data
from euro_aip import EuroAipModel

model = EuroAipModel.load("euro_aip.db")
briefing = source.parse("briefing.pdf")

# Get detailed airport info for briefing airports
for icao in briefing.route.get_all_airports():
    if icao in model.airports:
        airport = model.airports[icao]
        # Access procedures, runways, AIP entries
        approaches = airport.procedures_query.approaches().all()
```

---

## Integration with euro_aip

### Package Structure

The briefing module will be a subpackage of `euro_aip`:

```
euro_aip/
├── euro_aip/
│   ├── __init__.py          # Add briefing exports
│   ├── models/
│   ├── parsers/
│   ├── sources/
│   ├── storage/
│   ├── utils/
│   └── briefing/            # NEW
│       ├── __init__.py
│       ├── models/
│       ├── collections/
│       ├── sources/
│       ├── parsers/
│       └── filters/
```

### Shared Utilities

The briefing module will reuse:

- `CachedSource` from `euro_aip.sources.cached`
- `QueryableCollection` pattern from `euro_aip.models.queryable_collection`
- Dataclass patterns with `to_dict()`/`from_dict()`

### Dependencies

New dependencies for briefing:

```
# PDF parsing (already used in euro_aip)
pdfplumber>=0.10.0
pdfminer.six>=20221105

# METAR/TAF parsing (new)
python-metar>=1.4.0  # Optional, can implement own parser

# Date/time handling
python-dateutil>=2.8.0
```

---

## Implementation Phases

### Phase 1: Core Models & NOTAM Parser

**Priority: High**

1. Create core data models (Notam, Metar, Taf, Route, RoutePoint, Briefing)
2. Implement source-agnostic NOTAM parser (ICAO format)
3. Implement basic NotamCollection with:
   - Location filters (airport, FIR)
   - Time window filters (active_during, active_at)
   - Q-code filters
4. Implement QCodeCategorizer and TextRuleCategorizer
5. Create CategorizationPipeline

**Deliverables:**
- Can parse NOTAM text from any source
- Basic time and location filtering
- Rule-based categorization working

### Phase 2: ForeFlight Source & Spatial Filtering

**Priority: High**

1. Implement ForeFlight PDF parser (text extraction)
2. Extract route, METARs, TAFs, NOTAMs from ForeFlight format
3. Implement spatial filters:
   - within_radius
   - along_route
   - near_airports
4. Add altitude filters
5. Route coordinate handling

**Deliverables:**
- Can parse ForeFlight briefing PDF end-to-end
- Spatial filtering working
- Full NotamCollection API

### Phase 3: Scoring & Presets

**Priority: Medium**

1. Implement NotamScorer framework
2. RouteRelevanceScorer implementation
3. CompositeScorer for combining scorers
4. Filter presets (departure_critical, arrival_critical, vfr_relevant, etc.)
5. METAR/TAF decoding (wind, clouds, visibility)

**Deliverables:**
- Relevance scoring
- Pre-built filter combinations
- Weather decoding

### Phase 4: LLM Categorization & Additional Sources

**Priority: Low (future)**

1. LLMCategorizer implementation
2. Async batch processing for LLM
3. AVWX API source for live weather/NOTAMs
4. FAA NOTAM API source
5. EuroControl source

---

## Future Extensions

### Potential Future Features

1. **Real-time updates**: WebSocket or polling for NOTAM/weather updates
2. **NOTAM diff**: Compare briefings to highlight changes
3. **Advanced spatial**: FIR boundary polygons, airway corridors
4. **LLM categorization**: Use GPT/Claude for complex NOTAM analysis
5. **Swift integration**: Share models with RZFlight Swift package via JSON
6. **Visualization**: Generate briefing summaries/maps
7. **NOTAM history**: Track NOTAM changes over time
8. **Custom rule builder**: UI for creating text-based categorization rules
9. **Multi-language**: Parse NOTAMs in languages other than English

### API Sources to Consider

- **AVWX** (avwx.rest) - METARs, TAFs, station info
- **FAA NOTAM API** - US NOTAMs (icao.us)
- **EuroControl B2B** - European NOTAMs and flow management
- **ICAO API** - International NOTAMs
- **OpenSky Network** - Live traffic data
- **SkyVector** - Charts and procedures

### Cross-Platform Considerations

The briefing data should be easily consumable by:
- **Python CLI tools**: Direct API usage
- **Web applications**: JSON serialization, REST API wrapper
- **iOS/macOS apps**: JSON import, or shared Swift models
- **Automation scripts**: Command-line parsing, CI/CD integration

The `to_dict()` / `from_dict()` pattern ensures all models can be serialized to JSON and reconstructed on any platform.

---

## Open Questions

1. **NOTAM persistence**: Should briefings be stored in the euro_aip database?
2. **NOTAM deduplication**: How to handle duplicate NOTAMs from different sources?
3. **Coordinate parsing**: How to handle NOTAMs without coordinates for spatial queries?
4. **Testing**: Need sample ForeFlight PDFs for parser testing
5. **LLM integration**: Which LLM service/model for categorization? Local vs API?
6. **Route geometry**: Full great-circle distance to route segments vs simplified waypoint proximity?
7. **FIR boundaries**: Should we include FIR polygon data for spatial filtering?
8. **Airport coordinates**: Source for airport coordinates when not in briefing? (Use euro_aip model?)

---

## References

- [ICAO NOTAM Format](https://www.icao.int/safety/istars/pages/notam-format.aspx)
- [ForeFlight Briefing Documentation](https://foreflight.com/support/briefing/)
- [AVWX API Documentation](https://avwx.rest/documentation)
- [euro_aip Query API Architecture](./query_api_architecture.md)
