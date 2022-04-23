//
//  Secrets.swift
//  MentalCrosswind
//
//  Created by Brice Rosenzweig on 26/02/2022.
//

import Foundation

struct Secrets : Decodable {
    private let info : [String : String]
    private init(){
        if let fileurl = Bundle.main.url(forResource: "secrets", withExtension: "json"),
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
    
    static let shared = Secrets()
}
