"""Briefing container model."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Dict, Any, TYPE_CHECKING
import json
from pathlib import Path
import uuid

from euro_aip.briefing.models.notam import Notam
from euro_aip.briefing.models.route import Route

if TYPE_CHECKING:
    from euro_aip.briefing.collections.notam_collection import NotamCollection
    from euro_aip.briefing.weather.collection import WeatherCollection
    from euro_aip.briefing.weather.models import WeatherReport
    from euro_aip.models.euro_aip_model import EuroAipModel


@dataclass
class Briefing:
    """
    Container for flight briefing data.

    A Briefing holds all flight-related information for a specific route/time,
    including NOTAMs, route information, and metadata about the briefing source.

    Attributes:
        id: Unique briefing identifier
        created_at: When the briefing was created
        source: Source identifier (e.g., "foreflight", "avwx")
        route: Flight route information
        notams: List of NOTAMs in the briefing

    Example:
        briefing = Briefing(
            id="br-12345",
            source="foreflight",
            route=Route(departure="LFPG", destination="EGLL"),
            notams=[...],
        )

        # Query NOTAMs with fluent API
        runway_notams = briefing.notams_query.runway_related().active_now().all()
    """

    # Identity
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = field(default_factory=datetime.now)
    source: str = ""

    # Route information
    route: Optional[Route] = None

    # NOTAMs
    notams: List[Notam] = field(default_factory=list)

    # Weather reports
    weather_reports: List['WeatherReport'] = field(default_factory=list)

    # Metadata
    valid_from: Optional[datetime] = None
    valid_to: Optional[datetime] = None
    raw_data: Optional[Dict[str, Any]] = None

    # Optional reference to euro_aip model for coordinate lookups
    _model: Optional['EuroAipModel'] = field(default=None, repr=False)

    def set_model(self, model: 'EuroAipModel') -> 'Briefing':
        """
        Set the euro_aip model for coordinate lookups.

        Args:
            model: EuroAipModel instance

        Returns:
            Self for chaining
        """
        self._model = model
        return self

    @property
    def notams_query(self) -> 'NotamCollection':
        """
        Get queryable collection of NOTAMs.

        Returns:
            NotamCollection with fluent filtering API.
            If a model is set, spatial queries will auto-resolve coordinates.

        Example:
            # Filter NOTAMs for departure airport
            departure_notams = briefing.notams_query.for_airport("LFPG").all()

            # Chain multiple filters
            critical = (
                briefing.notams_query
                .for_airport("LFPG")
                .active_now()
                .runway_related()
                .all()
            )
        """
        from euro_aip.briefing.collections.notam_collection import NotamCollection
        return NotamCollection(self.notams, model=self._model)

    @property
    def weather_query(self) -> 'WeatherCollection':
        """
        Get queryable collection of weather reports.

        Returns:
            WeatherCollection with fluent filtering API.

        Example:
            # Get latest METAR for departure
            metar = briefing.weather_query.metars().for_airport("LFPG").latest()

            # Find IFR conditions
            ifr = briefing.weather_query.at_or_worse_than(FlightCategory.IFR).all()
        """
        from euro_aip.briefing.weather.collection import WeatherCollection
        return WeatherCollection(self.weather_reports)

    def to_dict(self) -> dict:
        """
        Serialize to dictionary for JSON export.

        Note: _model reference is not serialized.
        """
        return {
            'id': self.id,
            'created_at': self.created_at.isoformat(),
            'source': self.source,
            'route': self.route.to_dict() if self.route else None,
            'notams': [n.to_dict() for n in self.notams],
            'weather_reports': [w.to_dict() for w in self.weather_reports],
            'valid_from': self.valid_from.isoformat() if self.valid_from else None,
            'valid_to': self.valid_to.isoformat() if self.valid_to else None,
            'raw_data': self.raw_data,
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'Briefing':
        """
        Create Briefing from dictionary.

        Args:
            data: Dictionary with briefing fields

        Returns:
            Briefing instance
        """
        created_at = datetime.now()
        if data.get('created_at'):
            created_at = datetime.fromisoformat(data['created_at'])

        valid_from = None
        if data.get('valid_from'):
            valid_from = datetime.fromisoformat(data['valid_from'])

        valid_to = None
        if data.get('valid_to'):
            valid_to = datetime.fromisoformat(data['valid_to'])

        route = None
        if data.get('route'):
            route = Route.from_dict(data['route'])

        notams = []
        if data.get('notams'):
            notams = [Notam.from_dict(n) for n in data['notams']]

        weather_reports = []
        if data.get('weather_reports'):
            from euro_aip.briefing.weather.models import WeatherReport
            weather_reports = [WeatherReport.from_dict(w) for w in data['weather_reports']]

        return cls(
            id=data.get('id', str(uuid.uuid4())),
            created_at=created_at,
            source=data.get('source', ''),
            route=route,
            notams=notams,
            weather_reports=weather_reports,
            valid_from=valid_from,
            valid_to=valid_to,
            raw_data=data.get('raw_data'),
        )

    def to_json(self, indent: int = 2) -> str:
        """
        Serialize to JSON string.

        Args:
            indent: JSON indentation level

        Returns:
            JSON string
        """
        return json.dumps(self.to_dict(), indent=indent)

    @classmethod
    def from_json(cls, json_str: str) -> 'Briefing':
        """
        Create Briefing from JSON string.

        Args:
            json_str: JSON string

        Returns:
            Briefing instance
        """
        return cls.from_dict(json.loads(json_str))

    def save(self, path: str | Path) -> None:
        """
        Save briefing to JSON file.

        Args:
            path: File path to save to
        """
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.to_json())

    @classmethod
    def load(cls, path: str | Path) -> 'Briefing':
        """
        Load briefing from JSON file.

        Args:
            path: File path to load from

        Returns:
            Briefing instance
        """
        path = Path(path)
        return cls.from_json(path.read_text())

    def __repr__(self) -> str:
        route_str = f"{self.route.departure}->{self.route.destination}" if self.route else "no route"
        wx = f", weather={len(self.weather_reports)}" if self.weather_reports else ""
        return f"Briefing(id={self.id!r}, source={self.source!r}, route={route_str}, notams={len(self.notams)}{wx})"
