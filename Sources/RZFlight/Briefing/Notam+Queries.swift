//
//  Notam+Queries.swift
//  RZFlight
//
//  Filtering extensions for NOTAM collections.
//  Mirrors Python euro_aip.briefing NotamCollection API.
//

import Foundation
import CoreLocation
import MapKit

// MARK: - Location Filters

extension Array where Element == Notam {

    /// Filter NOTAMs affecting a specific airport
    ///
    /// - Parameter icao: ICAO code (case-insensitive)
    /// - Returns: NOTAMs where location matches or airport is in affectedLocations
    public func forAirport(_ icao: String) -> [Notam] {
        let icaoUpper = icao.uppercased()
        return filter {
            $0.location.uppercased() == icaoUpper ||
            $0.affectedLocations.contains { $0.uppercased() == icaoUpper }
        }
    }

    /// Filter NOTAMs affecting any of the specified airports
    ///
    /// - Parameter icaos: List of ICAO codes
    /// - Returns: NOTAMs affecting any of the airports
    public func forAirports(_ icaos: [String]) -> [Notam] {
        let icaosUpper = Set(icaos.map { $0.uppercased() })
        return filter { notam in
            icaosUpper.contains(notam.location.uppercased()) ||
            notam.affectedLocations.contains { icaosUpper.contains($0.uppercased()) }
        }
    }

    /// Filter NOTAMs for a specific FIR
    ///
    /// - Parameter fir: FIR code
    /// - Returns: NOTAMs in the specified FIR
    public func forFir(_ fir: String) -> [Notam] {
        let firUpper = fir.uppercased()
        return filter { $0.fir?.uppercased() == firUpper }
    }
}

// MARK: - Time Filters

extension Array where Element == Notam {

    /// Filter NOTAMs currently active
    public func activeNow() -> [Notam] {
        return activeDuring(Date(), to: Date())
    }

    /// Filter NOTAMs active at a specific time
    ///
    /// - Parameter date: The time to check
    /// - Returns: NOTAMs active at that time
    public func activeAt(_ date: Date) -> [Notam] {
        return filter { $0.isActive(at: date) }
    }

    /// Filter NOTAMs active during any part of a time window
    ///
    /// Use for flight planning - pass departure and arrival times.
    ///
    /// - Parameters:
    ///   - start: Window start (e.g., departure time)
    ///   - end: Window end (e.g., arrival time + buffer)
    /// - Returns: NOTAMs active during any part of the window
    public func activeDuring(_ start: Date, to end: Date) -> [Notam] {
        return filter { $0.isActive(during: start, to: end) }
    }

    /// Filter NOTAMs that become effective after a given time
    ///
    /// - Parameter date: Time threshold
    /// - Returns: NOTAMs with effectiveFrom > date
    public func effectiveAfter(_ date: Date) -> [Notam] {
        return filter { notam in
            guard let from = notam.effectiveFrom else { return false }
            return from > date
        }
    }

    /// Filter NOTAMs that expire before a given time
    ///
    /// - Parameter date: Time threshold
    /// - Returns: Temporary NOTAMs with effectiveTo < date
    public func expiringBefore(_ date: Date) -> [Notam] {
        return filter { notam in
            guard !notam.isPermanent, let to = notam.effectiveTo else { return false }
            return to < date
        }
    }

    /// Filter permanent NOTAMs (no end date)
    public func permanent() -> [Notam] {
        return filter { $0.isPermanent }
    }

    /// Filter temporary NOTAMs (have end date)
    public func temporary() -> [Notam] {
        return filter { !$0.isPermanent }
    }
}

// MARK: - Category Filters

extension Array where Element == Notam {

    /// Filter by ICAO NotamCategory
    ///
    /// - Parameter category: The category to filter by
    /// - Returns: NOTAMs with matching category
    public func byCategory(_ category: NotamCategory) -> [Notam] {
        return filter { $0.category == category }
    }

    /// Filter runway-related NOTAMs (movement area + lighting)
    public func runwayRelated() -> [Notam] {
        return filter { notam in
            notam.icaoCategory == .agaMovement ||
            notam.icaoCategory == .agaLighting ||
            notam.qCode?.hasPrefix("QMR") == true
        }
    }

