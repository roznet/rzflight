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


public struct Airport : Decodable {
        
    enum AirportError :  Error {
        case unknownIdentifier
    }
    
    enum Category: String, Decodable {
            case city, name, country, elevation_ft, icao, latitude, longitude, reporting
        }
    public struct Runway : Decodable{
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
    
    struct Near : Decodable{
        enum Category: String, Decodable {
                case station
            }

        var station : Airport
    }
    
    public var name : String
    public var city : String
    public var country : String
    public var elevation_ft : Int
    public var icao : String
    var latitude : Double
    var longitude : Double
    public var reporting : Bool
    
    public var runways : [Runway]
    
    public var coord : CLLocationCoordinate2D { return CLLocationCoordinate2D(latitude: latitude, longitude: longitude) }
    
    private var declination : Double { return Geomagnetism(longitude: longitude, latitude: latitude).declination }
    
    func magneticHeading(from : Heading) -> Heading {
        return Heading(heading: (from.heading - declination) )
    }
    func trueHeading(from : Heading) -> Heading {
        return Heading(heading: (from.heading + declination) )
    }
    
    public init(db : FMDatabase, ident : String) throws{
        let res = db.executeQuery("SELECT * FROM airports WHERE ident = ?", withArgumentsIn: [ident])
        if let res = res, res.next() {
            self.icao = ident
            //type TEXT,
            self.name = res.string(forColumn: "name") ?? ident
            self.latitude = res.double(forColumn: "latitude_deg")
            self.longitude = res.double(forColumn: "longitude_deg")
            self.elevation_ft = Int(res.int(forColumn: "elevation_ft"))
            //continent TEXT,
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
        self.reporting = false
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
    
    public static func at(icao: String, callback : @escaping (_ : Airport?) -> Void ) {
        if let url = URL(string: "https://avwx.rest/api/station/\(icao)"),
           let token = Secrets.shared["avwx"]{
            var request = URLRequest(url: url)
            
            request.setValue("BEARER \(token)", forHTTPHeaderField: "Authorization")
            Logger.web.info("query \(url, privacy: .public)")

            let task = URLSession.shared.dataTask(with: request) { data, response, error in
                if let error = error {
                    Logger.web.error("failed with \(error.localizedDescription, privacy: .public)")
                    callback(nil)
                    return
                }
                guard let httpResponse = response as? HTTPURLResponse,
                      (200...299).contains(httpResponse.statusCode) else {
                          callback(nil)
                          return
                      }
                if let mimeType = httpResponse.mimeType, mimeType == "application/json",
                   let data = data {
                    do {
                        let rv : Airport = try JSONDecoder().decode(Airport.self, from: data)
                        Logger.web.info("success \(url, privacy: .public)")
                        callback(rv)
                    } catch {
                        Logger.web.error("failed with \(error.localizedDescription, privacy: .public)")
                        callback(nil)
                    }
                }
            }
            task.resume()
        }
    }
    
    public static func near(coord : CLLocationCoordinate2D, count : Int = 5, reporting : Bool = true, callback : @escaping (_ : [Airport]) -> Void) {
        let reportingParameter = reporting ? "true" : "false"
        if let url = URL(string: "https://avwx.rest/api/station/near/\(coord.latitude),\(coord.longitude)?n=\(count)&reporting=\(reportingParameter)"),
           let token = Secrets.shared["avwx"]{
            var request = URLRequest(url: url)
            Logger.web.info("query \(url, privacy: .public)")
            request.setValue("BEARER \(token)", forHTTPHeaderField: "Authorization")
            let task = URLSession.shared.dataTask(with: request) { data, response, error in
                if let error = error {
                    Logger.web.error("failed with \(error.localizedDescription, privacy: .public)")
                    callback([])
                    return
                }
                guard let httpResponse = response as? HTTPURLResponse,
                      (200...299).contains(httpResponse.statusCode) else {
                          Logger.web.error("failed with invalid statusCode")
                          callback([])
                          return
                      }
                if let mimeType = httpResponse.mimeType, mimeType == "application/json",
                   let data = data {
                    do {
                        let rv : [Near] = try JSONDecoder().decode([Near].self, from: data)
                        Logger.web.info("success \(url, privacy: .public)")
                        callback(rv.map { $0.station })
                    } catch {
                        Logger.web.error("failed with \(error.localizedDescription, privacy: .public)")
                        callback([])
                    }
                }
            }
            task.resume()
        }
    }
}

