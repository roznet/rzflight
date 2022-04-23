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

struct Airport : Decodable {
    
    enum Category: String, Decodable {
            case city, name, country, elevation_ft, icao, latitude, longitude, reporting
        }
    struct Runway : Decodable{
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
    }
    
    struct Near : Decodable{
        enum Category: String, Decodable {
                case station
            }

        var station : Airport
    }
    
    var name : String
    var city : String
    var country : String
    var elevation_ft : Int
    var icao : String
    var latitude : Double
    var longitude : Double
    var reporting : Bool
    
    var runways : [Runway]
    
    var coord : CLLocationCoordinate2D { return CLLocationCoordinate2D(latitude: latitude, longitude: longitude) }
    
    private var declination : Double { return Geomagnetism(longitude: longitude, latitude: latitude).declination }
    
    func magneticHeading(from : Heading) -> Heading {
        return Heading(heading: (from.heading - declination) )
    }
    func trueHeading(from : Heading) -> Heading {
        return Heading(heading: (from.heading + declination) )
    }
    
    func bestRunway(wind : Heading) -> Heading {
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
    
    static func at(icao: String, callback : @escaping (_ : Airport?) -> Void ) {
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
    
    static func near(coord : CLLocationCoordinate2D, count : Int = 5, callback : @escaping (_ : [Airport]) -> Void) {
        if let url = URL(string: "https://avwx.rest/api/station/near/\(coord.latitude),\(coord.longitude)?n=\(count)&reporting=true"),
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
