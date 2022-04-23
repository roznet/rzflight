//
//  Heading.swift
//  xwind
//
//  Created by Brice Rosenzweig on 13/02/2022.
//

import Foundation

struct Heading {
    enum Direction {
        case left
        case right
        case ahead
        case behind
        
        var arrow : String {
            switch self {
            case .left: return "⬅"
            case .right: return "➡"
            case .ahead: return "⬇"
            case .behind: return "⬆"
            }
        }
        var description : String {
            switch self {
            case .left: return "Left"
            case .right: return "Right"
            case .ahead: return "Head"
            case .behind: return "Tail"
            }
        }
        
    }
    
    private(set) var roundedHeading : Int
    
    var heading : Double {
        get { return Double(roundedHeading) }
        set { self.roundedHeading = Int(round(newValue)) % 360 }
    }
    
    var descriptionWithUnit : String {
        get { let x = Int(round(heading)); return "\(x)°" }
    }
    
    var description : String {
        get { let x = Int(round(heading)); return x == 0 ? "360" : "\(x)" }
        set { if let x = Int(newValue) { self.roundedHeading = x } }
    }
    
    var runwayDescription : String {
        get { let x = Int(round(heading/10)); return x == 0 ? "36" : "\(String(format: "%02d",x))" }
        set { if let x = Int(newValue) { self.roundedHeading = (x % 360) * 10 } }
    }
    
    var opposing : Heading {
        get { return Heading(roundedHeading: self.roundedHeading + 180) }
        set { self.roundedHeading = (newValue.roundedHeading + 180) % 360 }
    }
    
    //MARK: - Init
    
    init(roundedHeading: Int){
        self.roundedHeading = (roundedHeading % 360)
    }
    
    init(runwayDescription : String){
        if let x = Int(runwayDescription) {
            self.roundedHeading = x * 10
        }else{
            self.roundedHeading = 0
        }
    }
    
    init(heading : Double){
        self.roundedHeading = Int(round(heading))
    }
    
    init(description: String){
        if let x = Int(description) {
            self.roundedHeading = x
        }else{
            self.roundedHeading = 0
        }

    }

    //MARK: - Computations
    
    func absoluteDifference(with other : Heading) -> Heading {
        let diff = abs(other.roundedHeading - self.roundedHeading)
        if diff > 180 {
            return Heading(roundedHeading: 360-diff)
        }else{
            return Heading(roundedHeading: diff)
        }
    }

    func directDirection(to other: Heading) -> Direction {
        let diff = self.absoluteDifference(with: other)
        if diff.roundedHeading < 90 {
            return .ahead
        }else if diff.roundedHeading > 90 {
            return .behind
        }else{
            if( self + diff == other){
                return .right
            }else{
                return .left
            }
        }
    }

    func crossDirection(to other: Heading) -> Direction {
        let diff = self.absoluteDifference(with: other)
        if diff.roundedHeading == 0 {
            return .ahead
        }else if diff.roundedHeading == 180 {
            return .behind
        }else{
            if( self + diff == other){
                return .right
            }else{
                return .left
            }
        }
    }
    
    func crossWindComponent(with other : Heading) -> Percent {
        return Percent(percent: abs(__sinpi(self.absoluteDifference(with: other).heading/180.0)))
    }
    
    func headWindComponent(with other : Heading) -> Percent {
        return Percent(percent: abs(__cospi(self.absoluteDifference(with: other).heading/180.0)))
    }

    mutating func rotate(degree : Int){
        self.roundedHeading = (self.roundedHeading + degree + 360) % 360
    }

    
}

func + (left:Heading, right:Heading) -> Heading {
    return Heading(roundedHeading: (left.roundedHeading+right.roundedHeading)%360)
}
extension Heading : Equatable {
    static func == (left:Heading, right:Heading) -> Bool {
        return left.roundedHeading == right.roundedHeading
    }
}
