//
//  Runway.swift
//  RZFlight
//
//  Created by Brice Rosenzweig on 29/10/2025.
//

import CoreLocation
import FMDB

public struct Runway : Codable{
    public struct RunwayEnd: Codable {
        public let ident: String
        public let latitude: Double?
        public let longitude: Double?
        public let elevationFt: Double?
        public let headingTrue: Double
        public let displacedThresholdFt: Double?
        
        public var coordinate: CLLocationCoordinate2D? {
            guard let lat = latitude, let lon = longitude else { return nil }
            return CLLocationCoordinate2D(latitude: lat, longitude: lon)
        }
        
        static func load(from res: FMResultSet, prefix: String) -> RunwayEnd {
            let ident = res.string(forColumn: "\(prefix)_ident") ?? ""
            let lat = res.columnIsNull("\(prefix)_latitude_deg") ? nil : res.double(forColumn: "\(prefix)_latitude_deg")
            let lon = res.columnIsNull("\(prefix)_longitude_deg") ? nil : res.double(forColumn: "\(prefix)_longitude_deg")
            let elev = res.columnIsNull("\(prefix)_elevation_ft") ? nil : res.double(forColumn: "\(prefix)_elevation_ft")
            let heading = res.double(forColumn: "\(prefix)_heading_degT")
            let displaced = res.columnIsNull("\(prefix)_displaced_threshold_ft") ? nil : res.double(forColumn: "\(prefix)_displaced_threshold_ft")
            return RunwayEnd(ident: ident, latitude: lat, longitude: lon, elevationFt: elev, headingTrue: heading, displacedThresholdFt: displaced)
        }
    }
    
    enum Category: String, Decodable {
            case length_ft, width_ft, surface, lighted, closed,
                 le_latitude_deg, le_longitude_deg, le_elevation_ft, le_displaced_threshold_ft,
                 he_latitude_deg, he_longitude_deg, he_elevation_ft, he_displaced_threshold_ft
        }
    var length_ft : Int
    var width_ft : Int
    var surface : String
    var lighted: Bool
    var closed: Bool
    
    public var le: RunwayEnd
    public var he: RunwayEnd
    
    // Backward-compatible computed properties
    private var bearing1 : Double { return le.headingTrue }
    private var bearing2 : Double { return he.headingTrue }
    var ident1 : String { return le.ident }
    var ident2 : String { return he.ident }
    
    public var trueHeading1 : Heading { return Heading(heading: bearing1 ) }
    public var trueHeading2 : Heading { return Heading(heading: bearing2 ) }
    
    public var hasCoordinates: Bool {
        return le.latitude != nil && le.longitude != nil && he.latitude != nil && he.longitude != nil
    }
    
    public var leCoordinate: CLLocationCoordinate2D? { return le.coordinate }
    public var heCoordinate: CLLocationCoordinate2D? { return he.coordinate }
    
    func bestTrueHeading(for wind : Heading) -> Heading {
        return trueHeading1.directDirection(to: wind) == .ahead ? trueHeading1 : trueHeading2
    }
    
    func better(for wind : Heading, than other : Runway) -> Bool{
        let thisComponent = self.bestTrueHeading(for: wind).headWindComponent(with: wind)
        let otherComponent = other.bestTrueHeading(for: wind).headWindComponent(with: wind)
        
        return thisComponent.percent > otherComponent.percent
    }
    
    init(res : FMResultSet){
        self.length_ft = Int(res.int(forColumn: "length_ft"))
        self.width_ft = Int(res.int(forColumn: "width_ft"))
        self.surface = res.string(forColumn: "surface") ?? ""
        self.lighted = res.bool(forColumn: "lighted")
        self.closed = res.bool(forColumn: "closed")
        self.le = RunwayEnd.load(from: res, prefix: "le")
        self.he = RunwayEnd.load(from: res, prefix: "he")
    }
}

