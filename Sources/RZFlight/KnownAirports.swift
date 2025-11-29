//  MIT License
//
//  Created by Brice Rosenzweig on 05/08/2023.
//
//  Copyright (c) 2023 Brice Rosenzweig
//
//  Permission is hereby granted, free of charge, to any person obtaining a copy
//  of this software and associated documentation files (the "Software"), to deal
//  in the Software without restriction, including without limitation the rights
//  to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
//  copies of the Software, and to permit persons to whom the Software is
//  furnished to do so, subject to the following conditions:
//
//  The above copyright notice and this permission notice shall be included in all
//  copies or substantial portions of the Software.
//
//  THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
//  IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
//  FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
//  AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
//  LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
//  OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
//  SOFTWARE.
//

import Foundation
import FMDB
import KDTree
import CoreLocation
import MapKit

extension Airport : KDTreePoint {
    
    public static var dimensions: Int = 2
    
    public var coordinate: CLLocationCoordinate2D {
        return CLLocationCoordinate2D(latitude: latitude, longitude: longitude)
    }
    public func kdDimension(_ dimension: Int) -> Double {
        if dimension == 0 {
            return latitude
        }else{
            return longitude
        }
    }
    public func squaredDistance(to otherPoint: Airport) -> Double {
        let lat = (latitude-otherPoint.latitude)
        let lon = (longitude-otherPoint.longitude)
        return lat*lat+lon*lon
    }
    public func distance(to: CLLocationCoordinate2D) -> CLLocationDistance {
        return MKMapPoint(CLLocationCoordinate2D(latitude: latitude, longitude: longitude)).distance(to: MKMapPoint(to))
    }
}

public class KnownAirports {
    let tree : KDTree<Airport>
    let db : FMDatabase
    let known : [String:Airport]
    private var borderCrossingICAOs : Set<String>?
    
    public init(db : FMDatabase, where whereClause : String? = nil){
        var points : [String:Airport] = [:]
        var sql = "SELECT * FROM airports"
        if let whereClause = whereClause {
            sql += " WHERE \(whereClause)"
        }
        if let res = db.executeQuery(sql, withArgumentsIn: []){
            while( res.next() ){
                if let airport = Airport(res: res) {
                    points[airport.icao] = airport
                }
            }
        }
        self.db = db
        self.known = points
        self.tree = KDTree<Airport>(values: Array(points.values))
        self.borderCrossingICAOs = nil  // Will be lazily loaded
    }
    
    public func airport(icao : String, ensureRunway: Bool = true) -> Airport? {
        var found = known[icao]
        if ensureRunway {
            _ = found?.addRunways(db: self.db)
        }
        return found
    }
    
    /// Enhanced airport loading with selective data loading
    public func airport(icao: String, 
                       ensureRunway: Bool = true, 
                       ensureProcedures: Bool = false, 
                       ensureAIP: Bool = false) -> Airport? {
        var found = known[icao]
        
        if ensureRunway {
            _ = found?.addRunways(db: self.db)
        }
        
        if ensureProcedures {
            _ = found?.addProcedures(db: self.db)
        }
        
        if ensureAIP {
            _ = found?.addAIPEntries(db: self.db)
        }
        
        return found
    }
    
    /// Load airport with all extended data (runways, procedures, AIP)
    public func airportWithExtendedData(icao: String) -> Airport? {
        var found = known[icao]
        _ = found?.addExtendedData(db: self.db)
        return found
    }
    
    public func nearestAirport(coord : CLLocationCoordinate2D) -> Airport? {
        let found = tree.nearest(to: Airport.at(location: coord))
        return found
    }
    public func nearest(coord : CLLocationCoordinate2D, count : Int) -> [Airport] {
        return tree.nearestK(count, to: Airport.at(location: coord))
    }
    public func nearestMatching(coord : CLLocationCoordinate2D, needle: String, count : Int) -> [Airport] {
        if needle.isEmpty {
            return self.nearest(coord: coord, count: count)
        }
        return tree.nearestK(count, to: Airport.at(location: coord)) { $0.matches(needle) }
    }
    public func matching(needle : String) -> [Airport] {
        var rv : [Airport] = []
        for (_,airport) in self.known {
            if airport.matches(needle) {
                rv.append(airport)
            }
        }
        return rv
    }
    
    public func airportsWithinBox(minCoord: CLLocationCoordinate2D, maxCoord: CLLocationCoordinate2D) -> [Airport] {
        var results: [Airport] = []
        let minLat = min(minCoord.latitude, maxCoord.latitude)
        let maxLat = max(minCoord.latitude, maxCoord.latitude)
        let minLon = min(minCoord.longitude, maxCoord.longitude)
        let maxLon = max(minCoord.longitude, maxCoord.longitude)
        
        for (_, airport) in known {
            if airport.latitude >= minLat && airport.latitude <= maxLat &&
               airport.longitude >= minLon && airport.longitude <= maxLon {
                results.append(airport)
            }
        }
        
        return results
    }
    
