//
//  FlightExchange.swift
//  RZFlight
//
//  Cross-app flight interchange model.
//  Mirrors the Python euro_aip.briefing.models.FlightExchange wire format.
//

import Foundation

/// A shared, language-neutral representation of a "flight" (route + timing +
/// aircraft) that round-trips between the Python server (`euro_aip`) and the
/// Swift apps (`RZFlight`), so a flight can be exported from one flyfun app and
/// imported into another.
///
/// `FlightExchange` is a thin envelope around the existing ``Route`` type: the
/// `route` JSON object is `Route`'s coding embedded verbatim, so the two never
/// drift. The envelope only adds the fields that are *not* on ``Route``: a
/// display ``name``, the aircraft ``registration``, provenance (``source``),
/// and a ``schemaVersion``.
///
/// See `designs/flight_exchange_design.md` for the full wire format. The Python
/// counterpart lives in `euro_aip/briefing/models/flight_exchange.py` and must
/// stay in parity.
public struct FlightExchange: Codable, Sendable {

    /// Wire format version. v1 == designs/flight_exchange_design.md.
    public static let currentSchemaVersion: Int = 1

    // MARK: - Nested Types

    /// Provenance — where the flight came from. All fields optional.
    public struct Source: Codable, Sendable {
        /// Emitting app: "weather" | "forms" | "brief".
        public var app: String?

        /// Sender's native flight id (opaque to the consumer).
        public var flightId: String?

        /// Present when the sender supports public re-fetch.
        public var shareCode: String?

        enum CodingKeys: String, CodingKey {
            case app
            case flightId = "flight_id"
            case shareCode = "share_code"
        }

        public init(app: String? = nil, flightId: String? = nil, shareCode: String? = nil) {
            self.app = app
            self.flightId = flightId
            self.shareCode = shareCode
        }
    }

    /// Aircraft envelope — the cross-app fields not carried on ``Route``.
    public struct Aircraft: Codable, Sendable {
        /// Aircraft registration — the cross-app field none store on the route today.
        public var registration: String?

        /// Convenience mirror of `route.aircraftType` (the route stays the source of truth).
        public var type: String?

        public init(registration: String? = nil, type: String? = nil) {
            self.registration = registration
            self.type = type
        }
    }

    // MARK: - Fields

    /// Wire format version (v1 = current).
    public var schemaVersion: Int

    /// Optional provenance.
    public var source: Source?

    /// Optional display title (e.g. "Oxford -> Sion").
    public var name: String?

    /// The flight route — the single source of route truth.
    public var route: Route

    /// Optional aircraft envelope (registration + type mirror).
    public var aircraft: Aircraft?

    // MARK: - CodingKeys

    enum CodingKeys: String, CodingKey {
        case schemaVersion = "schema_version"
        case source
        case name
        case route
        case aircraft
    }

    // MARK: - Decoding

    public init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        self.schemaVersion = try container.decodeIfPresent(Int.self, forKey: .schemaVersion)
            ?? FlightExchange.currentSchemaVersion
        // Reject unknown (newer) schema versions — a v2 payload may carry
        // breaking changes this build can't interpret. See design doc.
        guard self.schemaVersion <= FlightExchange.currentSchemaVersion else {
            throw DecodingError.dataCorruptedError(
                forKey: .schemaVersion, in: container,
                debugDescription: "Unsupported FlightExchange schema_version "
                    + "\(self.schemaVersion) (max supported "
                    + "\(FlightExchange.currentSchemaVersion))")
        }
        self.source = try container.decodeIfPresent(Source.self, forKey: .source)
        self.name = try container.decodeIfPresent(String.self, forKey: .name)
        self.route = try container.decode(Route.self, forKey: .route)
        self.aircraft = try container.decodeIfPresent(Aircraft.self, forKey: .aircraft)
    }
}

// MARK: - Memberwise Initializer

extension FlightExchange {
    /// Create a FlightExchange with all fields specified.
    public init(
        route: Route,
        schemaVersion: Int = FlightExchange.currentSchemaVersion,
        name: String? = nil,
        source: Source? = nil,
        aircraft: Aircraft? = nil
    ) {
        self.route = route
        self.schemaVersion = schemaVersion
        self.name = name
        self.source = source
        self.aircraft = aircraft
    }
}

// MARK: - Convenience Coding

extension FlightExchange {
    /// Decode a FlightExchange from JSON data, using the snake_case + ISO-8601
    /// conventions of the Python wire format.
    public static func decode(from data: Data) throws -> FlightExchange {
        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601
        return try decoder.decode(FlightExchange.self, from: data)
    }

    /// Encode this FlightExchange to JSON data in the language-neutral wire
    /// format (snake_case keys, ISO-8601 UTC times).
    public func encoded() throws -> Data {
        let encoder = JSONEncoder()
        encoder.dateEncodingStrategy = .iso8601
        return try encoder.encode(self)
    }
}

// MARK: - Protocol Conformances

extension FlightExchange: CustomStringConvertible {
    public var description: String {
        return "FlightExchange(\(route.departure) -> \(route.destination), v\(schemaVersion))"
    }
}
