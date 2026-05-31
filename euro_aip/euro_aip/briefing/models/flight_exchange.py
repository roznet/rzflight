"""FlightExchange — cross-app flight interchange model.

A shared, language-neutral representation of a "flight" (route + timing +
aircraft) that round-trips between the Python server (``euro_aip``) and the
Swift apps (``RZFlight``), so flights can be exported from one flyfun app and
imported into another.

``FlightExchange`` is a thin envelope around the existing :class:`Route` type:
the ``route`` JSON object is :meth:`Route.to_dict` embedded verbatim, so the
two never drift. The envelope only adds the fields that are *not* on ``Route``:
a display ``name``, the aircraft ``registration``, provenance (``source``), and
a ``schema_version``.

See ``designs/flight_exchange_design.md`` for the full wire format and field
semantics. The Swift counterpart lives in
``Sources/RZFlight/Briefing/FlightExchange.swift`` and must stay in parity.
"""

from dataclasses import dataclass
from typing import Optional

from euro_aip.briefing.models.route import Route

# Wire format version. v1 == designs/flight_exchange_design.md.
# Consumers reject unknown major versions.
SCHEMA_VERSION = 1


@dataclass
class FlightExchange:
    """Cross-app flight interchange envelope around a :class:`Route`.

    Attributes:
        route: The flight route. Serialized verbatim as ``Route.to_dict()`` —
            the single source of route truth (departure/destination/waypoints/
            alternates, coords, times, cruise altitude, aircraft type).
        schema_version: Wire format version (v1 = current).
        name: Optional display title (e.g. "Oxford -> Sion").
        aircraft_registration: Aircraft registration — the cross-app field that
            no app stores at the route level today.
        source_app: Provenance — emitting app ("weather" | "forms" | "brief").
        source_flight_id: Sender's native flight id (opaque to the consumer).
        source_share_code: Present when the sender supports public re-fetch.
    """

    route: Route
    schema_version: int = SCHEMA_VERSION
    name: Optional[str] = None
    aircraft_registration: Optional[str] = None
    source_app: Optional[str] = None
    source_flight_id: Optional[str] = None
    source_share_code: Optional[str] = None

    def to_dict(self) -> dict:
        """Serialize to the language-neutral wire format (snake_case keys).

        Optional envelope fields are omitted when unset, so a minimal flight
        emits just ``schema_version`` and ``route``. The ``aircraft.type`` key
        is a convenience mirror of ``route.aircraft_type`` (the route remains
        the source of truth).
        """
        data: dict = {
            'schema_version': self.schema_version,
            'route': self.route.to_dict(),
        }

        if self.name is not None:
            data['name'] = self.name

        source = {}
        if self.source_app is not None:
            source['app'] = self.source_app
        if self.source_flight_id is not None:
            source['flight_id'] = self.source_flight_id
        if self.source_share_code is not None:
            source['share_code'] = self.source_share_code
        if source:
            data['source'] = source

        aircraft = {}
        if self.aircraft_registration is not None:
            aircraft['registration'] = self.aircraft_registration
        # Convenience mirror of route.aircraft_type.
        if self.route.aircraft_type is not None:
            aircraft['type'] = self.route.aircraft_type
        if aircraft:
            data['aircraft'] = aircraft

        return data

    @classmethod
    def from_dict(cls, data: dict) -> 'FlightExchange':
        """Create from the wire format.

        ``aircraft.type`` is ignored on import — ``route.aircraft_type`` is the
        source of truth, and ``to_dict`` re-mirrors it on the way out.
        """
        # Reject unknown (newer) schema versions before touching any fields —
        # a v2 payload may carry breaking changes this build can't interpret.
        # See design doc.
        version = data.get('schema_version', SCHEMA_VERSION)
        if version > SCHEMA_VERSION:
            raise ValueError(
                f"Unsupported FlightExchange schema_version {version} "
                f"(max supported {SCHEMA_VERSION})"
            )

        source = data.get('source') or {}
        aircraft = data.get('aircraft') or {}

        return cls(
            route=Route.from_dict(data['route']),
            schema_version=version,
            name=data.get('name'),
            aircraft_registration=aircraft.get('registration'),
            source_app=source.get('app'),
            source_flight_id=source.get('flight_id'),
            source_share_code=source.get('share_code'),
        )

    def __repr__(self) -> str:
        return (
            f"FlightExchange({self.route.departure} -> {self.route.destination}"
            f", v{self.schema_version})"
        )
