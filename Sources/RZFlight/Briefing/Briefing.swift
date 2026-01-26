//
//  Briefing.swift
//  RZFlight
//
//  Flight briefing container model.
//  Decodes from Python euro_aip.briefing JSON format.
//

import Foundation

/// Container for flight briefing data.
///
/// A Briefing holds all flight-related information for a specific route/time,
/// including NOTAMs, route information, and metadata about the briefing source.
///
/// Load from JSON produced by Python's `euro_aip.briefing` module:
/// ```swift
/// let briefing = try Briefing.load(from: fileURL)
///
/// // Query NOTAMs
/// let critical = briefing.notams
///     .forAirport(briefing.route?.departure ?? "")
///     .activeNow()
///     .runwayRelated()
/// ```
public struct Briefing: Codable, Sendable {

    // MARK: - Identity

    /// Unique briefing identifier (UUID)
    public let id: String

    /// When the briefing was created
    public let createdAt: Date

    /// Source identifier (e.g., "foreflight", "avwx")
    public let source: String

    // MARK: - Content

    /// Flight route information
    public let route: Route?

    /// All NOTAMs in the briefing
    public let notams: [Notam]

    // MARK: - Validity

    /// Briefing validity start time
    public let validFrom: Date?

    /// Briefing validity end time
    public let validTo: Date?

    // MARK: - Convenience Properties

    /// Departure airport ICAO (from route)
    public var departure: String? {
        return route?.departure
    }

    /// Destination airport ICAO (from route)
    public var destination: String? {
        return route?.destination
    }

    /// NOTAMs for the departure airport
    public var departureNotams: [Notam] {
        guard let dep = route?.departure else { return [] }
        return notams.forAirport(dep)
    }

    /// NOTAMs for the destination airport
    public var destinationNotams: [Notam] {
        guard let dest = route?.destination else { return [] }
        return notams.forAirport(dest)
    }

    /// NOTAMs for alternate airports
    public var alternateNotams: [Notam] {
        guard let alts = route?.alternates, !alts.isEmpty else { return [] }
        return notams.forAirports(alts)
    }

    /// NOTAMs active during the flight window
    public var flightWindowNotams: [Notam] {
        guard let window = route?.flightWindow() else {
            return notams.activeNow()
        }
        return notams.activeDuring(window.start, to: window.end)
    }

    // MARK: - CodingKeys

    enum CodingKeys: String, CodingKey {
        case id
        case createdAt = "created_at"
        case source
        case route
        case notams
        case validFrom = "valid_from"
        case validTo = "valid_to"
    }

    // MARK: - Decoding

    public init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)

        self.id = try container.decodeIfPresent(String.self, forKey: .id) ?? UUID().uuidString
        self.createdAt = try container.decodeIfPresent(Date.self, forKey: .createdAt) ?? Date()
        self.source = try container.decodeIfPresent(String.self, forKey: .source) ?? ""
        self.route = try container.decodeIfPresent(Route.self, forKey: .route)
        self.notams = try container.decodeIfPresent([Notam].self, forKey: .notams) ?? []
        self.validFrom = try container.decodeIfPresent(Date.self, forKey: .validFrom)
        self.validTo = try container.decodeIfPresent(Date.self, forKey: .validTo)
    }

    // MARK: - Loading

    /// Load a briefing from a JSON file
    ///
    /// - Parameter url: URL to the JSON file
    /// - Returns: Decoded Briefing
    /// - Throws: Decoding errors
    public static func load(from url: URL) throws -> Briefing {
        let data = try Data(contentsOf: url)
        return try load(from: data)
    }

    /// Load a briefing from JSON data
    ///
    /// - Parameter data: JSON data
    /// - Returns: Decoded Briefing
    /// - Throws: Decoding errors
    public static func load(from data: Data) throws -> Briefing {
        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601
        return try decoder.decode(Briefing.self, from: data)
    }

    /// Load a briefing from a JSON string
    ///
    /// - Parameter json: JSON string
    /// - Returns: Decoded Briefing
    /// - Throws: Decoding errors
    public static func load(from json: String) throws -> Briefing {
        guard let data = json.data(using: .utf8) else {
            throw DecodingError.dataCorrupted(
                DecodingError.Context(codingPath: [], debugDescription: "Invalid UTF-8 string")
            )
        }
        return try load(from: data)
    }
}

// MARK: - Memberwise Initializer

extension Briefing {
    /// Create a Briefing with all fields specified
    public init(
        id: String = UUID().uuidString,
        createdAt: Date = Date(),
        source: String,
        route: Route? = nil,
        notams: [Notam] = [],
        validFrom: Date? = nil,
        validTo: Date? = nil
    ) {
        self.id = id
        self.createdAt = createdAt
        self.source = source
        self.route = route
        self.notams = notams
        self.validFrom = validFrom
        self.validTo = validTo
    }
}

// MARK: - Protocol Conformances

extension Briefing: Identifiable {}

extension Briefing: CustomStringConvertible {
    public var description: String {
        let routeStr = route?.description ?? "no route"
        return "Briefing(\(source), \(routeStr), \(notams.count) NOTAMs)"
    }
}
