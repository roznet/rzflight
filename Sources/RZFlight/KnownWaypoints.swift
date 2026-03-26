//
//  KnownWaypoints.swift
//  RZFlight
//
//  Database-backed waypoint lookup with spatial indexing.
//  Parallels KnownAirports for named navigation waypoints.
//

import Foundation
import FMDB
import KDTree
import CoreLocation
import MapKit

extension Waypoint: KDTreePoint {

    public static var dimensions: Int = 2

    public func kdDimension(_ dimension: Int) -> Double {
        if dimension == 0 {
            return latitude
        } else {
            return longitude
        }
    }

    public func squaredDistance(to otherPoint: Waypoint) -> Double {
        let lat = latitude - otherPoint.latitude
        let lon = longitude - otherPoint.longitude
        return lat * lat + lon * lon
    }

    public func distance(to coord: CLLocationCoordinate2D) -> CLLocationDistance {
        return MKMapPoint(CLLocationCoordinate2D(latitude: latitude, longitude: longitude))
            .distance(to: MKMapPoint(coord))
    }
}

/// Database-backed waypoint store with O(1) name lookup and spatial queries via KDTree.
///
/// Usage:
/// ```swift
/// let waypoints = KnownWaypoints(db: db)
/// let wp = waypoints.waypoint(name: "BILGO")
/// let nearest = waypoints.nearest(coord: location, count: 10)
/// ```
public class KnownWaypoints {
    let tree: KDTree<Waypoint>
    let db: FMDatabase
    var known: [String: Waypoint]

    /// Initialize by loading all waypoints from the database.
    ///
    /// Gracefully handles the case where the `waypoints` table doesn't exist
    /// (e.g., older databases), resulting in an empty store.
    public init(db: FMDatabase) {
        var points: [String: Waypoint] = [:]

        // Check if waypoints table exists
        let tableCheck = db.executeQuery(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='waypoints'",
            withArgumentsIn: []
        )
        let hasTable = tableCheck?.next() ?? false
        tableCheck?.close()

        if hasTable {
            if let res = db.executeQuery("SELECT * FROM waypoints", withArgumentsIn: []) {
                while res.next() {
                    if let waypoint = Waypoint(res: res) {
                        points[waypoint.name] = waypoint
                    }
                }
            }
        }

        self.db = db
        self.known = points
        self.tree = KDTree<Waypoint>(values: Array(points.values))
    }

    /// Number of loaded waypoints
    public var count: Int { known.count }

    /// Look up a waypoint by exact name (O(1)).
    public func waypoint(name: String) -> Waypoint? {
        return known[name.uppercased()]
    }

    /// Find nearest waypoints to a coordinate.
    public func nearest(coord: CLLocationCoordinate2D, count: Int) -> [Waypoint] {
        let ref = Waypoint(name: "", latitude: coord.latitude, longitude: coord.longitude)
        return tree.nearestK(count, to: ref)
    }

    /// Find waypoints whose name contains the needle (case-insensitive).
    public func matching(needle: String) -> [Waypoint] {
        let lower = needle.lowercased()
        return known.values.filter { $0.nameLower.contains(lower) }
    }

    /// Ranked search: exact prefix > contains, sorted alphabetically within each tier.
    public func rankedSearch(needle: String, limit: Int = 20) -> [Waypoint] {
        guard !needle.isEmpty else { return [] }
        let lower = needle.lowercased()

        var buckets: [[Waypoint]] = [[], []]

        for (_, waypoint) in known {
            if waypoint.nameLower.hasPrefix(lower) {
                buckets[0].append(waypoint)
            } else if waypoint.nameLower.contains(lower) {
                buckets[1].append(waypoint)
            }
        }

        var result: [Waypoint] = []
        result.reserveCapacity(limit)
        for i in 0..<2 where !buckets[i].isEmpty {
            buckets[i].sort { $0.name < $1.name }
            let remaining = limit - result.count
            result.append(contentsOf: buckets[i].prefix(remaining))
            if result.count >= limit { break }
        }
        return result
    }

    /// Filter waypoints by FIR code.
    public func byFIR(_ firCode: String) -> [Waypoint] {
        let upper = firCode.uppercased()
        return known.values.filter { waypoint in
            waypoint.firList.contains(where: { $0.uppercased() == upper })
        }
    }

    /// Filter waypoints by point type (e.g., "VOR", "DME", "5LNC").
    public func byType(_ pointType: String) -> [Waypoint] {
        let upper = pointType.uppercased()
        return known.values.filter { $0.pointType?.uppercased() == upper }
    }
}
