//
//  Route+Geometry.swift
//  RZFlight
//
//  Route geometry utilities for spatial NOTAM operations.
//  Provides perpendicular distance and along-route distance calculations.
//

import Foundation
import CoreLocation
import MapKit

// MARK: - Route Geometry Extensions

extension Route {

    /// Result of projecting a point onto the route
    public struct RouteProjection {
        /// Perpendicular distance from point to route centerline (nautical miles)
        public let perpendicularDistanceNm: Double

        /// Distance along route from origin to projection point (nautical miles)
        public let alongRouteDistanceNm: Double

        /// Total route length (nautical miles)
        public let totalRouteLengthNm: Double

        /// Normalized position along route (0.0 = origin, 1.0 = destination)
        public var normalizedPosition: Double {
            guard totalRouteLengthNm > 0 else { return 0 }
            return alongRouteDistanceNm / totalRouteLengthNm
        }

        /// Index of the route segment where the projection falls
        public let segmentIndex: Int
    }

    /// Project a coordinate onto this route
    ///
    /// Calculates both perpendicular distance (how far from route) and
    /// along-route distance (how far from origin along the route).
    ///
    /// - Parameter coordinate: The point to project
    /// - Returns: RouteProjection with distances, or nil if route has no coordinates
    public func projectPoint(_ coordinate: CLLocationCoordinate2D) -> RouteProjection? {
        let routePoints = allCoordinates
        guard routePoints.count >= 2 else { return nil }

        var bestPerpendicularDistance = Double.infinity
        var bestAlongRouteDistance = 0.0
        var bestSegmentIndex = 0
        var cumulativeDistance = 0.0

        // Check each segment
        for i in 0..<(routePoints.count - 1) {
            let segmentStart = routePoints[i]
            let segmentEnd = routePoints[i + 1]
            let segmentLength = RouteGeometry.directDistanceNm(from: segmentStart, to: segmentEnd)

            let (perpDistance, projectionRatio) = RouteGeometry.perpendicularDistanceAndRatio(
                from: coordinate,
                toSegmentStart: segmentStart,
                segmentEnd: segmentEnd
            )

            if perpDistance < bestPerpendicularDistance {
                bestPerpendicularDistance = perpDistance
                bestSegmentIndex = i
                // Along-route distance = cumulative + position within segment
                bestAlongRouteDistance = cumulativeDistance + (projectionRatio * segmentLength)
            }

            cumulativeDistance += segmentLength
        }

        return RouteProjection(
            perpendicularDistanceNm: bestPerpendicularDistance,
            alongRouteDistanceNm: bestAlongRouteDistance,
            totalRouteLengthNm: cumulativeDistance,
            segmentIndex: bestSegmentIndex
        )
    }

    /// Calculate total route length in nautical miles
    public var totalLengthNm: Double {
        let routePoints = allCoordinates
        guard routePoints.count >= 2 else { return 0 }

        var total = 0.0
        for i in 0..<(routePoints.count - 1) {
            total += RouteGeometry.directDistanceNm(from: routePoints[i], to: routePoints[i + 1])
        }
        return total
    }
}

// MARK: - Coordinate Geometry Utilities

/// Public geometry utilities for route-related calculations
public enum RouteGeometry {

    /// Calculate direct distance between two coordinates
    ///
    /// - Returns: Distance in nautical miles
    public static func directDistanceNm(
        from point1: CLLocationCoordinate2D,
        to point2: CLLocationCoordinate2D
    ) -> Double {
        let loc1 = CLLocation(latitude: point1.latitude, longitude: point1.longitude)
        let loc2 = CLLocation(latitude: point2.latitude, longitude: point2.longitude)
        return loc1.distance(from: loc2) / 1852.0
    }

    /// Calculate perpendicular distance from a point to a line segment
    ///
    /// - Parameters:
    ///   - point: The point to measure from
    ///   - start: Segment start coordinate
    ///   - end: Segment end coordinate
    /// - Returns: Distance in nautical miles
    public static func perpendicularDistanceNm(
        from point: CLLocationCoordinate2D,
        toSegmentStart start: CLLocationCoordinate2D,
        segmentEnd end: CLLocationCoordinate2D
    ) -> Double {
        return perpendicularDistanceAndRatio(from: point, toSegmentStart: start, segmentEnd: end).distance
    }

