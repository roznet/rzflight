# FlightExchange: Cross-App Flight Interchange Format

> A shared, language-neutral representation of a "flight" (route + timing + aircraft)
> that round-trips between the Python server (`euro_aip`) and the Swift apps (`RZFlight`),
> so flights can be exported from one flyfun app and imported into another.

**Status:** Proposed (design only — not yet implemented).
**Home:** rzflight, in both `RZFlight` (Swift) and `euro_aip` (Python), alongside `Route`.

## Intent

Three flyfun apps each own their own flight records in their own stores, and there is
currently no way to move a flight from one to another:

- **flyfun-weather** — server-of-record (FastAPI + DB). Richest route model.
- **flyfun-forms** — on-device (SwiftData/CloudKit); cares about origin/destination + ETD/ETA + aircraft.
- **flyfunbrief** (flyfun-apps) — on-device (CoreData/CloudKit); cares about the full route for NOTAM filtering.

The goal is **not** to centralize flight storage. Each app keeps its own source of truth.
We only standardize:

1. **Representation** — one in-memory type each side already largely has (`Route`).
2. **A wire format** — `FlightExchange` JSON, emitted and consumed by all sides.

The first concrete use is **import-from-weather**: weather emits a `FlightExchange`, and
forms / brief import it. Weather is the natural source — it has the richest, already-resolved
route, and it's where flights get planned first (a pure downhill data flow).

## Relationship to `Route`

`FlightExchange` is deliberately **a thin envelope around the existing `Route` type**, not a
new parallel model. `Route` (Python `euro_aip/briefing/models/route.py`, Swift
`Sources/RZFlight/Briefing/Route.swift`) already carries everything in the route + timing axis:

```
FlightExchange  ≈  Route  +  { name, aircraft.registration, source, schema_version }
```

| Concept | Already on `Route`? | Added by `FlightExchange` |
|---|---|---|
| departure / destination / waypoints / alternates | ✅ | — |
| resolved coords (`*_coords`, `waypoint_coords`) | ✅ | — |
| `departure_time` / `arrival_time` | ✅ | — |
| `cruise_altitude_ft` / `flight_level` | ✅ | — |
| `aircraft_type` | ✅ | — |
| aircraft **registration** | ❌ | ✅ `aircraft.registration` |
| display name / title | ❌ | ✅ `name` |
| provenance (source app / id / share code) | ❌ | ✅ `source` |
| schema version | ❌ | ✅ `schema_version` |

This is why rzflight is the home: we are wrapping a type that already lives there, in both
languages, with existing `to_dict()`/`from_dict()` parity.

## The wire format

Language-neutral JSON. `snake_case` keys (matches `euro_aip`'s existing `to_dict()`; Swift
maps via `CodingKeys`). The `route` object **is** `Route.to_dict()` output, embedded verbatim,
so the two stay in lockstep — `FlightExchange` never re-describes route fields.

```jsonc
{
  "schema_version": 1,

  // provenance — optional; enables re-fetch / future live-link
  "source": {
    "app": "weather",                               // "weather" | "forms" | "brief"
    "flight_id": "egtk_lsgs-2026-06-01-a1b2",       // sender's native id
    "share_code": "Ab3xY9k2"                        // optional, for re-fetch
  },

  "name": "Oxford → Sion",                          // optional display title

  // route == Route.to_dict() — embedded verbatim, not re-described here
  "route": {
    "departure":   "EGTK",
    "destination": "LSGS",
    "waypoints":   ["BILGO", "XIDIL"],              // intermediate only
    "alternates":  ["LSGG"],
    "departure_time": "2026-06-01T09:00:00Z",       // UTC ISO-8601
    "arrival_time":   "2026-06-01T11:15:00Z",
    "cruise_altitude_ft": 8000,
    "flight_level": null,
    "aircraft_type": "P28A",
    "departure_coords":   [51.83, -1.32],
    "destination_coords": [46.22,  7.33],
    "alternate_coords":   {"LSGG": [46.24, 6.11]},
    "waypoint_coords": [                            // resolved geometry (optional superset)
      {"name": "BILGO", "latitude": 48.50, "longitude": 2.17, "point_type": "waypoint"}
    ],
    "rejected_waypoints": []
    // ...plus any other Route.to_dict() fields (raw_route, etc.) verbatim
  },

  // flight envelope — fields not on Route
  "aircraft": {                                     // optional
    "registration": "HB-ABC",
    "type": "P28A"                                  // mirror of route.aircraft_type for convenience
  }
}
```

