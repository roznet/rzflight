//
//  Percent.swift
//  MentalCrosswind
//
//  Created by Brice Rosenzweig on 24/02/2022.
//

import Foundation

struct Percent {
    // store in decimal: 1 = 100%
    var percent : Double
    
    init(percent : Double){
        self.percent = percent
    }
    
    init(rounded: Int){
        self.percent = Double(rounded) / 100.0
    }
    
    var description : String {
        let rounded = Int(round(percent*100.0))
        return "\(rounded)%"
    }
}
