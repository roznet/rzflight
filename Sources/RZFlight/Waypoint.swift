//
//  Waypoint.swift
//  RZFlight
//
//  Named navigation waypoint (5-letter codes and NAVAIDs like VOR/DME/NDB).
//

import Foundation
import CoreLocation
import FMDB

/// A named navigation waypoint with coordinates.
///
/// Waypoints come from sources like Eurocontrol's FRA (Free Route Airspace)
/// points list. Used alongside airports for route resolution.
public struct Waypoint: Codable, Sendable {

    /// Waypoint name (e.g., "BILGO", "REM") — primary key
    public let name: String

    /// Pre-computed lowercase name for fast search
    public let nameLower: String

    /// Latitude in decimal degrees
    public let latitude: Double

    /// Longitude in decimal degrees
    public let longitude: Double

    /// Point type: "5LNC", "VOR", "DME", "VORDME", "NDB", "VORTAC", "NDBDME", "LOCATOR"
    public let pointType: String?

    /// Comma-separated FIR ICAO codes
    public let firCodes: String?

    /// Level availability (e.g., "FL195 / FL660")
    public let levelAvailability: String?

    /// Data source identifier
    public let source: String?

    /// Coordinates as CLLocationCoordinate2D
    public var coordinate: CLLocationCoordinate2D {
        return CLLocationCoordinate2D(latitude: latitude, longitude: longitude)
    }

    /// Whether this is a NAVAID (VOR, DME, NDB, etc.) rather than a 5-letter code
    public var isNavaid: Bool {
        guard let pt = pointType else { return false }
        return pt != "5LNC"
    }

    /// FIR codes as an array
    public var firList: [String] {
        guard let codes = firCodes else { return [] }
        return codes.split(separator: ",").map { $0.trimmingCharacters(in: .whitespaces) }
    }

    // MARK: - Initialization

    public init(name: String, latitude: Double, longitude: Double,
                pointType: String? = nil, firCodes: String? = nil,
                levelAvailability: String? = nil, source: String? = nil) {
        self.name = name
        self.nameLower = name.lowercased()
        self.latitude = latitude
        self.longitude = longitude
        self.pointType = pointType
        self.firCodes = firCodes
        self.levelAvailability = levelAvailability
        self.source = source
    }

    /// Initialize from a database result set.
    public init?(res: FMResultSet) {
        guard let name = res.string(forColumn: "name") else { return nil }

        self.name = name
        self.nameLower = name.lowercased()
        self.latitude = res.double(forColumn: "latitude_deg")
        self.longitude = res.double(forColumn: "longitude_deg")
        self.pointType = res.string(forColumn: "point_type")
        self.firCodes = res.string(forColumn: "fir_codes")
        self.levelAvailability = res.string(forColumn: "level_availability")
        self.source = res.string(forColumn: "source")
    }

    // MARK: - Search

    public func contains(_ searchText: String) -> Bool {
        return nameLower.contains(searchText.lowercased())
    }

    func matches(_ needle: String) -> Bool {
        return nameLower.contains(needle.lowercased())
    }

    // MARK: - Codable

    enum CodingKeys: String, CodingKey {
        case name
        case latitude = "latitude_deg"
        case longitude = "longitude_deg"
        case pointType = "point_type"
        case firCodes = "fir_codes"
        case levelAvailability = "level_availability"
        case source
    }

    public init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        let name = try container.decode(String.self, forKey: .name)
        self.name = name
        self.nameLower = name.lowercased()
        self.latitude = try container.decode(Double.self, forKey: .latitude)
        self.longitude = try container.decode(Double.self, forKey: .longitude)
        self.pointType = try container.decodeIfPresent(String.self, forKey: .pointType)
        self.firCodes = try container.decodeIfPresent(String.self, forKey: .firCodes)
        self.levelAvailability = try container.decodeIfPresent(String.self, forKey: .levelAvailability)
        self.source = try container.decodeIfPresent(String.self, forKey: .source)
    }
}

// MARK: - Protocol Conformances

extension Waypoint: Hashable {
    public static func == (lhs: Waypoint, rhs: Waypoint) -> Bool {
        return lhs.name == rhs.name
    }

    public func hash(into hasher: inout Hasher) {
        hasher.combine(name)
    }
}

extension Waypoint: Identifiable {
    public var id: String { name }
}

extension Waypoint: CustomStringConvertible {
    public var description: String {
        if let pt = pointType, pt != "5LNC" {
            return "\(name) (\(pt))"
        }
        return name
    }
}
