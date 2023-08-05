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
                case length_ft, width_ft, surface, bearing1, bearing2, ident1, ident2
            }
        var length_ft : Int
        var width_ft : Int
        var surface : String
        private var bearing1 : Double
        private var bearing2 : Double
        var ident1 : String
        var ident2 : String
        
        var trueHeading1 : Heading { return Heading(heading: bearing1 ) }
        var trueHeading2 : Heading { return Heading(heading: bearing2 ) }
        
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
            //lighted INT,
            //closed INT,
            self.ident1 = res.string(forColumn: "le_ident") ?? ""
            //le_latitude_deg REAL,
            //le_longitude_deg REAL,
            //le_elevation_ft REAL,
            self.bearing1 = res.double(forColumn: "le_heading_degT")
            //le_displaced_threshold_ft REAL,
            self.ident2 = res.string(forColumn: "he_ident") ?? ""
            //he_latitude_deg REAL,
            //he_longitude_deg REAL,
            //he_elevation_ft REAL,
            self.bearing2 = res.double(forColumn: "he_heading_degT")
            //he_displaced_threshold_ft REAL
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
        guard let ident = res.string(forColumn: "ident")
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
    }
   
    private static func runways(for icao : String, db : FMDatabase) -> [Runway] {
        let run = db.executeQuery("SELECT * FROM runways WHERE airport_ident = ?", withArgumentsIn: [icao])
        var runways : [Runway] = []
        if let run = run {
            while run.next() {
                runways.append(Runway(res: run))
            }
        }
        return runways
    }
    
    public mutating func addRunways(db : FMDatabase) {
        self.runways = Self.runways(for: self.icao, db: db)
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