    /// Filter navigation-related NOTAMs (VOR, ILS, DME, etc.)
    public func navigationRelated() -> [Notam] {
        return filter {
            $0.icaoCategory == .navigation ||
            $0.icaoCategory == .cnsILS ||
            $0.icaoCategory == .cnsGNSS
        }
    }

    /// Filter airspace-related NOTAMs (TFRs, restricted areas)
    public func airspaceRelated() -> [Notam] {
        return filter {
            $0.icaoCategory == .airspaceRestrictions ||
            $0.icaoCategory == .atmAirspace
        }
    }

    /// Filter procedure-related NOTAMs (SID, STAR, approaches)
    public func procedureRelated() -> [Notam] {
        return filter { $0.icaoCategory == .atmProcedures }
    }

    /// Filter obstacle NOTAMs (cranes, towers)
    /// Obstacles are in "Other Information" category with subject codes OB, OL
    public func obstacleRelated() -> [Notam] {
        return filter { notam in
            notam.qCodeSubject == "OB" || notam.qCodeSubject == "OL"
        }
    }
}

// MARK: - Q-Code Filters

extension Array where Element == Notam {

    /// Filter by exact Q-code match
    ///
    /// - Parameter qCode: 5-letter Q-code (e.g., "QMRLC")
    /// - Returns: NOTAMs with matching Q-code
    public func byQCode(_ qCode: String) -> [Notam] {
        let qUpper = qCode.uppercased()
        return filter { $0.qCode?.uppercased() == qUpper }
    }

    /// Filter by Q-code prefix
    ///
    /// Common prefixes:
    /// - QM: Movement area (runway, taxiway)
    /// - QL: Lighting
    /// - QN: Navigation aids
    /// - QO: Obstacles
    /// - QR: Procedures
    /// - QA: Aerodrome
    ///
    /// - Parameter prefix: Q-code prefix (e.g., "QM")
    /// - Returns: NOTAMs with Q-codes starting with prefix
    public func byQCodePrefix(_ prefix: String) -> [Notam] {
        let prefixUpper = prefix.uppercased()
        return filter { $0.qCode?.uppercased().hasPrefix(prefixUpper) == true }
    }

    /// Filter by traffic type from Q-line
    ///
    /// - Parameter traffic: "I" (IFR), "V" (VFR), or "IV" (both)
    /// - Returns: NOTAMs affecting the specified traffic type
    public func byTrafficType(_ traffic: String) -> [Notam] {
        let trafficUpper = traffic.uppercased()
        return filter { notam in
            guard let type = notam.trafficType?.uppercased() else { return false }
            return type.contains(trafficUpper) || trafficUpper.contains(type)
        }
    }

    /// Filter by scope from Q-line
    ///
    /// - Parameter scope: "A" (aerodrome), "E" (enroute), "W" (warning)
    /// - Returns: NOTAMs with matching scope
    public func byScope(_ scope: String) -> [Notam] {
        let scopeUpper = scope.uppercased()
        return filter { notam in
            guard let s = notam.scope?.uppercased() else { return false }
            return s.contains(scopeUpper)
        }
    }
}

// MARK: - Custom Category Filters (from CategorizationPipeline)

extension Array where Element == Notam {

    /// Filter by custom category assigned by categorization pipeline
    ///
    /// - Parameter category: Category name (e.g., "runway", "obstacle")
    /// - Returns: NOTAMs with the category in customCategories
    public func byCustomCategory(_ category: String) -> [Notam] {
        return filter { $0.customCategories.contains(category) }
    }

    /// Filter by custom tag assigned by categorization pipeline
    ///
    /// - Parameter tag: Tag name (e.g., "crane", "closed", "ils")
    /// - Returns: NOTAMs with the tag in customTags
    public func byCustomTag(_ tag: String) -> [Notam] {
        return filter { $0.customTags.contains(tag) }
    }

    /// Filter by primary category from pipeline
    ///
    /// - Parameter category: Primary category string
    /// - Returns: NOTAMs where primaryCategory matches
    public func byPrimaryCategory(_ category: String) -> [Notam] {
        return filter { $0.primaryCategory == category }
    }
}

