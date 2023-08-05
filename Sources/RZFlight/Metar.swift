//
//  Metar.swift
//  MentalCrosswind
//
//  Created by Brice Rosenzweig on 26/02/2022.
//

import Foundation
import OSLog
import RZUtilsSwift

public struct Metar : Decodable {
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
    
}