### Field semantics

| Key | Req? | Notes |
|---|---|---|
| `schema_version` | ✅ | Integer. v1 = this doc. Consumers reject unknown major versions. |
| `source.app` | — | Provenance; lets a consumer attribute / re-fetch. |
| `source.flight_id` | — | Sender's native id (opaque to consumer). |
| `source.share_code` | — | Present when the sender supports public re-fetch. |
| `name` | — | Display title. weather's `route_name`; absent in forms/brief today. |
| `route` | ✅ | Verbatim `Route.to_dict()`. The single source of route truth. |
| `aircraft.registration` | — | The cross-app field none store at top level today. |
| `aircraft.type` | — | Convenience mirror of `route.aircraft_type`. |

### Times

`departure_time` is the anchor; `arrival_time` is optional (forms wants ETA directly, weather
derives it from duration on emit, brief omits it). Duration is **not** a wire field — it's
`arrival_time − departure_time`, or recomputed by the consumer from its own model.

### Deliberately excluded

- **No PII.** forms' crew / passengers / contact never enter this payload.
- **No app-private fields.** weather's `profile_id`, `flight_ceiling_ft`, `auto_refresh*`,
  `private`; brief's `isArchived`. These don't cross app boundaries.
- **No free-form blob.** The superset is curated. New cross-app needs → add a field + bump
  `schema_version`, not an untyped `extras` bag.

## Encode / decode API

Symmetric, parity-tested across the two implementations (same config-parity discipline as the
briefing parsers — see INDEX.md "Cross-Platform Design").

**Python** (`euro_aip/briefing/models/flight_exchange.py`):
```python
@dataclass
class FlightExchange:
    route: Route
    schema_version: int = 1
    name: str | None = None
    aircraft_registration: str | None = None
    source_app: str | None = None
    source_flight_id: str | None = None
    source_share_code: str | None = None

    def to_dict(self) -> dict: ...
    @classmethod
    def from_dict(cls, d: dict) -> "FlightExchange": ...
```

**Swift** (`Sources/RZFlight/Briefing/FlightExchange.swift`):
```swift
public struct FlightExchange: Codable {
    public var schemaVersion: Int
    public var source: Source?
    public var name: String?
    public var route: Route
    public var aircraft: Aircraft?
    // Codable with snake_case CodingKeys; round-trips Route's existing coding
}
```

Round-trip invariant: `from_dict(to_dict(x)) == x` on both sides, and a payload emitted by
Python decodes byte-compatibly in Swift and vice-versa (parity fixtures shared in repo).

## Per-app adapters

`FlightExchange` is the normalizing contract; **each app maps its native type to/from it**.
The apps' current keys are *not* consistent with each other (different names, different route
shapes, different time models), so each needs a small adapter. Effort varies:

### flyfunbrief — cleanest (and repairs current weakness)
brief already builds a transient `RZFlight.Route` before flattening it into a space-joined
`routeICAOs` string (losing structure, stubbing coords). The adapter is "stop flattening, keep
the `Route`." Importing a weather `FlightExchange` then gives brief real structured routes +
coords → proper en-route NOTAM filtering. **This issue should also fix the existing flat-string
route handling**, not just add import.

Native: `CDFlight { origin, destination, routeICAOs (flat), departureTime, durationHours, cruiseAltitude }`.

