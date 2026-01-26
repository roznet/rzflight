//
//  Route.swift
//  RZFlight
//
//  Flight route model for briefings.
//  Decodes from Python euro_aip.briefing JSON format.
//

import Foundation
import CoreLocation

/// A point along a flight route with coordinates.
public struct RoutePoint: Codable, Sendable {
    /// Waypoint name or ICAO code
    public let name: String

    /// Latitude in decimal degrees
    public let latitude: Double

    /// Longitude in decimal degrees
    public let longitude: Double

    /// Point type: "departure", "destination", "alternate", "waypoint"
    public let pointType: String

    /// Coordinates as CLLocationCoordinate2D
    public var coordinate: CLLocationCoordinate2D {
        return CLLocationCoordinate2D(latitude: latitude, longitude: longitude)
    }

    enum CodingKeys: String, CodingKey {
        case name
        case latitude
        case longitude
        case pointType = "point_type"
    }

    public init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        self.name = try container.decode(String.self, forKey: .name)
        self.latitude = try container.decode(Double.self, forKey: .latitude)
        self.longitude = try container.decode(Double.self, forKey: .longitude)
        self.pointType = try container.decodeIfPresent(String.self, forKey: .pointType) ?? "waypoint"
    }
}

/// Flight route information with coordinates for spatial queries.
///
/// Supports coordinate lookups for departure, destination, alternates,
/// and waypoints. Used for spatial NOTAM filtering.
public struct Route: Codable, Sendable {

    // MARK: - Core Fields

    /// Departure airport ICAO code
    public let departure: String

    /// Destination airport ICAO code
    public let destination: String

    /// Alternate airport ICAO codes
    public let alternates: [String]

    /// Waypoint names along the route
    public let waypoints: [String]

    // MARK: - Coordinates (stored as arrays for Codable)

    private let departureCoords: [Double]?
    private let destinationCoords: [Double]?
    private let alternateCoords: [String: [Double]]?

    /// Full waypoint data with coordinates
    public let waypointCoords: [RoutePoint]

    // MARK: - Flight Details

    /// Aircraft type code
    public let aircraftType: String?

    /// Planned departure time (UTC)
    public let departureTime: Date?

    /// Estimated arrival time (UTC)
    public let arrivalTime: Date?

    /// Cruise flight level (e.g., 350 for FL350)
    public let flightLevel: Int?

    /// Cruise altitude in feet
    public let cruiseAltitudeFt: Int?

    // MARK: - Computed Properties

    /// Departure airport coordinates
    public var departureCoordinate: CLLocationCoordinate2D? {
        guard let coords = departureCoords, coords.count == 2 else { return nil }
        return CLLocationCoordinate2D(latitude: coords[0], longitude: coords[1])
    }

    /// Destination airport coordinates
    public var destinationCoordinate: CLLocationCoordinate2D? {
        guard let coords = destinationCoords, coords.count == 2 else { return nil }
        return CLLocationCoordinate2D(latitude: coords[0], longitude: coords[1])
    }

    /// All airports involved in the route (unique)
    public var allAirports: [String] {
        var airports = [departure, destination]
        airports.append(contentsOf: alternates)
        // Remove duplicates while preserving order
        var seen = Set<String>()
        return airports.filter { seen.insert($0).inserted }
    }

    /// Get coordinates for all route points (departure through waypoints to destination)
    public var allCoordinates: [CLLocationCoordinate2D] {
        var coords: [CLLocationCoordinate2D] = []
        if let dep = departureCoordinate {
            coords.append(dep)
        }
        coords.append(contentsOf: waypointCoords.map { $0.coordinate })
        if let dest = destinationCoordinate {
            coords.append(dest)
        }
        return coords
    }

    /// Get coordinates for a specific airport
    public func coordinate(for icao: String) -> CLLocationCoordinate2D? {
        if icao == departure {
            return departureCoordinate
        }
        if icao == destination {
            return destinationCoordinate
        }
        if let altCoords = alternateCoords?[icao], altCoords.count == 2 {
            return CLLocationCoordinate2D(latitude: altCoords[0], longitude: altCoords[1])
        }
        return nil
    }

