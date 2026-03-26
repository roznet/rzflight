//
//  RoutePointResolver.swift
//  RZFlight
//
//  Resolves route strings with mixed airport ICAOs and waypoint names
//  to Route objects with fully populated coordinates.
//

import Foundation
import CoreLocation

/// Resolves route point names to coordinates using airport and waypoint databases.
///
/// Resolution order for each token:
/// 1. Airport lookup (by ICAO code)
/// 2. Waypoint lookup (by name)
/// 3. Unresolved (skipped)
///
/// Usage:
/// ```swift
/// let resolver = RoutePointResolver(airports: knownAirports, waypoints: knownWaypoints)
/// let route = resolver.resolveRoute(departure: "EGTF", destination: "LSGS",
///                                    waypoints: ["VESAN", "POGOL"])
/// ```
public class RoutePointResolver {

    public let airports: KnownAirports
    public let waypoints: KnownWaypoints?

    /// Create a resolver with airport and optional waypoint databases.
    ///
    /// - Parameters:
    ///   - airports: Airport database for ICAO lookups
    ///   - waypoints: Waypoint database (nil for backward compatibility with older DBs)
    public init(airports: KnownAirports, waypoints: KnownWaypoints? = nil) {
        self.airports = airports
        self.waypoints = waypoints
    }

    /// Resolve a single name to a RoutePoint. Tries airport first, then waypoint.
    ///
    /// - Parameter name: ICAO code or waypoint name
    /// - Returns: RoutePoint with coordinates, or nil if not found
    public func resolve(_ name: String) -> RoutePoint? {
        let upper = name.uppercased()

        // Try airport first
        if let airport = airports.airport(icao: upper, ensureRunway: false) {
            return RoutePoint(
                name: upper,
                latitude: airport.coord.latitude,
                longitude: airport.coord.longitude,
                pointType: "airport"
            )
        }

        // Try waypoint
        if let waypoint = waypoints?.waypoint(name: upper) {
            return RoutePoint(
                name: upper,
                latitude: waypoint.latitude,
                longitude: waypoint.longitude,
                pointType: waypoint.pointType ?? "waypoint"
            )
        }

        return nil
    }

    /// Resolve a full route with departure, destination, intermediate waypoints, and alternates.
    ///
    /// - Parameters:
    ///   - departure: Departure airport ICAO
    ///   - destination: Destination airport ICAO
    ///   - waypoints: Intermediate waypoint names (airports or named waypoints)
    ///   - alternates: Alternate airport ICAOs
    /// - Returns: Route with resolved coordinates
    public func resolveRoute(
        departure: String,
        destination: String,
        waypoints: [String] = [],
        alternates: [String] = []
    ) -> Route {
        // Resolve departure
        let depPoint = resolve(departure)
        let depCoords: [Double]? = depPoint.map { [$0.latitude, $0.longitude] }

        // Resolve destination
        let destPoint = resolve(destination)
        let destCoords: [Double]? = destPoint.map { [$0.latitude, $0.longitude] }

        // Resolve alternates
        var altCoords: [String: [Double]] = [:]
        for alt in alternates {
            if let point = resolve(alt) {
                altCoords[alt.uppercased()] = [point.latitude, point.longitude]
            }
        }

        // Resolve intermediate waypoints
        var resolvedNames: [String] = []
        var resolvedCoords: [RoutePoint] = []
        for wp in waypoints {
            if let point = resolve(wp) {
                resolvedNames.append(wp.uppercased())
                resolvedCoords.append(RoutePoint(
                    name: point.name,
                    latitude: point.latitude,
                    longitude: point.longitude,
                    pointType: point.pointType == "airport" ? "waypoint" : point.pointType
                ))
            }
        }

        return Route(
            departure: departure.uppercased(),
            destination: destination.uppercased(),
            alternates: alternates.map { $0.uppercased() },
            waypoints: resolvedNames,
            departureCoords: depCoords,
            destinationCoords: destCoords,
            alternateCoords: altCoords.isEmpty ? nil : altCoords,
            waypointCoords: resolvedCoords
        )
    }

    /// Resolve a space-separated route string.
    ///
    /// The first token is departure, the last is destination,
    /// everything in between is treated as intermediate waypoints.
    /// Common notation tokens (DCT, ->) are filtered out.
    ///
    /// - Parameter routeString: e.g., "EGTF VESAN POGOL LSGS"
    /// - Returns: Route with resolved coordinates, or nil if fewer than 2 tokens
    public func resolveRouteString(_ routeString: String) -> Route? {
        let filtered = ["DCT", "->", "TO"]
        let tokens = routeString.uppercased()
            .split(separator: " ")
            .map(String.init)
            .filter { !filtered.contains($0) }

        guard tokens.count >= 2 else { return nil }

        let departure = tokens[0]
        let destination = tokens[tokens.count - 1]
        let middle = tokens.count > 2 ? Array(tokens[1..<tokens.count - 1]) : []

        return resolveRoute(
            departure: departure,
            destination: destination,
            waypoints: middle
        )
    }

    // MARK: - Search

    /// Search both airports and waypoints, returning combined results.
    ///
    /// Results are merged with airports first, then waypoints, both ranked by relevance.
    ///
    /// - Parameters:
    ///   - needle: Search text
    ///   - limit: Maximum results to return
    /// - Returns: Array of tuples (name, type, coordinate)
    public func search(needle: String, limit: Int = 20) -> [(name: String, type: String, coordinate: CLLocationCoordinate2D)] {
        var results: [(name: String, type: String, coordinate: CLLocationCoordinate2D)] = []

        // Airports first
        let airportResults = airports.rankedSearch(needle: needle, limit: limit)
        for airport in airportResults {
            results.append((name: airport.icao, type: "airport", coordinate: airport.coord))
        }

        // Waypoints
        if let wps = waypoints {
            let remaining = limit - results.count
            if remaining > 0 {
                let wpResults = wps.rankedSearch(needle: needle, limit: remaining)
                for wp in wpResults {
                    results.append((name: wp.name, type: wp.pointType ?? "waypoint", coordinate: wp.coordinate))
                }
            }
        }

        return results
    }
}