### flyfun-weather — most route-axis mapping, on the emit side
weather models the route as a **single `waypoints` list with implicit endpoints** (`waypoints[0]`
= departure, `waypoints[-1]` = destination) and **has no `alternates` concept**. To emit:
- split `waypoints` → `route.departure` / `route.destination` / intermediate `route.waypoints`
- resolve `aircraft_id` (int FK) → `aircraft.registration`
- compute `arrival_time` from `departure_time` + `flight_duration_hours`
- map `route_name` → `name`, copy `raw_route` / coords through

Needs a JSON export endpoint (e.g. `/api/s/{share_code}` returning `FlightExchange`) — the one
genuinely new piece of backend. Decided: the DTO follows `Route`'s explicit-endpoints shape;
**weather is the side that adapts**, not the format.

Native: `Flight { route_name, waypoints[list], departure_time, flight_duration_hours, cruise_altitude_ft, aircraft_id, raw_route, parser_version, share_code }`.

### flyfun-forms — partial consumer
forms only needs `departure` / `destination` / times / aircraft. It ignores `waypoints` /
`waypoint_coords` / `cruise_altitude_ft`. Only fiddly bit: it stores time as split
`date` + `"HH:MM"` UTC strings, so the adapter composes/decomposes ISO datetimes. It reads
`aircraft.registration` / `aircraft.type` into its `Aircraft` relationship.

Native (Swift): `Flight { originICAO, destinationICAO, departureDate, departureTimeUTC, arrivalDate, arrivalTimeUTC, aircraft→{registration,type}, ... PII ... }`.

### Native-key divergence (why an adapter, not a rename)

| FlightExchange | weather | forms | brief |
|---|---|---|---|
| `name` | `route_name` | — | — |
| `route.departure` | `waypoints[0]` *(implicit)* | `originICAO` | `origin` |
| `route.destination` | `waypoints[-1]` *(implicit)* | `destinationICAO` | `destination` |
| `route.waypoints` | `waypoints[1..-2]` | — | `routeICAOs` *(flat, mixed)* |
| `route.alternates` | — | — | folded into `routeICAOs` |
| `route.departure_time` | `departure_time` | `departureDate`+`departureTimeUTC` | `departureTime` |
| `route.arrival_time` | derived | `arrivalDate`+`arrivalTimeUTC` | derived |
| `route.cruise_altitude_ft` | `cruise_altitude_ft` | — | `cruiseAltitude` |
| `aircraft.registration` | `aircraft_id` *(FK)* | `aircraft.registration` | — |

## Transport & privacy (out of scope for the type; noted for the consuming issues)

`FlightExchange` is just the payload. How it travels is each import feature's concern:

- **Public share link** — anyone with weather's `/s/{code}` link imports, no account.
  Lowest friction; non-private flights only.
- **Authed fetch** — importing app signs in with the same flyfun account (uses
  `FlyFunCommon`'s `RollingBearerSession`); works for private flights.

Per the agreed layering: **rzflight owns the representation (this doc); flyfun-common owns
identity/transport when auth is needed; each app owns its own flight records.**

## Implementation order

1. **rzflight** — add `FlightExchange` (Python + Swift), `to_dict`/`from_dict` ↔ `Codable`,
   shared parity fixtures, tests. Bump both package versions. *(Blocks the rest.)*
2. **flyfun-weather** — `aircraft_id`→registration resolve, `waypoints`→endpoints split,
   `arrival_time` compute, and a `FlightExchange` JSON export endpoint.
3. **flyfunbrief** — import a `FlightExchange`; replace flat `routeICAOs` with the structured
   `Route`; wire up universal-link / share handling.
4. **flyfun-forms** — import a `FlightExchange` (origin/dest/times/aircraft subset).

Steps 2–4 depend on 1 and can proceed in parallel once it ships.

## Open questions

- Coords (`waypoint_coords`) in v1 payloads, or codes-only first? (Leaning: include — it's
  the superset payoff and lets brief skip re-resolution.) **Resolved: include.**
- Public-link vs authed-fetch as the v1 transport for the weather export endpoint — decided
  per consuming app, not by this type.
- Whether `name` should fall back to `"DEP → DEST"` when absent (consumer-side default).
