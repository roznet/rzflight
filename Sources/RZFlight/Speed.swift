//
//  Speed.swift
//  xwind
//
//  Created by Brice Rosenzweig on 13/02/2022.
//

import Foundation

public struct Speed {
    var roundedSpeed : Int
    
    public var speed : Double {
        get { Double(self.roundedSpeed) }
        set { self.roundedSpeed = max(0,Int(round(newValue))) }
    }
    
    public var descriptionWithUnit : String {
        get { "\(roundedSpeed)kts" }
    }

    public var description : String {
        get { "\(roundedSpeed)" }
        set { if let x = Int(newValue) { roundedSpeed = x } else { roundedSpeed = 0 } }
    }

    public init( roundedSpeed : Int){
        self.roundedSpeed = roundedSpeed
    }
    
    public init( speed : Double){
        self.roundedSpeed = Int(round(speed))
    }
    
    public mutating func increase(speed : Int){
        self.roundedSpeed = max(0, speed + self.roundedSpeed)
    }
    
    public mutating func cap(at : Int){
        if roundedSpeed > at {
            roundedSpeed = at
        }
    }
    
    public static func *(_ speed : Speed, _ percent : Percent) -> Speed {
        return Speed(speed: speed.speed * percent.percent)
    }

}

@propertyWrapper
public struct SpeedStorage {
    private let key : String
    private let defaultValue : Speed
    
    public init(key : String, defaultValue : Speed){
        self.key = key
        self.defaultValue = defaultValue
    }
    
    public var wrappedValue : Speed {
        get {
            let val = UserDefaults.standard.integer(forKey: key)
            return Speed(roundedSpeed: val)
        }
        set {
            UserDefaults.standard.set(newValue.roundedSpeed, forKey: key)
        }
    }
}


