//
//  Airport.swift
//  MentalCrosswind
//
//  Created by Brice Rosenzweig on 04/03/2022.
//

import Foundation
import CoreLocation
import Geomagnetism
import OSLog
import FMDB
import RZUtilsSwift


public struct Airport : Codable {
        
    enum AirportError :  Error {
        case unknownIdentifier
    }
    
    enum Category: String, Codable {
            case city, name, country, elevation_ft, icao, latitude, longitude, reporting
        }
    
    public enum AirportType : String, Codable {
        case none
        case balloonport
        case closed
        case large_airport
        case medium_airport
        case seaplane_base
        case small_airport
    }
    public enum Continent : String, Codable {
        case none
        case AF
        case AN
        case AS
        case EU
        case NA
        case OC
        case SA
    }
    
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
    
    
    public let name : String
    public let city : String
    public let country : String
    public let elevation_ft : Int
    public let icao : String
    public let type : AirportType
    public let continent : Continent
    let latitude : Double
    let longitude : Double
    
    public var runways : [Runway]
    public var procedures : [Procedure]
    public var aipEntries : [AIPEntry]
    
    public var coord : CLLocationCoordinate2D { return CLLocationCoordinate2D(latitude: latitude, longitude: longitude) }
    
    private var declination : Double { return Geomagnetism(longitude: longitude, latitude: latitude).declination }
    
    func magneticHeading(from : Heading) -> Heading {
        return Heading(heading: (from.heading - declination) )
    }
    func trueHeading(from : Heading) -> Heading {
        return Heading(heading: (from.heading + declination) )
    }
    
    public func contains( _ searchText : String) -> Bool {
        let lowered = searchText.lowercased()
        if icao.lowercased().contains(lowered) || name.lowercased().contains(lowered) || country.lowercased().contains(lowered) || city.lowercased().contains(lowered) {
            return true
        }
        return false
    }
    func matches(_ needle : String) -> Bool {
        if self.icao.range(of: needle, options: [.caseInsensitive,.diacriticInsensitive]) != nil ||
            self.name.range(of: needle, options: [.caseInsensitive,.diacriticInsensitive]) != nil {
            return true
        }
        return false
    }
    
    public init?(res : FMResultSet, db : FMDatabase? = nil) {
        guard let ident = res.string(forColumn: "icao_code")
        else { return nil }
        
        self.icao = ident
        self.name = res.string(forColumn: "name") ?? ident
        self.latitude = res.double(forColumn: "latitude_deg")
        self.longitude = res.double(forColumn: "longitude_deg")
        self.elevation_ft = Int(res.int(forColumn: "elevation_ft"))
        self.continent = Continent(rawValue: res.string(forColumn: "continent") ?? "") ?? .none
        self.type = AirportType(rawValue: res.string(forColumn:"type") ?? "") ?? .none
        self.country = res.string(forColumn: "iso_country") ?? ""
        //iso_region TEXT,
        self.city = res.string(forColumn: "municipality") ?? ""
        
        if let db = db {
            self.runways = Self.runways(for: self.icao, db: db)
        }else{
            self.runways = []
        }
        
        // Initialize empty arrays - will be loaded lazily
        self.procedures = []
        self.aipEntries = []
    }
   
    private static func runways(for icao : String, db : FMDatabase) -> [Runway] {
        let run = db.executeQuery("SELECT * FROM runways WHERE airport_icao = ?", withArgumentsIn: [icao])
        var runways : [Runway] = []
        if let run = run {
            while run.next() {
                runways.append(Runway(res: run))
            }
        }
        return runways
    }
    
    private static func procedures(for icao: String, db: FMDatabase) -> [Procedure] {
        let res = db.executeQuery("SELECT * FROM procedures WHERE airport_icao = ?", withArgumentsIn: [icao])
        var procedures: [Procedure] = []
        if let res = res {
            while res.next() {
                procedures.append(Procedure(res: res))
            }
        }
        return procedures
    }
    
    private static func aipEntries(for icao: String, db: FMDatabase) -> [AIPEntry] {
        let res = db.executeQuery("SELECT * FROM aip_entries WHERE airport_icao = ?", withArgumentsIn: [icao])
        var entries: [AIPEntry] = []
        if let res = res {
            while res.next() {
                entries.append(AIPEntry(res: res))
            }
        }
        return entries
    }
    
    public mutating func addRunways(db : FMDatabase) -> Airport {
        self.runways = Self.runways(for: self.icao, db: db)
        return self
    }
    
    public mutating func addProcedures(db: FMDatabase) -> Airport {
        self.procedures = Self.procedures(for: self.icao, db: db)
        return self
    }
    
    public mutating func addAIPEntries(db: FMDatabase) -> Airport {
        self.aipEntries = Self.aipEntries(for: self.icao, db: db)
        return self
    }
    