    /// Get the flight time window with buffer
    ///
    /// - Parameter bufferMinutes: Buffer time after arrival (default 60)
    /// - Returns: Tuple of (departure, arrival + buffer) or nil if departure time not set
    public func flightWindow(bufferMinutes: Int = 60) -> (start: Date, end: Date)? {
        guard let dep = departureTime else { return nil }
        let end = arrivalTime ?? dep
        return (dep, end.addingTimeInterval(Double(bufferMinutes) * 60))
    }

    // MARK: - CodingKeys

    enum CodingKeys: String, CodingKey {
        case departure
        case destination
        case alternates
        case waypoints
        case departureCoords = "departure_coords"
        case destinationCoords = "destination_coords"
        case alternateCoords = "alternate_coords"
        case waypointCoords = "waypoint_coords"
        case aircraftType = "aircraft_type"
        case departureTime = "departure_time"
        case arrivalTime = "arrival_time"
        case flightLevel = "flight_level"
        case cruiseAltitudeFt = "cruise_altitude_ft"
    }

    // MARK: - Decoding

    public init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)

        self.departure = try container.decode(String.self, forKey: .departure)
        self.destination = try container.decode(String.self, forKey: .destination)
        self.alternates = try container.decodeIfPresent([String].self, forKey: .alternates) ?? []
        self.waypoints = try container.decodeIfPresent([String].self, forKey: .waypoints) ?? []

        self.departureCoords = try container.decodeIfPresent([Double].self, forKey: .departureCoords)
        self.destinationCoords = try container.decodeIfPresent([Double].self, forKey: .destinationCoords)
        self.alternateCoords = try container.decodeIfPresent([String: [Double]].self, forKey: .alternateCoords)
        self.waypointCoords = try container.decodeIfPresent([RoutePoint].self, forKey: .waypointCoords) ?? []

        self.aircraftType = try container.decodeIfPresent(String.self, forKey: .aircraftType)
        self.departureTime = try container.decodeIfPresent(Date.self, forKey: .departureTime)
        self.arrivalTime = try container.decodeIfPresent(Date.self, forKey: .arrivalTime)
        self.flightLevel = try container.decodeIfPresent(Int.self, forKey: .flightLevel)
        self.cruiseAltitudeFt = try container.decodeIfPresent(Int.self, forKey: .cruiseAltitudeFt)
    }
}

// MARK: - Memberwise Initializer

extension Route {
    /// Create a Route with all fields specified
    public init(
        departure: String,
        destination: String,
        alternates: [String] = [],
        waypoints: [String] = [],
        departureCoords: [Double]? = nil,
        destinationCoords: [Double]? = nil,
        alternateCoords: [String: [Double]]? = nil,
        waypointCoords: [RoutePoint] = [],
        aircraftType: String? = nil,
        departureTime: Date? = nil,
        arrivalTime: Date? = nil,
        flightLevel: Int? = nil,
        cruiseAltitudeFt: Int? = nil
    ) {
        self.departure = departure
        self.destination = destination
        self.alternates = alternates
        self.waypoints = waypoints
        self.departureCoords = departureCoords
        self.destinationCoords = destinationCoords
        self.alternateCoords = alternateCoords
        self.waypointCoords = waypointCoords
        self.aircraftType = aircraftType
        self.departureTime = departureTime
        self.arrivalTime = arrivalTime
        self.flightLevel = flightLevel
        self.cruiseAltitudeFt = cruiseAltitudeFt
    }
}

// MARK: - Protocol Conformances

extension Route: CustomStringConvertible {
    public var description: String {
        return "\(departure) -> \(destination)"
    }
}

extension RoutePoint: Hashable, Equatable, Identifiable {
    public var id: String { name }
}

extension RoutePoint {
    /// Create a RoutePoint with all fields specified
    public init(name: String, latitude: Double, longitude: Double, pointType: String = "waypoint") {
        self.name = name
        self.latitude = latitude
        self.longitude = longitude
        self.pointType = pointType
    }
}