    public func frenchPPL() -> [Airport] {
        var rv : [Airport] = []
        let sql = "SELECT ident FROM frppf"
        if let res = db.executeQuery(sql, withArgumentsIn: []){
            while( res.next() ){
                if let ident = res.string(forColumn: "ident"),
                   let airport = self.airport(icao: ident, ensureRunway: false) {
                    rv.append(airport)
                }
            }
        }
        var ppf : [Airport] = []
        for airport in rv {
            var one = airport
            ppf.append(one.addRunways(db: self.db))
        }
        return ppf
    }
    
    // MARK: - Enhanced Query Methods
    
    /// Find airports with specific approach types within distance
    public func airportsWithApproach(_ approachType: Procedure.ApproachType, 
                                   near coord: CLLocationCoordinate2D, 
                                   within distanceKm: Double, 
                                   limit: Int = 10) -> [Airport] {
        let nearbyAirports = tree.nearestK(limit * 3, to: Airport.at(location: coord))
        
        var results: [Airport] = []
        for var airport in nearbyAirports {
            let distance = airport.distance(to: coord) / 1000 // Convert to km
            if distance <= distanceKm {
                // Load procedures to check
                _ = airport.addProcedures(db: self.db)
                if airport.approaches.contains(where: { $0.approachType == approachType }) {
                    results.append(airport)
                }
            }
            if results.count >= limit {
                break
            }
        }
        
        return results
    }
    
    /// Find airports with precision approaches within distance
    public func airportsWithPrecisionApproaches(near coord: CLLocationCoordinate2D, 
                                               within distanceKm: Double, 
                                               limit: Int = 10) -> [Airport] {
        let nearbyAirports = tree.nearestK(limit * 3, to: Airport.at(location: coord))
        
        var results: [Airport] = []
        for var airport in nearbyAirports {
            let distance = airport.distance(to: coord) / 1000 // Convert to km
            if distance <= distanceKm {
                // Load procedures to check
                _ = airport.addProcedures(db: self.db)
                if airport.approaches.contains(where: { $0.precisionCategory == .precision }) {
                    results.append(airport)
                }
            }
            if results.count >= limit {
                break
            }
        }
        
        return results
    }
    
    /// Get airports with AIP data for a specific field
    public func airportsWithAIPField(_ fieldName: String, useStandardized: Bool = true) -> [Airport] {
        var results: [Airport] = []
        
        for (_, var airport) in known {
            _ = airport.addAIPEntries(db: self.db)
            if airport.aipEntry(for: fieldName, useStandardized: useStandardized) != nil {
                results.append(airport)
            }
        }
        
        return results
    }
    
    // MARK: - Border Crossing / Point of Entry Methods
    
    /// Load the set of ICAO codes that are border crossing points (cached after first load)
    private func loadBorderCrossingICAOs() {
        if borderCrossingICAOs != nil {
            return  // Already loaded
        }
        
        var icaoSet = Set<String>()
        let query = "SELECT DISTINCT icao_code, matched_airport_icao FROM border_crossing_points"
        
        if let res = db.executeQuery(query, withArgumentsIn: []) {
            while res.next() {
                if let icao = res.string(forColumn: "icao_code"), !icao.isEmpty {
                    icaoSet.insert(icao)
                }
                if let matchedIcao = res.string(forColumn: "matched_airport_icao"), !matchedIcao.isEmpty {
                    icaoSet.insert(matchedIcao)
                }
            }
        }
        
        borderCrossingICAOs = icaoSet
    }
    
    /// Check if an ICAO code is a border crossing point
    private func isBorderCrossingICAO(_ icao: String) -> Bool {
        loadBorderCrossingICAOs()
        return borderCrossingICAOs?.contains(icao) ?? false
    }
    
    /// Get all airports that are border crossing points
    public func airportsWithBorderCrossing() -> [Airport] {
        loadBorderCrossingICAOs()
        var results: [Airport] = []
        
        for icao in borderCrossingICAOs ?? [] {
            if let airport = known[icao] {
                results.append(airport)
            }
        }
        
        return results
    }
    
    /// Find nearest airports with border crossing facilities within a specified distance
    public func airportsWithBorderCrossing(near coord: CLLocationCoordinate2D, 
                                           within distanceKm: Double, 
                                           limit: Int = 10) -> [Airport] {
        let nearbyAirports = tree.nearestK(limit * 3, to: Airport.at(location: coord))
        
        var results: [Airport] = []
        for airport in nearbyAirports {
            let distance = airport.distance(to: coord) / 1000 // Convert to km
            if distance <= distanceKm && isBorderCrossingICAO(airport.icao) {
                results.append(airport)
            }
            if results.count >= limit {
                break
            }
        }
        
        return results
    }
    