// MARK: - Altitude Filters

extension Array where Element == Notam {

    /// Filter NOTAMs with upper limit below specified altitude
    ///
    /// - Parameter feet: Altitude in feet
    /// - Returns: NOTAMs entirely below the altitude
    public func belowAltitude(_ feet: Int) -> [Notam] {
        return filter { notam in
            guard let upper = notam.upperLimit else { return false }
            return upper <= feet
        }
    }

    /// Filter NOTAMs with lower limit above specified altitude
    ///
    /// - Parameter feet: Altitude in feet
    /// - Returns: NOTAMs entirely above the altitude
    public func aboveAltitude(_ feet: Int) -> [Notam] {
        return filter { notam in
            guard let lower = notam.lowerLimit else { return false }
            return lower >= feet
        }
    }

    /// Filter NOTAMs affecting an altitude range
    ///
    /// - Parameters:
    ///   - lower: Lower bound in feet
    ///   - upper: Upper bound in feet
    /// - Returns: NOTAMs that overlap with the altitude range
    public func inAltitudeRange(_ lower: Int, to upper: Int) -> [Notam] {
        return filter { notam in
            let notamLower = notam.lowerLimit ?? 0
            let notamUpper = notam.upperLimit ?? 99999
            return notamLower <= upper && notamUpper >= lower
        }
    }
}

// MARK: - Content Filters

extension Array where Element == Notam {

    /// Filter NOTAMs containing specific text
    ///
    /// - Parameter text: Text to search for (case-insensitive)
    /// - Returns: NOTAMs with text in rawText or message
    public func containing(_ text: String) -> [Notam] {
        let textUpper = text.uppercased()
        return filter {
            $0.rawText.uppercased().contains(textUpper) ||
            $0.message.uppercased().contains(textUpper)
        }
    }

    /// Filter NOTAMs matching a regex pattern
    ///
    /// - Parameter pattern: Regular expression pattern
    /// - Returns: NOTAMs matching the pattern in rawText or message
    public func matching(_ pattern: String) -> [Notam] {
        guard let regex = try? NSRegularExpression(pattern: pattern, options: .caseInsensitive) else {
            return []
        }
        return filter { notam in
            let rawRange = NSRange(notam.rawText.startIndex..., in: notam.rawText)
            let msgRange = NSRange(notam.message.startIndex..., in: notam.message)
            return regex.firstMatch(in: notam.rawText, range: rawRange) != nil ||
                   regex.firstMatch(in: notam.message, range: msgRange) != nil
        }
    }
}

// MARK: - Spatial Filters

extension Array where Element == Notam {

    /// Filter NOTAMs within a radius of a point
    ///
    /// - Parameters:
    ///   - coordinate: Center point
    ///   - radiusNm: Radius in nautical miles
    /// - Returns: NOTAMs with coordinates within the radius
    public func withinRadius(of coordinate: CLLocationCoordinate2D, nm radiusNm: Double) -> [Notam] {
        let center = CLLocation(latitude: coordinate.latitude, longitude: coordinate.longitude)
        let radiusMeters = radiusNm * 1852.0

        return filter { notam in
            guard let coord = notam.coordinate else { return false }
            let location = CLLocation(latitude: coord.latitude, longitude: coord.longitude)
            return center.distance(from: location) <= radiusMeters
        }
    }

    /// Filter NOTAMs near specific airports
    ///
    /// - Parameters:
    ///   - icaos: List of ICAO codes
    ///   - radiusNm: Radius around each airport
    ///   - coordinates: Dict mapping ICAO to coordinates
    /// - Returns: NOTAMs within radius of any airport, or matching by location field
    public func nearAirports(
        _ icaos: [String],
        radiusNm: Double,
        coordinates: [String: CLLocationCoordinate2D]
    ) -> [Notam] {
        return filter { notam in
            // Include if location matches (for NOTAMs without coords)
            let icaosUpper = Set(icaos.map { $0.uppercased() })
            if icaosUpper.contains(notam.location.uppercased()) {
                return true
            }

            // Check distance if NOTAM has coordinates
            guard let notamCoord = notam.coordinate else { return false }
            let notamLocation = CLLocation(latitude: notamCoord.latitude, longitude: notamCoord.longitude)
            let radiusMeters = radiusNm * 1852.0

            for icao in icaos {
                if let aptCoord = coordinates[icao] {
                    let aptLocation = CLLocation(latitude: aptCoord.latitude, longitude: aptCoord.longitude)
                    if notamLocation.distance(from: aptLocation) <= radiusMeters {
                        return true
                    }
                }
            }
            return false
        }
    }
}