    /// Calculate perpendicular distance and projection ratio
    ///
    /// - Parameters:
    ///   - point: The point to measure from
    ///   - start: Segment start coordinate
    ///   - end: Segment end coordinate
    /// - Returns: Tuple of (distance in nm, projection ratio 0-1 along segment)
    public static func perpendicularDistanceAndRatio(
        from point: CLLocationCoordinate2D,
        toSegmentStart start: CLLocationCoordinate2D,
        segmentEnd end: CLLocationCoordinate2D
    ) -> (distance: Double, ratio: Double) {
        // Vector math to find closest point on segment
        let A = point.latitude - start.latitude
        let B = point.longitude - start.longitude
        let C = end.latitude - start.latitude
        let D = end.longitude - start.longitude

        let dot = A * C + B * D
        let lenSq = C * C + D * D
        let param = lenSq > 0 ? dot / lenSq : -1

        var closestLat: Double
        var closestLon: Double
        var clampedParam: Double

        if param < 0 {
            // Closest point is segment start
            closestLat = start.latitude
            closestLon = start.longitude
            clampedParam = 0
        } else if param > 1 {
            // Closest point is segment end
            closestLat = end.latitude
            closestLon = end.longitude
            clampedParam = 1
        } else {
            // Closest point is on the segment
            closestLat = start.latitude + param * C
            closestLon = start.longitude + param * D
            clampedParam = param
        }

        // Calculate distance using MapKit for accuracy
        let pointMap = MKMapPoint(point)
        let closestMap = MKMapPoint(CLLocationCoordinate2D(latitude: closestLat, longitude: closestLon))
        let distanceNm = pointMap.distance(to: closestMap) / 1852.0

        return (distanceNm, clampedParam)
    }

    /// Calculate minimum perpendicular distance from a point to a route polyline
    ///
    /// - Parameters:
    ///   - point: The point to measure from
    ///   - routePoints: Ordered array of route waypoints
    /// - Returns: Minimum distance in nautical miles
    public static func minimumDistanceToRoute(
        from point: CLLocationCoordinate2D,
        routePoints: [CLLocationCoordinate2D]
    ) -> Double {
        guard !routePoints.isEmpty else { return .infinity }

        if routePoints.count == 1 {
            return directDistanceNm(from: point, to: routePoints[0])
        }

        var minDistance = Double.infinity

        for i in 0..<(routePoints.count - 1) {
            let dist = perpendicularDistanceNm(
                from: point,
                toSegmentStart: routePoints[i],
                segmentEnd: routePoints[i + 1]
            )
            minDistance = Swift.min(minDistance, dist)
        }

        return minDistance
    }
}

// MARK: - Notam Route Classification

/// Classification of a NOTAM's position relative to a flight route
public struct NotamRouteClassification {
    /// The route segment this NOTAM belongs to
    public let segment: RouteSegment

    /// Perpendicular distance from route centerline (nm), nil if not applicable
    public let perpendicularDistanceNm: Double?

    /// Distance along route from origin (nm), nil if not applicable
    public let alongRouteDistanceNm: Double?

    /// Public initializer for external use (e.g., FlightContext classification)
    public init(segment: RouteSegment, perpendicularDistanceNm: Double?, alongRouteDistanceNm: Double?) {
        self.segment = segment
        self.perpendicularDistanceNm = perpendicularDistanceNm
        self.alongRouteDistanceNm = alongRouteDistanceNm
    }

    /// Route segment types
    public enum RouteSegment: Int, CaseIterable, Sendable {
        case departure = 0
        case enRoute = 1
        case destination = 2
        case alternates = 3
        case distant = 4
        case noCoordinate = 5

        public var displayName: String {
            switch self {
            case .departure: return "Departure"
            case .enRoute: return "En Route"
            case .destination: return "Destination"
            case .alternates: return "Alternates"
            case .distant: return "Distant NOTAMs"
            case .noCoordinate: return "No Coordinates"
            }
        }

        public var icon: String {
            switch self {
            case .departure: return "airplane.departure"
            case .enRoute: return "point.topleft.down.to.point.bottomright.curvepath"
            case .destination: return "airplane.arrival"
            case .alternates: return "arrow.triangle.branch"
            case .distant: return "scope"
            case .noCoordinate: return "questionmark.circle"
            }
        }
    }
}

