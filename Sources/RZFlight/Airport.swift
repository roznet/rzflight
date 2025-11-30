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
    public let isoRegion : String?
    public let scheduledService : String?
    public let gpsCode : String?
    public let iataCode : String?
    public let localCode : String?
    public let homeLink : String?
    public let wikipediaLink : String?
    public let keywords : String?
    public let sources : [String]
    public let createdAt : Date?
    public let updatedAt : Date?
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
        self.isoRegion = res.string(forColumn: "iso_region")
        self.city = res.string(forColumn: "municipality") ?? ""
        self.scheduledService = res.string(forColumn: "scheduled_service")
        self.gpsCode = res.string(forColumn: "gps_code")
        self.iataCode = res.string(forColumn: "iata_code")
        self.localCode = res.string(forColumn: "local_code")
        self.homeLink = res.string(forColumn: "home_link")
        self.wikipediaLink = res.string(forColumn: "wikipedia_link")
        self.keywords = res.string(forColumn: "keywords")
        let sourcesStr = res.string(forColumn: "sources") ?? ""
        self.sources = sourcesStr.isEmpty ? [] : sourcesStr.split(separator: ",").map { String($0) }
        
        if let createdRaw = res.string(forColumn: "created_at") {
            self.createdAt = ISO8601DateFormatter().date(from: createdRaw)
        } else { self.createdAt = nil }
        if let updatedRaw = res.string(forColumn: "updated_at") {
            self.updatedAt = ISO8601DateFormatter().date(from: updatedRaw)
        } else { self.updatedAt = nil }
        
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
        self.isoRegion = nil
        self.scheduledService = nil
        self.gpsCode = nil
        self.iataCode = nil
        self.localCode = nil
        self.homeLink = nil
        self.wikipediaLink = nil
        self.keywords = nil
        self.sources = []
        self.createdAt = nil
        self.updatedAt = nil
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
            self.isoRegion = res.string(forColumn: "iso_region")
            self.city = res.string(forColumn: "municipality") ?? ""
            self.scheduledService = res.string(forColumn: "scheduled_service")
            self.gpsCode = res.string(forColumn: "gps_code")
            self.iataCode = res.string(forColumn: "iata_code")
            self.localCode = res.string(forColumn: "local_code")
            self.homeLink = res.string(forColumn: "home_link")
            self.wikipediaLink = res.string(forColumn: "wikipedia_link")
            self.keywords = res.string(forColumn: "keywords")
            
            // Parse sources
            let sourcesStr = res.string(forColumn: "sources") ?? ""
            self.sources = sourcesStr.isEmpty ? [] : sourcesStr.split(separator: ",").map { String($0) }
            
            // Parse dates
            if let createdRaw = res.string(forColumn: "created_at") {
                self.createdAt = ISO8601DateFormatter().date(from: createdRaw)
            } else { self.createdAt = nil }
            
            if let updatedRaw = res.string(forColumn: "updated_at") {
                self.updatedAt = ISO8601DateFormatter().date(from: updatedRaw)
            } else { self.updatedAt = nil }
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
    
    enum CodingKeys: String, CodingKey {
        case name
        case city
        case municipality  // API format - for decoding only
        case country
        case iso_country  // API format - for decoding only
        case isoRegion = "iso_region"  // API format (snake_case)
        case scheduledService = "scheduled_service"  // API format (snake_case)
        case gpsCode = "gps_code"  // API format (snake_case)
        case iataCode = "iata_code"  // API format (snake_case)
        case localCode = "local_code"  // API format (snake_case)
        case homeLink = "home_link"  // API format (snake_case)
        case wikipediaLink = "wikipedia_link"  // API format (snake_case)
        case keywords
        case sources
        case createdAt = "created_at"  // API format (snake_case)
        case updatedAt = "updated_at"  // API format (snake_case)
        case elevation_ft
        case icao
        case ident  // API format - for decoding only
        case type
        case continent
        case latitude
        case latitude_deg  // API format - for decoding only
        case longitude
        case longitude_deg  // API format - for decoding only
        case runways
        case procedures
        case aipEntries = "aip_entries"  // API format (snake_case)
    }

    public init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        
        // Helper to try multiple keys (returns first non-nil value found)
        func decodeString(keys: CodingKeys..., defaultValue: String = "") throws -> String {
            for key in keys {
                if let value = try container.decodeIfPresent(String.self, forKey: key), !value.isEmpty {
                    return value
                }
            }
            return defaultValue
        }
        
        func decodeDouble(keys: CodingKeys..., defaultValue: Double = 0.0) throws -> Double {
            for key in keys {
                if let value = try container.decodeIfPresent(Double.self, forKey: key) {
                    return value
                }
            }
            return defaultValue
        }

        // Basic strings with defaults
        self.name = try container.decodeIfPresent(String.self, forKey: .name) ?? ""
        
        // Support both "city" and "municipality" (API format)
        self.city = try decodeString(keys: .city, .municipality)
        
        // Support both "country" and "iso_country" (API format)
        self.country = try decodeString(keys: .country, .iso_country)

        // Optional strings - support both camelCase and snake_case
        self.isoRegion = try container.decodeIfPresent(String.self, forKey: .isoRegion)
        self.scheduledService = try container.decodeIfPresent(String.self, forKey: .scheduledService)
        self.gpsCode = try container.decodeIfPresent(String.self, forKey: .gpsCode)
        self.iataCode = try container.decodeIfPresent(String.self, forKey: .iataCode)
        self.localCode = try container.decodeIfPresent(String.self, forKey: .localCode)
        self.homeLink = try container.decodeIfPresent(String.self, forKey: .homeLink)
        self.wikipediaLink = try container.decodeIfPresent(String.self, forKey: .wikipediaLink)
        self.keywords = try container.decodeIfPresent(String.self, forKey: .keywords)

        // Arrays with defaults
        self.sources = try container.decodeIfPresent([String].self, forKey: .sources) ?? []

        // Dates (decode directly if encoded as Date, otherwise nil)
        self.createdAt = try container.decodeIfPresent(Date.self, forKey: .createdAt)
        self.updatedAt = try container.decodeIfPresent(Date.self, forKey: .updatedAt)

        // Numerics with defaults
        self.elevation_ft = try container.decodeIfPresent(Int.self, forKey: .elevation_ft) ?? 0

        // Identifiers - support both "icao" and "ident" (API format)
        self.icao = try decodeString(keys: .icao, .ident)

        // Enums with defaults
        self.type = try container.decodeIfPresent(AirportType.self, forKey: .type) ?? .none
        self.continent = try container.decodeIfPresent(Continent.self, forKey: .continent) ?? .none

        // Coordinates - support both "latitude"/"longitude" and "latitude_deg"/"longitude_deg" (API format)
        self.latitude = try decodeDouble(keys: .latitude, .latitude_deg)
        self.longitude = try decodeDouble(keys: .longitude, .longitude_deg)

        // Collections with defaults
        self.runways = try container.decodeIfPresent([Runway].self, forKey: .runways) ?? []
        self.procedures = try container.decodeIfPresent([Procedure].self, forKey: .procedures) ?? []
        self.aipEntries = try container.decodeIfPresent([AIPEntry].self, forKey: .aipEntries) ?? []
    }
    
    public func encode(to encoder: Encoder) throws {
        var container = encoder.container(keyedBy: CodingKeys.self)
        
        try container.encode(name, forKey: .name)
        try container.encode(city, forKey: .city)
        try container.encode(country, forKey: .country)
        try container.encodeIfPresent(isoRegion, forKey: .isoRegion)
        try container.encodeIfPresent(scheduledService, forKey: .scheduledService)
        try container.encodeIfPresent(gpsCode, forKey: .gpsCode)
        try container.encodeIfPresent(iataCode, forKey: .iataCode)
        try container.encodeIfPresent(localCode, forKey: .localCode)
        try container.encodeIfPresent(homeLink, forKey: .homeLink)
        try container.encodeIfPresent(wikipediaLink, forKey: .wikipediaLink)
        try container.encodeIfPresent(keywords, forKey: .keywords)
        try container.encode(sources, forKey: .sources)
        try container.encodeIfPresent(createdAt, forKey: .createdAt)
        try container.encodeIfPresent(updatedAt, forKey: .updatedAt)
        try container.encode(elevation_ft, forKey: .elevation_ft)
        try container.encode(icao, forKey: .icao)
        try container.encode(type, forKey: .type)
        try container.encode(continent, forKey: .continent)
        try container.encode(latitude, forKey: .latitude)
        try container.encode(longitude, forKey: .longitude)
        try container.encode(runways, forKey: .runways)
        try container.encode(procedures, forKey: .procedures)
        try container.encode(aipEntries, forKey: .aipEntries)
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
    
    // MARK: - Border Crossing / Point of Entry
    
    /// Check if this airport is a border crossing point (requires database context)
    public func isBorderCrossing(db: FMDatabase) -> Bool {
        let query = "SELECT COUNT(*) as count FROM border_crossing_points WHERE matched_airport_icao = ? OR icao_code = ?"
        if let result = db.executeQuery(query, withArgumentsIn: [self.icao, self.icao]) {
            if result.next() {
                return result.int(forColumn: "count") > 0
            }
        }
        return false
    }
    
    /// Check if this airport can be used for customs/border crossing (requires database context)
    public func hasCustoms(db: FMDatabase) -> Bool {
        return isBorderCrossing(db: db)
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

