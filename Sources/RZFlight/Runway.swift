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
    public var length_ft : Int
    public var width_ft : Int
    public var surface : String
    public var lighted: Bool
    public var closed: Bool
    
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
    
    /// Check if runway has hard surface (asphalt, concrete, etc.)
    public var isHardSurface: Bool {
        let hardSurfaces = ["asphalt", "concrete", "paved", "hard"]
        return hardSurfaces.contains { surface.lowercased().contains($0) }
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
        self.length_ft = Int(res.int(forColumn: "length_ft"))
        self.width_ft = Int(res.int(forColumn: "width_ft"))
        self.surface = res.string(forColumn: "surface") ?? ""
        self.lighted = res.bool(forColumn: "lighted")
        self.closed = res.bool(forColumn: "closed")
        self.le = RunwayEnd.load(from: res, prefix: "le")
        self.he = RunwayEnd.load(from: res, prefix: "he")
    }
    
    enum CodingKeys: String, CodingKey {
        case length_ft
        case width_ft
        case surface
        case lighted
        case closed
        // RunwayEnd fields with prefixes
        case le_ident
        case le_latitude_deg
        case le_longitude_deg
        case le_elevation_ft
        case le_heading_degT
        case le_displaced_threshold_ft
        case he_ident
        case he_latitude_deg
        case he_longitude_deg
        case he_elevation_ft
        case he_heading_degT
        case he_displaced_threshold_ft
    }
    
    public init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        
        self.length_ft = try container.decodeIfPresent(Int.self, forKey: .length_ft) ?? 0
        self.width_ft = try container.decodeIfPresent(Int.self, forKey: .width_ft) ?? 0
        self.surface = try container.decodeIfPresent(String.self, forKey: .surface) ?? ""
        self.lighted = try container.decodeIfPresent(Bool.self, forKey: .lighted) ?? false
        self.closed = try container.decodeIfPresent(Bool.self, forKey: .closed) ?? false
        
        // Decode LE (low end) runway end
        let leIdent = try container.decodeIfPresent(String.self, forKey: .le_ident) ?? ""
        let leLat = try container.decodeIfPresent(Double.self, forKey: .le_latitude_deg)
        let leLon = try container.decodeIfPresent(Double.self, forKey: .le_longitude_deg)
        let leElev = try container.decodeIfPresent(Double.self, forKey: .le_elevation_ft)
        let leHeading = try container.decodeIfPresent(Double.self, forKey: .le_heading_degT) ?? 0.0
        let leDisplaced = try container.decodeIfPresent(Double.self, forKey: .le_displaced_threshold_ft)
        self.le = RunwayEnd(ident: leIdent, latitude: leLat, longitude: leLon, 
                           elevationFt: leElev, headingTrue: leHeading, 
                           displacedThresholdFt: leDisplaced)
        
        // Decode HE (high end) runway end
        let heIdent = try container.decodeIfPresent(String.self, forKey: .he_ident) ?? ""
        let heLat = try container.decodeIfPresent(Double.self, forKey: .he_latitude_deg)
        let heLon = try container.decodeIfPresent(Double.self, forKey: .he_longitude_deg)
        let heElev = try container.decodeIfPresent(Double.self, forKey: .he_elevation_ft)
        let heHeading = try container.decodeIfPresent(Double.self, forKey: .he_heading_degT) ?? 0.0
        let heDisplaced = try container.decodeIfPresent(Double.self, forKey: .he_displaced_threshold_ft)
        self.he = RunwayEnd(ident: heIdent, latitude: heLat, longitude: heLon, 
                           elevationFt: heElev, headingTrue: heHeading, 
                           displacedThresholdFt: heDisplaced)
    }
    
    public func encode(to encoder: Encoder) throws {
        var container = encoder.container(keyedBy: CodingKeys.self)
        
        try container.encode(length_ft, forKey: .length_ft)
        try container.encode(width_ft, forKey: .width_ft)
        try container.encode(surface, forKey: .surface)
        try container.encode(lighted, forKey: .lighted)
        try container.encode(closed, forKey: .closed)
        
        // Encode LE runway end
        try container.encode(le.ident, forKey: .le_ident)
        try container.encodeIfPresent(le.latitude, forKey: .le_latitude_deg)
        try container.encodeIfPresent(le.longitude, forKey: .le_longitude_deg)
        try container.encodeIfPresent(le.elevationFt, forKey: .le_elevation_ft)
        try container.encode(le.headingTrue, forKey: .le_heading_degT)
        try container.encodeIfPresent(le.displacedThresholdFt, forKey: .le_displaced_threshold_ft)
        
        // Encode HE runway end
        try container.encode(he.ident, forKey: .he_ident)
        try container.encodeIfPresent(he.latitude, forKey: .he_latitude_deg)
        try container.encodeIfPresent(he.longitude, forKey: .he_longitude_deg)
        try container.encodeIfPresent(he.elevationFt, forKey: .he_elevation_ft)
        try container.encode(he.headingTrue, forKey: .he_heading_degT)
        try container.encodeIfPresent(he.displacedThresholdFt, forKey: .he_displaced_threshold_ft)
    }
}

