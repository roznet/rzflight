"""Weather report data models."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from math import cos, sin, radians
from typing import Optional, List, Dict, Any


class FlightCategory(Enum):
    """
    FAA flight category based on ceiling and visibility.

    Ordered from worst to best: LIFR < IFR < MVFR < VFR.

    Thresholds (ceiling OR visibility, whichever is worse):
        LIFR:  visibility < 1 SM  or  ceiling < 500 ft
        IFR:   1 <= vis < 3 SM    or  500 <= ceiling < 1000 ft
        MVFR:  3 <= vis <= 5 SM   or  1000 <= ceiling <= 3000 ft
        VFR:   visibility > 5 SM  and ceiling > 3000 ft
    """

    LIFR = "LIFR"
    IFR = "IFR"
    MVFR = "MVFR"
    VFR = "VFR"

    @property
    def order(self) -> int:
        """Numeric ordering from worst (0) to best (3)."""
        return _CATEGORY_ORDER[self]

    def __lt__(self, other: 'FlightCategory') -> bool:
        if not isinstance(other, FlightCategory):
            return NotImplemented
        return self.order < other.order

    def __le__(self, other: 'FlightCategory') -> bool:
        if not isinstance(other, FlightCategory):
            return NotImplemented
        return self.order <= other.order

    def __gt__(self, other: 'FlightCategory') -> bool:
        if not isinstance(other, FlightCategory):
            return NotImplemented
        return self.order > other.order

    def __ge__(self, other: 'FlightCategory') -> bool:
        if not isinstance(other, FlightCategory):
            return NotImplemented
        return self.order >= other.order


_CATEGORY_ORDER = {
    FlightCategory.LIFR: 0,
    FlightCategory.IFR: 1,
    FlightCategory.MVFR: 2,
    FlightCategory.VFR: 3,
}


class WeatherType(Enum):
    """Type of weather report."""

    METAR = "METAR"
    SPECI = "SPECI"
    TAF = "TAF"


@dataclass
class WindComponents:
    """
    Wind components relative to a runway.

    Positive headwind means wind is coming from ahead (favorable).
    Positive crosswind means wind is from the right.
    """

    runway_ident: str
    runway_heading: int
    headwind: float
    crosswind: float
    crosswind_direction: str = ""  # "left" or "right"
    gust_headwind: Optional[float] = None
    gust_crosswind: Optional[float] = None
    max_crosswind: Optional[float] = None

    def within_limits(
        self,
        max_crosswind_kt: float = 20.0,
        max_tailwind_kt: float = 10.0,
    ) -> bool:
        """
        Check if wind components are within limits.

        Args:
            max_crosswind_kt: Maximum crosswind in knots
            max_tailwind_kt: Maximum tailwind in knots (positive value)

        Returns:
            True if within limits
        """
        xwind = abs(self.gust_crosswind if self.gust_crosswind is not None else self.crosswind)
        if xwind > max_crosswind_kt:
            return False
        if self.headwind < 0 and abs(self.headwind) > max_tailwind_kt:
            return False
        if self.gust_headwind is not None and self.gust_headwind < 0 and abs(self.gust_headwind) > max_tailwind_kt:
            return False
        return True

    def to_dict(self) -> dict:
        return {
            'runway_ident': self.runway_ident,
            'runway_heading': self.runway_heading,
            'headwind': self.headwind,
            'crosswind': self.crosswind,
            'crosswind_direction': self.crosswind_direction,
            'gust_headwind': self.gust_headwind,
            'gust_crosswind': self.gust_crosswind,
            'max_crosswind': self.max_crosswind,
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'WindComponents':
        return cls(
            runway_ident=data.get('runway_ident', ''),
            runway_heading=data.get('runway_heading', 0),
            headwind=data.get('headwind', 0.0),
            crosswind=data.get('crosswind', 0.0),
            crosswind_direction=data.get('crosswind_direction', ''),
            gust_headwind=data.get('gust_headwind'),
            gust_crosswind=data.get('gust_crosswind'),
            max_crosswind=data.get('max_crosswind'),
        )


@dataclass
class WeatherReport:
    """
    Parsed METAR or TAF weather report.

    For TAFs, the trends field contains nested WeatherReport objects
    representing BECMG/TEMPO/FM groups.

    Attributes:
        icao: Airport ICAO code
        report_type: METAR, SPECI, or TAF
        raw_text: Original report text
        observation_time: Time of observation/issuance
        wind_direction: Wind direction in degrees (None if variable/calm)
        wind_speed: Wind speed in knots
        wind_gust: Gust speed in knots
        wind_variable_from: Variable wind range start
        wind_variable_to: Variable wind range end
        wind_unit: Wind unit (KT, MPS, KMH)
        visibility_meters: Visibility in meters
        visibility_sm: Visibility in statute miles
        ceiling_ft: Ceiling height in feet (lowest BKN/OVC layer)
        cavok: Ceiling And Visibility OK
        clouds: List of cloud layer dicts
        weather_conditions: List of weather condition strings
        temperature: Temperature in Celsius
        dewpoint: Dewpoint in Celsius
        altimeter: Altimeter setting (hPa or inHg)
        flight_category: Computed flight category
        validity_start: TAF validity period start
        validity_end: TAF validity period end
        trends: Nested WeatherReport objects for TAF change groups
        trend_type: Type of trend (BECMG, TEMPO, FM)
        probability: TAF trend probability percentage
        source: Data source identifier
    """

    # Identity
    icao: str = ""
    report_type: WeatherType = WeatherType.METAR
    raw_text: str = ""
    observation_time: Optional[datetime] = None

    # Wind
    wind_direction: Optional[int] = None
    wind_speed: Optional[int] = None
    wind_gust: Optional[int] = None
    wind_variable_from: Optional[int] = None
    wind_variable_to: Optional[int] = None
    wind_unit: str = "KT"

    # Visibility
    visibility_meters: Optional[int] = None
    visibility_sm: Optional[float] = None

    # Ceiling & clouds
    ceiling_ft: Optional[int] = None
    cavok: bool = False
    clouds: List[Dict[str, Any]] = field(default_factory=list)

    # Weather phenomena
    weather_conditions: List[str] = field(default_factory=list)

    # Temperature & pressure
    temperature: Optional[int] = None
    dewpoint: Optional[int] = None
    altimeter: Optional[float] = None

    # Flight category
    flight_category: Optional[FlightCategory] = None

    # TAF validity
    validity_start: Optional[datetime] = None
    validity_end: Optional[datetime] = None

    # TAF trends (nested WeatherReport objects)
    trends: List['WeatherReport'] = field(default_factory=list)
    trend_type: Optional[str] = None  # "BECMG", "TEMPO", "FM"
    probability: Optional[int] = None

    # Metadata
    source: str = ""

    @classmethod
    def from_metar(cls, raw_text: str, source: str = "") -> Optional['WeatherReport']:
        """
        Parse a METAR string into a WeatherReport.

        Args:
            raw_text: Raw METAR text
            source: Data source identifier

        Returns:
            WeatherReport or None if parsing fails
        """
        from euro_aip.briefing.weather.parser import WeatherParser
        return WeatherParser.parse_metar(raw_text, source=source)

    @classmethod
    def from_taf(cls, raw_text: str, source: str = "") -> Optional['WeatherReport']:
        """
        Parse a TAF string into a WeatherReport.

        Args:
            raw_text: Raw TAF text
            source: Data source identifier

        Returns:
            WeatherReport or None if parsing fails
        """
        from euro_aip.briefing.weather.parser import WeatherParser
        return WeatherParser.parse_taf(raw_text, source=source)

    def wind_components(
        self,
        runway_heading: int,
        runway_ident: str = "",
    ) -> Optional[WindComponents]:
        """
        Calculate wind components for a given runway.

        Args:
            runway_heading: Runway heading in degrees
            runway_ident: Runway identifier (e.g., "27L")

        Returns:
            WindComponents or None if wind data unavailable
        """
        from euro_aip.briefing.weather.analysis import WeatherAnalyzer
        return WeatherAnalyzer.wind_components(self, runway_heading, runway_ident)

    def to_dict(self) -> dict:
        """Serialize to dictionary for JSON export."""
        return {
            'icao': self.icao,
            'report_type': self.report_type.value if self.report_type else None,
            'raw_text': self.raw_text,
            'observation_time': self.observation_time.isoformat() if self.observation_time else None,
            'wind_direction': self.wind_direction,
            'wind_speed': self.wind_speed,
            'wind_gust': self.wind_gust,
            'wind_variable_from': self.wind_variable_from,
            'wind_variable_to': self.wind_variable_to,
            'wind_unit': self.wind_unit,
            'visibility_meters': self.visibility_meters,
            'visibility_sm': self.visibility_sm,
            'ceiling_ft': self.ceiling_ft,
            'cavok': self.cavok,
            'clouds': self.clouds,
            'weather_conditions': self.weather_conditions,
            'temperature': self.temperature,
            'dewpoint': self.dewpoint,
            'altimeter': self.altimeter,
            'flight_category': self.flight_category.value if self.flight_category else None,
            'validity_start': self.validity_start.isoformat() if self.validity_start else None,
            'validity_end': self.validity_end.isoformat() if self.validity_end else None,
            'trends': [t.to_dict() for t in self.trends],
            'trend_type': self.trend_type,
            'probability': self.probability,
            'source': self.source,
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'WeatherReport':
        """Create WeatherReport from dictionary."""
        observation_time = None
        if data.get('observation_time'):
            observation_time = datetime.fromisoformat(data['observation_time'])

        report_type = WeatherType.METAR
        if data.get('report_type'):
            try:
                report_type = WeatherType(data['report_type'])
            except ValueError:
                pass

        flight_category = None
        if data.get('flight_category'):
            try:
                flight_category = FlightCategory(data['flight_category'])
            except ValueError:
                pass

        validity_start = None
        if data.get('validity_start'):
            validity_start = datetime.fromisoformat(data['validity_start'])

        validity_end = None
        if data.get('validity_end'):
            validity_end = datetime.fromisoformat(data['validity_end'])

        trends = []
        if data.get('trends'):
            trends = [WeatherReport.from_dict(t) for t in data['trends']]

        return cls(
            icao=data.get('icao', ''),
            report_type=report_type,
            raw_text=data.get('raw_text', ''),
            observation_time=observation_time,
            wind_direction=data.get('wind_direction'),
            wind_speed=data.get('wind_speed'),
            wind_gust=data.get('wind_gust'),
            wind_variable_from=data.get('wind_variable_from'),
            wind_variable_to=data.get('wind_variable_to'),
            wind_unit=data.get('wind_unit', 'KT'),
            visibility_meters=data.get('visibility_meters'),
            visibility_sm=data.get('visibility_sm'),
            ceiling_ft=data.get('ceiling_ft'),
            cavok=data.get('cavok', False),
            clouds=data.get('clouds', []),
            weather_conditions=data.get('weather_conditions', []),
            temperature=data.get('temperature'),
            dewpoint=data.get('dewpoint'),
            altimeter=data.get('altimeter'),
            flight_category=flight_category,
            validity_start=validity_start,
            validity_end=validity_end,
            trends=trends,
            trend_type=data.get('trend_type'),
            probability=data.get('probability'),
            source=data.get('source', ''),
        )

    def __repr__(self) -> str:
        cat = f" {self.flight_category.value}" if self.flight_category else ""
        return f"WeatherReport({self.report_type.value} {self.icao}{cat})"
