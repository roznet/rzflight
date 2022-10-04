//
//  Secrets.swift
//  MentalCrosswind
//
//  Created by Brice Rosenzweig on 26/02/2022.
//

import Foundation

public struct Secrets : Decodable {
    private let info : [String : String]
    public init(url : URL?){
        if let fileurl = url,
           let data = try? Data(contentsOf: fileurl),
           let secrets = try? JSONDecoder().decode([String:String].self, from: data) {
            info = secrets
        }else{
            info = [:]
        }
    }
    
    subscript(_ key : String) -> String? {
        return info[ key ]
    }
    
    public func value(for key: String, default value :String = "") -> String {
        return info[key] ?? value
    }
    /**
     * need to be initialized by the application with a valid json secret file
     */
    public static var shared = Secrets(url: nil)
}