    /// Find airports near a route defined by airport ICAO codes
    public func airportsNearRoute(_ routeAirports: [String], within distanceNm: Double) -> [Airport] {
        // Convert route airports to coordinates
        let routePoints = routeAirports.compactMap { icao -> CLLocationCoordinate2D? in
            guard let airport = airport(icao: icao, ensureRunway: false) else { return nil }
            return airport.coord
        }
        
        guard !routePoints.isEmpty else { return [] }
        
        var results: [(airport: Airport, distance: Double)] = []
        
        // Find all airports near the route
        for (_, airport) in known {
            // Calculate minimum distance to route
            var minDistance = Double.infinity
            
            if routePoints.count == 1 {
                // Single point, calculate direct distance
                minDistance = airport.distance(to: routePoints[0]) / 1852 // Convert to nautical miles
            } else {
                // Calculate distance to nearest segment
                for i in 0..<(routePoints.count - 1) {
                    let segmentStart = routePoints[i]
                    let segmentEnd = routePoints[i + 1]
                    
                    // Calculate perpendicular distance
                    let dist = perpendicularDistance(from: airport.coord, 
                                                      to: segmentStart, 
                                                      and: segmentEnd)
                    minDistance = min(minDistance, dist)
                }
            }
            
            if minDistance <= distanceNm {
                results.append((airport: airport, distance: minDistance))
            }
        }
        
        // Sort by distance and return just airports
        return results.sorted { $0.distance < $1.distance }.map { $0.airport }
    }
    
    // Helper method to calculate perpendicular distance from a point to a line segment
    private func perpendicularDistance(from point: CLLocationCoordinate2D, 
                                       to start: CLLocationCoordinate2D, 
                                       and end: CLLocationCoordinate2D) -> Double {
        let A = point.latitude - start.latitude
        let B = point.longitude - start.longitude
        let C = end.latitude - start.latitude
        let D = end.longitude - start.longitude
        
        let dot = A * C + B * D
        let lenSq = C * C + D * D
        let param = lenSq > 0 ? dot / lenSq : -1
        
        var xx: Double
        var yy: Double
        
        if param < 0 {
            xx = start.latitude
            yy = start.longitude
        } else if param > 1 {
            xx = end.latitude
            yy = end.longitude
        } else {
            xx = start.latitude + param * C
            yy = start.longitude + param * D
        }
        
        // Calculate distance in nautical miles using MapKit
        let distanceMeters = MKMapPoint(CLLocationCoordinate2D(latitude: point.latitude, longitude: point.longitude))
            .distance(to: MKMapPoint(CLLocationCoordinate2D(latitude: xx, longitude: yy)))
        return distanceMeters / 1852.0
    }
}

// MARK: - Airport Array Filtering Extensions

extension Array where Element == Airport {
    
    /// Filter airports to only those that are border crossing points
    /// Note: Requires checking against the database's border_crossing_points table
    public func borderCrossingOnly(db: FMDatabase) -> [Airport] {
        return self.filter { airport in
            let query = "SELECT COUNT(*) as count FROM border_crossing_points WHERE matched_airport_icao = ? OR icao_code = ?"
            if let result = db.executeQuery(query, withArgumentsIn: [airport.icao, airport.icao]) {
                if result.next() {
                    return result.int(forColumn: "count") > 0
                }
            }
            return false
        }
    }
    
    /// Filter airports to only those with runways of a certain minimum length
    public func withRunwayLength(minimumFeet: Int) -> [Airport] {
        return self.filter { airport in
            airport.runways.contains { $0.length_ft >= minimumFeet }
        }
    }
    
    /// Filter airports to only those with runways between min and max length
    public func withRunwayLength(minimumFeet: Int, maximumFeet: Int) -> [Airport] {
        return self.filter { airport in
            airport.runways.contains { $0.length_ft >= minimumFeet && $0.length_ft <= maximumFeet }
        }
    }
    
    /// Filter airports to only those that have procedures
    public func withProcedures() -> [Airport] {
        return self.filter { !$0.procedures.isEmpty }
    }
    
    /// Filter airports to only those that have approach procedures
    public func withApproaches() -> [Airport] {
        return self.filter { !$0.approaches.isEmpty }
    }
    
    /// Filter airports to only those with precision approaches
    public func withPrecisionApproaches() -> [Airport] {
        return self.filter { airport in
            airport.approaches.contains { $0.precisionCategory == .precision }
        }
    }
    
    /// Filter airports to only those with hard surface runways
    public func withHardRunways() -> [Airport] {
        return self.filter { airport in
            airport.runways.contains { $0.isHardSurface }
        }
    }
    
    /// Filter airports to only those with lighted runways
    public func withLightedRunways() -> [Airport] {
        return self.filter { airport in
            airport.runways.contains { $0.lighted == true }
        }
    }
    
    /// Filter airports to only those in a specific country
    public func inCountry(_ countryCode: String) -> [Airport] {
        return self.filter { $0.country == countryCode }
    }
    
    /// Filter airports to only those matching a search term (name or ICAO)
    public func matching(_ searchTerm: String) -> [Airport] {
        let lowerSearchTerm = searchTerm.lowercased()
        return self.filter { airport in
            airport.name.lowercased().contains(lowerSearchTerm) ||
            airport.icao.lowercased().contains(lowerSearchTerm)
        }
    }
}
