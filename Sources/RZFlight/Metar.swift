//
//  Metar.swift
//  MentalCrosswind
//
//  Created by Brice Rosenzweig on 26/02/2022.
//

import Foundation
import OSLog

struct Metar : Decodable {
    enum Category: String, Decodable {
            case wind_direction, wind_speed
        }
    struct Value : Decodable{
        enum Category: String, Decodable {
                case value
            }
        var value : Int
    }
    
    struct Time : Decodable{
        enum Category : String, Decodable {
            case dt
        }
        var dt : Date
    }
    
    var time : Time
    var wind_direction : Value
    var wind_speed : Value
    var gust_speed : Value?
    
    var ageInMinutesIfLessThanOneHour : Int? {
        let secs = Int(Date().timeIntervalSince1970 - time.dt.timeIntervalSince1970)
        if secs > 3600 {
            return nil
        }
        return secs / 60
    }
    
    static func metar(json : Data) throws -> Metar {
        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601
        let rv : Metar = try decoder.decode(Metar.self, from: json)
        return rv
    }
    
    static func metar(icao : String, callback : @escaping (_ : Metar?, _ : String) -> Void){
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
                    let rv : Metar? = try? self.metar(json: data)
                    callback(rv,icao)
                }
            }
            task.resume()
        }
    }
}