// MARK: - Grouping

extension Array where Element == Notam {

    /// Group NOTAMs by primary airport
    ///
    /// - Returns: Dictionary mapping ICAO codes to NOTAMs
    public func groupedByAirport() -> [String: [Notam]] {
        return Dictionary(grouping: self) { $0.location }
    }

    /// Group NOTAMs by ICAO category
    ///
    /// - Returns: Dictionary mapping categories to NOTAMs
    public func groupedByCategory() -> [NotamCategory: [Notam]] {
        var result: [NotamCategory: [Notam]] = [:]
        for notam in self {
            let category = notam.icaoCategory ?? .otherInfo
            result[category, default: []].append(notam)
        }
        return result
    }

    /// Group NOTAMs by custom primary category
    ///
    /// - Returns: Dictionary mapping primary category strings to NOTAMs
    public func groupedByPrimaryCategory() -> [String: [Notam]] {
        var result: [String: [Notam]] = [:]
        for notam in self {
            let category = notam.primaryCategory ?? "uncategorized"
            result[category, default: []].append(notam)
        }
        return result
    }
}

// MARK: - Route Corridor Filters

extension Array where Element == Notam {

    /// Filter NOTAMs within a corridor along a flight route
    ///
    /// Uses perpendicular distance to route segments for NOTAMs with coordinates.
    /// Falls back to airport matching for NOTAMs without coordinates.
    ///
    /// - Parameters:
    ///   - route: Flight route with waypoint coordinates
    ///   - corridorWidthNm: Corridor half-width in nautical miles (e.g., 25nm = 50nm total width)
    /// - Returns: NOTAMs within the corridor or affecting route airports
    ///
    /// Example:
    /// ```swift
    /// let routeNotams = briefing.notams.alongRoute(briefing.route!, withinNm: 25)
    /// ```
    public func alongRoute(_ route: Route, withinNm corridorWidthNm: Double) -> [Notam] {
        let routePoints = route.allCoordinates
        guard !routePoints.isEmpty else { return [] }

        // Collect all route airport ICAOs for fallback matching
        var routeAirports: Set<String> = []
        routeAirports.insert(route.departure.uppercased())
        routeAirports.insert(route.destination.uppercased())
        for alt in route.alternates {
            routeAirports.insert(alt.uppercased())
        }

        return filter { notam in
            // First check: NOTAM location matches a route airport
            if routeAirports.contains(notam.location.uppercased()) {
                return true
            }

            // Second check: Any affected location matches route airports
            for affected in notam.affectedLocations {
                if routeAirports.contains(affected.uppercased()) {
                    return true
                }
            }

            // Third check: Spatial distance for NOTAMs with coordinates
            guard let notamCoord = notam.coordinate else {
                return false
            }

            // Calculate minimum distance to route (including NOTAM radius)
            let notamRadiusNm = notam.radiusNm ?? 0
            let effectiveCorridor = corridorWidthNm + notamRadiusNm

            let minDistance = minimumDistanceToRoute(
                from: notamCoord,
                routePoints: routePoints
            )

            return minDistance <= effectiveCorridor
        }
    }

