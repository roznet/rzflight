//
//  Runway.swift
//  RZFlight
//
//  Created by Brice Rosenzweig on 29/10/2025.
//

import CoreLocation
import FMDB

public struct Runway : Codable{
    enum Category: String, Decodable {
            case length_ft, width_ft, surface, bearing1, bearing2, ident1, ident2, lighted, closed,
                 le_latitude_deg, le_longitude_deg, le_elevation_ft, le_displaced_threshold_ft,
                 he_latitude_deg, he_longitude_deg, he_elevation_ft, he_displaced_threshold_ft
        }
    var length_ft : Int
    var width_ft : Int
    var surface : String
    private var bearing1 : Double
    private var bearing2 : Double
    var ident1 : String
    var ident2 : String
    
    // Enhanced fields from Python model
    var lighted: Bool
    var closed: Bool
    
    // Low end (LE) enhanced information
    var leLatitude: Double?
    var leLongitude: Double?
    var leElevation: Double?
    var leDisplacedThreshold: Double?
    
    // High end (HE) enhanced information
    var heLatitude: Double?
    var heLongitude: Double?
    var heElevation: Double?
    var heDisplacedThreshold: Double?
    
    public var trueHeading1 : Heading { return Heading(heading: bearing1 ) }
    public var trueHeading2 : Heading { return Heading(heading: bearing2 ) }
    
    /// Check if runway has coordinates for both ends
    public var hasCoordinates: Bool {
        return leLatitude != nil && leLongitude != nil &&
               heLatitude != nil && heLongitude != nil
    }
    
    /// Get coordinate for low end
    public var leCoordinate: CLLocationCoordinate2D? {
        guard let lat = leLatitude, let lon = leLongitude else { return nil }
        return CLLocationCoordinate2D(latitude: lat, longitude: lon)
    }
    
    /// Get coordinate for high end
    public var heCoordinate: CLLocationCoordinate2D? {
        guard let lat = heLatitude, let lon = heLongitude else { return nil }
        return CLLocationCoordinate2D(latitude: lat, longitude: lon)
    }
    
    func bestTrueHeading(for wind : Heading) -> Heading {
        return trueHeading1.directDirection(to: wind) == .ahead ? trueHeading1 : trueHeading2
    }
    
    func better(for wind : Heading, than other : Runway) -> Bool{
        let thisComponent = self.bestTrueHeading(for: wind).headWindComponent(with: wind)
        let otherComponent = other.bestTrueHeading(for: wind).headWindComponent(with: wind)
        
        return thisComponent.percent > otherComponent.percent
    }
    
    init(res : FMResultSet){
        //id INT,
        //airport_ref INT,
        //airport_ident TEXT,
        self.length_ft = Int(res.int(forColumn: "length_ft"))
        self.width_ft = Int(res.int(forColumn: "width_ft"))
        self.surface = res.string(forColumn: "surface") ?? ""
        
        // Enhanced fields
        self.lighted = res.bool(forColumn: "lighted")
        self.closed = res.bool(forColumn: "closed")
        
        // Low end (LE) information
        self.ident1 = res.string(forColumn: "le_ident") ?? ""
        self.leLatitude = res.columnIsNull("le_latitude_deg") ? nil : res.double(forColumn: "le_latitude_deg")
        self.leLongitude = res.columnIsNull("le_longitude_deg") ? nil : res.double(forColumn: "le_longitude_deg")
        self.leElevation = res.columnIsNull("le_elevation_ft") ? nil : res.double(forColumn: "le_elevation_ft")
        self.bearing1 = res.double(forColumn: "le_heading_degT")
        self.leDisplacedThreshold = res.columnIsNull("le_displaced_threshold_ft") ? nil : res.double(forColumn: "le_displaced_threshold_ft")
        
        // High end (HE) information
        self.ident2 = res.string(forColumn: "he_ident") ?? ""
        self.heLatitude = res.columnIsNull("he_latitude_deg") ? nil : res.double(forColumn: "he_latitude_deg")
        self.heLongitude = res.columnIsNull("he_longitude_deg") ? nil : res.double(forColumn: "he_longitude_deg")
        self.heElevation = res.columnIsNull("he_elevation_ft") ? nil : res.double(forColumn: "he_elevation_ft")
        self.bearing2 = res.double(forColumn: "he_heading_degT")
        self.heDisplacedThreshold = res.columnIsNull("he_displaced_threshold_ft") ? nil : res.double(forColumn: "he_displaced_threshold_ft")
    }
}