extension Notam {

    /// Classify this NOTAM's position relative to a route
    ///
    /// Classification order:
    /// 1. Departure - location matches departure ICAO
    /// 2. Destination - location matches destination ICAO
    /// 3. Alternates - location matches any alternate
    /// 4. En Route - has coordinates, within 50nm of route
    /// 5. Distant - has coordinates, > 50nm from route
    /// 6. No Coordinate - no geographic data
    ///
    /// - Parameters:
    ///   - route: The flight route
    ///   - distantThresholdNm: Distance threshold for "distant" classification (default 50nm)
    /// - Returns: Classification with segment and distances
    public func classifyForRoute(
        _ route: Route,
        distantThresholdNm: Double = 50.0
    ) -> NotamRouteClassification {
        let locationUpper = location.uppercased()

        // Check departure
        if locationUpper == route.departure.uppercased() {
            return NotamRouteClassification(
                segment: .departure,
                perpendicularDistanceNm: 0,
                alongRouteDistanceNm: 0
            )
        }

        // Check destination
        if locationUpper == route.destination.uppercased() {
            return NotamRouteClassification(
                segment: .destination,
                perpendicularDistanceNm: 0,
                alongRouteDistanceNm: route.totalLengthNm
            )
        }

        // Check alternates
        if route.alternates.contains(where: { $0.uppercased() == locationUpper }) {
            return NotamRouteClassification(
                segment: .alternates,
                perpendicularDistanceNm: nil,
                alongRouteDistanceNm: nil
            )
        }

        // Check coordinate-based classification
        guard let coord = coordinate else {
            return NotamRouteClassification(
                segment: .noCoordinate,
                perpendicularDistanceNm: nil,
                alongRouteDistanceNm: nil
            )
        }

        // Project onto route
        guard let projection = route.projectPoint(coord) else {
            return NotamRouteClassification(
                segment: .noCoordinate,
                perpendicularDistanceNm: nil,
                alongRouteDistanceNm: nil
            )
        }

        // Classify based on perpendicular distance
        if projection.perpendicularDistanceNm <= distantThresholdNm {
            return NotamRouteClassification(
                segment: .enRoute,
                perpendicularDistanceNm: projection.perpendicularDistanceNm,
                alongRouteDistanceNm: projection.alongRouteDistanceNm
            )
        } else {
            return NotamRouteClassification(
                segment: .distant,
                perpendicularDistanceNm: projection.perpendicularDistanceNm,
                alongRouteDistanceNm: projection.alongRouteDistanceNm
            )
        }
    }
}

// MARK: - Array Extension for Route Classification

extension Array where Element == Notam {

    /// Classify and group NOTAMs by route segment
    ///
    /// - Parameters:
    ///   - route: The flight route
    ///   - distantThresholdNm: Distance threshold for "distant" classification (default 50nm)
    /// - Returns: Dictionary mapping segments to NOTAMs, with en-route sorted by along-route distance
    public func groupedByRouteSegment(
        route: Route,
        distantThresholdNm: Double = 50.0
    ) -> [NotamRouteClassification.RouteSegment: [(notam: Notam, classification: NotamRouteClassification)]] {

        var result: [NotamRouteClassification.RouteSegment: [(Notam, NotamRouteClassification)]] = [:]

        // Initialize all segments
        for segment in NotamRouteClassification.RouteSegment.allCases {
            result[segment] = []
        }

        // Classify each NOTAM
        for notam in self {
            let classification = notam.classifyForRoute(route, distantThresholdNm: distantThresholdNm)
            result[classification.segment, default: []].append((notam, classification))
        }

        // Sort en-route by along-route distance
        result[.enRoute] = result[.enRoute]?.sorted { lhs, rhs in
            let lhsDist = lhs.1.alongRouteDistanceNm ?? 0
            let rhsDist = rhs.1.alongRouteDistanceNm ?? 0
            return lhsDist < rhsDist
        }

        // Sort distant by perpendicular distance (closest first)
        result[.distant] = result[.distant]?.sorted { lhs, rhs in
            let lhsDist = lhs.1.perpendicularDistanceNm ?? Double.infinity
            let rhsDist = rhs.1.perpendicularDistanceNm ?? Double.infinity
            return lhsDist < rhsDist
        }

        return result
    }
}