    /// Filter NOTAMs along a route defined by ICAO codes
    ///
    /// Convenience method when you have airport codes but need coordinates.
    ///
    /// - Parameters:
    ///   - icaoCodes: Space or comma-separated ICAO codes (e.g., "LFPG EGLL" or "LFPG,EGLL")
    ///   - corridorWidthNm: Corridor half-width in nautical miles
    ///   - airportCoordinates: Dictionary mapping ICAO codes to coordinates
    /// - Returns: NOTAMs within the corridor
    public func alongRoute(
        icaoCodes: String,
        withinNm corridorWidthNm: Double,
        airportCoordinates: [String: CLLocationCoordinate2D]
    ) -> [Notam] {
        // Parse ICAO codes (space or comma separated)
        let codes = icaoCodes
            .uppercased()
            .components(separatedBy: CharacterSet(charactersIn: " ,"))
            .filter { !$0.isEmpty }

        guard !codes.isEmpty else { return [] }

        // Build route points from coordinates
        let routePoints = codes.compactMap { airportCoordinates[$0] }

        guard !routePoints.isEmpty else {
            // Fall back to airport matching only
            return forAirports(codes)
        }

        let routeAirportsSet = Set(codes)

        return filter { notam in
            // Airport matching
            if routeAirportsSet.contains(notam.location.uppercased()) {
                return true
            }

            for affected in notam.affectedLocations {
                if routeAirportsSet.contains(affected.uppercased()) {
                    return true
                }
            }

            // Spatial check
            guard let notamCoord = notam.coordinate else {
                return false
            }

            let notamRadiusNm = notam.radiusNm ?? 0
            let effectiveCorridor = corridorWidthNm + notamRadiusNm

            let minDistance = minimumDistanceToRoute(
                from: notamCoord,
                routePoints: routePoints
            )

            return minDistance <= effectiveCorridor
        }
    }

    /// Calculate minimum distance from a point to a route (series of segments)
    ///
    /// - Parameters:
    ///   - point: The point to measure from
    ///   - routePoints: Ordered array of route waypoints
    /// - Returns: Minimum distance in nautical miles
    private func minimumDistanceToRoute(
        from point: CLLocationCoordinate2D,
        routePoints: [CLLocationCoordinate2D]
    ) -> Double {
        guard !routePoints.isEmpty else { return .infinity }

        if routePoints.count == 1 {
            // Single point - direct distance
            return directDistanceNm(from: point, to: routePoints[0])
        }

        var minDistance = Double.infinity

        // Check distance to each segment
        for i in 0..<(routePoints.count - 1) {
            let segmentStart = routePoints[i]
            let segmentEnd = routePoints[i + 1]

            let dist = perpendicularDistanceNm(
                from: point,
                toSegmentStart: segmentStart,
                segmentEnd: segmentEnd
            )
            minDistance = Swift.min(minDistance, dist)
        }

        return minDistance
    }

    /// Calculate perpendicular distance from a point to a line segment
    ///
    /// - Parameters:
    ///   - point: The point to measure from
    ///   - start: Segment start coordinate
    ///   - end: Segment end coordinate
    /// - Returns: Distance in nautical miles
    private func perpendicularDistanceNm(
        from point: CLLocationCoordinate2D,
        toSegmentStart start: CLLocationCoordinate2D,
        segmentEnd end: CLLocationCoordinate2D
    ) -> Double {
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

        if param < 0 {
            // Closest point is segment start
            closestLat = start.latitude
            closestLon = start.longitude
        } else if param > 1 {
            // Closest point is segment end
            closestLat = end.latitude
            closestLon = end.longitude
        } else {
            // Closest point is on the segment
            closestLat = start.latitude + param * C
            closestLon = start.longitude + param * D
        }

        // Calculate distance using MapKit for accuracy
        let pointMap = MKMapPoint(point)
        let closestMap = MKMapPoint(CLLocationCoordinate2D(latitude: closestLat, longitude: closestLon))

        return pointMap.distance(to: closestMap) / 1852.0
    }

    /// Calculate direct distance between two coordinates
    ///
    /// - Returns: Distance in nautical miles
    private func directDistanceNm(
        from point1: CLLocationCoordinate2D,
        to point2: CLLocationCoordinate2D
    ) -> Double {
        let loc1 = CLLocation(latitude: point1.latitude, longitude: point1.longitude)
        let loc2 = CLLocation(latitude: point2.latitude, longitude: point2.longitude)
        return loc1.distance(from: loc2) / 1852.0
    }
}
