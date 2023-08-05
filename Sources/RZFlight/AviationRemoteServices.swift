//
//  File.swift
//  
//
//  Created by Brice Rosenzweig on 05/08/2023.
//

import Foundation
import RZUtilsSwift
import OSLog
import CoreLocation

struct AviationRemoteService {
   
    struct AVWX {
        
        struct Near : Decodable{
            enum Category: String, Decodable {
                case station
            }
            
            var station : Airport
        }
        public static func metar(icao : String, callback : @escaping (_ : Metar?, _ : String) -> Void){
            if let url = URL(string: "https://avwx.rest/api/metar/\(icao)"),
               let token = Secrets.shared["avwx"]{
                var request = URLRequest(url: url)
                Logger.web.info("query \(url, privacy: .public)")
                request.setValue("BEARER \(token)", forHTTPHeaderField: "Authorization")
                let task = URLSession.shared.dataTask(with: request) { data, response, error in
                    if let error = error {
                        Logger.web.error("failed with \(error.localizedDescription, privacy: .public)")
                        callback(nil,icao)
                        return
                    }
                    guard let httpResponse = response as? HTTPURLResponse,
                          (200...299).contains(httpResponse.statusCode) else {
                        callback(nil,icao)
                        return
                    }
                    if let mimeType = httpResponse.mimeType, mimeType == "application/json",
                       let data = data {
                        let rv : Metar? = try? Metar.metar(json: data)
                        callback(rv,icao)
                    }
                    return
                }
                task.resume()
            }
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
}