    public mutating func addExtendedData(db: FMDatabase) -> Airport {
        self.runways = Self.runways(for: self.icao, db: db)
        self.procedures = Self.procedures(for: self.icao, db: db)
        self.aipEntries = Self.aipEntries(for: self.icao, db: db)
        return self
    }
    static func at(location: CLLocationCoordinate2D) -> Airport {
        return Airport(location: location, icao: "__DUMMY__")
    }
    public init(location : CLLocationCoordinate2D, icao : String? = nil) {
        self.latitude = location.latitude
        self.longitude = location.longitude
        self.icao = icao ?? ""
        self.name = ""
        self.city = ""
        self.country = ""
        self.elevation_ft = 0
        self.runways = []
        self.procedures = []
        self.aipEntries = []
        self.continent = .none
        self.type = .none
    
    }
    public init(db : FMDatabase, ident : String) throws{
        let res = db.executeQuery("SELECT * FROM airports WHERE ident = ?", withArgumentsIn: [ident])
        if let res = res, res.next() {
            self.icao = ident
            self.type = AirportType(rawValue: res.string(forColumn:"type") ?? "") ?? .none
            self.name = res.string(forColumn: "name") ?? ident
            self.latitude = res.double(forColumn: "latitude_deg")
            self.longitude = res.double(forColumn: "longitude_deg")
            self.elevation_ft = Int(res.int(forColumn: "elevation_ft"))
            self.continent = Continent(rawValue: res.string(forColumn: "continent") ?? "") ?? .none
            self.country = res.string(forColumn: "iso_country") ?? ""
            //iso_region TEXT,
            self.city = res.string(forColumn: "municipality") ?? ""
            //scheduled_service TEXT,
            //gps_code TEXT,
            //iata_code TEXT,
            //local_code TEXT,
            //home_link TEXT,
            //wikipedia_link TEXT,
            //keywords TEXT
        }else{
            throw AirportError.unknownIdentifier
        }
        let run = db.executeQuery("SELECT * FROM runways WHERE airport_ident = ?", withArgumentsIn: [ident])
        var runways : [Runway] = []
        if let run = run {
            while run.next() {
                runways.append(Runway(res: run))
            }
        }
        self.runways = runways
        self.procedures = []
        self.aipEntries = []
    }
    
    public func bestRunway(wind : Heading) -> Heading {
        if let first = runways.first {
            var best : Runway = first
            for runway in runways {
                if runway.better(for: wind, than: best) {
                    best = runway
                }
            }
            return self.magneticHeading(from: best.bestTrueHeading(for: wind))
        }
        return wind
    }
    
    // MARK: - Procedure Convenience Methods
    
    /// Get all approach procedures
    public var approaches: [Procedure] {
        return procedures.filter { $0.isApproach }
    }
    
    /// Get all departure procedures
    public var departures: [Procedure] {
        return procedures.filter { $0.isDeparture }
    }
    
    /// Get all arrival procedures
    public var arrivals: [Procedure] {
        return procedures.filter { $0.isArrival }
    }
    
    /// Get procedures for a specific runway
    public func procedures(for runway: Runway) -> [Procedure] {
        return procedures.filter { $0.matches(runway: runway) }
    }
    
    /// Get procedures for a specific runway identifier
    public func procedures(for runwayIdent: String) -> [Procedure] {
        return procedures.filter { $0.matches(runwayIdent: runwayIdent) }
    }
    
    /// Get approaches for a specific runway
    public func approaches(for runway: Runway) -> [Procedure] {
        return approaches.filter { $0.matches(runway: runway) }
    }
    
    /// Get the most precise approach for a runway
    public func mostPreciseApproach(for runway: Runway) -> Procedure? {
        let runwayApproaches = approaches(for: runway)
        return runwayApproaches.min { $0.isMorePreciseThan($1) }
    }
    
    /// Get the most precise approach for a runway identifier
    public func mostPreciseApproach(for runwayIdent: String) -> Procedure? {
        let runwayApproaches = approaches.filter { $0.matches(runwayIdent: runwayIdent) }
        return runwayApproaches.min { $0.isMorePreciseThan($1) }
    }
    
    // MARK: - AIP Entry Convenience Methods
    
    /// Get AIP entries by section
    public func aipEntries(for section: AIPEntry.Section) -> [AIPEntry] {
        return aipEntries.filter { $0.section == section }
    }
    
    /// Get standardized AIP entries
    public var standardizedAIPEntries: [AIPEntry] {
        return aipEntries.filter { $0.isStandardized }
    }
    
    /// Get AIP entry by field name
    public func aipEntry(for fieldName: String, useStandardized: Bool = true) -> AIPEntry? {
        if useStandardized {
            // Try standardized field first
            if let entry = aipEntries.first(where: { $0.stdField == fieldName }) {
                return entry
            }
        }
        // Fall back to original field name
        return aipEntries.first { $0.field == fieldName }
    }
}

extension Airport : Hashable, Equatable,Identifiable {
    static public func ==(lhs : Airport, rhs : Airport) -> Bool {
        return lhs.icao == rhs.icao
    }
    
    public func hash(into hasher: inout Hasher) {
        hasher.combine(self.icao)
    }
    public var id: String { return self.icao }
}

extension Airport : CustomStringConvertible {
    public var description : String { return "Airport(\(icao))" }
}

