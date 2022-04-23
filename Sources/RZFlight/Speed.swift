//
//  Speed.swift
//  xwind
//
//  Created by Brice Rosenzweig on 13/02/2022.
//

import Foundation

struct Speed {
    var roundedSpeed : Int
    
    var speed : Double {
        get { Double(self.roundedSpeed) }
        set { self.roundedSpeed = max(0,Int(round(newValue))) }
    }
    
    var descriptionWithUnit : String {
        get { "\(roundedSpeed)kts" }
    }

    var description : String {
        get { "\(roundedSpeed)" }
        set { if let x = Int(newValue) { roundedSpeed = x } else { roundedSpeed = 0 } }
    }

    init( roundedSpeed : Int){
        self.roundedSpeed = roundedSpeed
    }
    
    init( speed : Double){
        self.roundedSpeed = Int(round(speed))
    }
    
    mutating func increase(speed : Int){
        self.roundedSpeed = max(0, speed + self.roundedSpeed)
    }
    
    mutating func cap(at : Int){
        if roundedSpeed > at {
            roundedSpeed = at
        }
    }
    
    static func *(_ speed : Speed, _ percent : Percent) -> Speed {
        return Speed(speed: speed.speed * percent.percent)
    }

}

