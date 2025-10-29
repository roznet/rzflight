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
        if self.runways.isEmpty {
            self.runways = Self.runways(for: self.icao, db: db)
        }
        return self
    }
    
    public mutating func addProcedures(db: FMDatabase) -> Airport {
        if self.procedures.isEmpty {
            self.procedures = Self.procedures(for: self.icao, db: db)
        }
        return self
    }
    
    public mutating func addAIPEntries(db: FMDatabase) -> Airport {
        if self.aipEntries.isEmpty {
            self.aipEntries = Self.aipEntries(for: self.icao, db: db)
        }
        return self
    }
    
    public mutating func addExtendedData(db: FMDatabase) -> Airport {
        if self.runways.isEmpty || self.procedures.isEmpty || self.aipEntries.isEmpty {
            self.runways = Self.runways(for: self.icao, db: db)
            self.procedures = Self.procedures(for: self.icao, db: db)
            self.aipEntries = Self.aipEntries(for: self.icao, db: db)
        }
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
            if let entry = aipEntries.first(where: { $0.standardField?.name == fieldName }) {
                return entry
            }
        }
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

