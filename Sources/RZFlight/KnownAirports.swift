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
}
