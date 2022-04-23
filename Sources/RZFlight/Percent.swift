//
//  Percent.swift
//  MentalCrosswind
//
//  Created by Brice Rosenzweig on 24/02/2022.
//

import Foundation

public struct Percent {
    // store in decimal: 1 = 100%
    var percent : Double
    
    public init(percent : Double){
        self.percent = percent
    }
    
    public init(rounded: Int){
        self.percent = Double(rounded) / 100.0
    }
    
    public var description : String {
        let rounded = Int(round(percent*100.0))
        return "\(rounded)%"
    }
}
