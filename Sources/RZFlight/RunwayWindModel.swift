//
//  XCWindModel.swift
//  xwind
//
//  Created by Brice Rosenzweig on 13/02/2022.
//

import Foundation
#if os(iOS)
import AVFoundation
#endif

@objc public class RunwayWindModel : NSObject {
    private var completion : ()->Void = {}
    
    public var runwayHeading : Heading
    public var windHeading : Heading

    public var windSpeed : Speed = Speed(roundedSpeed: 10 )
    public var windGust : Speed? = nil
    
    public var windSource : String? = nil
    public var windSourceDate : Date? = nil
    
    public init( runway : Heading, wind : Heading? = nil, speed : Speed? = nil, gust : Speed? = nil){
        self.runwayHeading = runway
        self.windHeading = wind ?? runway
        self.windSpeed = speed ?? Speed(roundedSpeed: 0)
        self.windGust = gust
    }
    
    public override init(){
        self.runwayHeading = Heading(roundedHeading: 240 )
        self.windHeading = Heading(roundedHeading: 190 )
        self.windSpeed = Speed(roundedSpeed: 10)
        self.windGust = nil
    }

    //MARK: - calculate
    
    public var crossWindComponent :  Percent {
        return self.windHeading.crossWindComponent(with: self.runwayHeading)
    }
    
    public var crossWindSpeed : Speed {
        return self.windSpeed * crossWindComponent
    }
    
    public var directWindDirection : Heading.Direction {
        return self.windHeading.directDirection(to: self.runwayHeading)
    }
    
    public var crossWindDirection : Heading.Direction {
        return self.windHeading.crossDirection(to: self.runwayHeading)
    }
    
    public var headWindComponent : Percent {
        return self.windHeading.headWindComponent(with: self.runwayHeading)
    }
    
    public var headWindSpeed : Speed {
        return self.windSpeed * self.headWindComponent
    }

    public var windRunwayOffset : Heading {
        return self.windHeading.absoluteDifference(with: self.runwayHeading)
    }
    
    
    
    //MARK: - describe
    
    public func enunciate(number : String) -> String{
        let chars = number.map { String($0) }
        return chars.joined(separator: " ")
    }

    public var windDisplay : String {
        return "\(self.windHeading.description) @ \(self.windSpeed.description)"
    }
    
    public var announce : String {
        let eHeading = self.enunciate(number: self.windHeading.description)
        let eSpeed = self.enunciate(number: self.windSpeed.description)
        if let windGust = self.windGust {
            let eGust = self.enunciate(number: windGust.description)
            return  "\(eHeading) at \(eSpeed), Gust \(eGust)"
        }else{
            return  "\(eHeading) at \(eSpeed)"
        }
    }
    
    public var windcheck : String {
        return "Wind: \(self.announce)"
    }
    
    public var clearance : String {
        let eRunway = self.enunciate(number: self.runwayHeading.runwayDescription)
        return "Wind: \(self.announce), Runway \(eRunway), Clear to land"
    }
   
    
#if os(iOS)
    var synthetizer : AVSpeechSynthesizer? = nil
    public enum SpeechType {
        case clearance, windcheck
    }
    
    public func speak( which : SpeechType = .clearance, completion : @escaping ()->Void = {}){
        
        let utterance = AVSpeechUtterance(string: which == .clearance ? self.clearance : self.windcheck )
        utterance.rate = 0.5 + (Float.random(in: 0..<10)/1000.0)
        utterance.pitchMultiplier = 0.8 + (Float.random(in: 0..<10)/1000.0)
        utterance.postUtteranceDelay = 0.2
        utterance.volume = 0.8

        
        let available = AVSpeechSynthesisVoice.speechVoices().filter {
            $0.language.starts(with: "en")
        }
        
        let voice = available[ Int.random(in: 0 ..< available.count)]
        utterance.voice = voice
        self.synthetizer = AVSpeechSynthesizer()
        self.completion = completion
        synthetizer?.delegate = self
        synthetizer?.speak(utterance)
    }
#endif
    //MARK: - generate
    
    func speedProbabilities() -> [Double] {
        var probabilities : [Double] = []
        
        for _ in 0 ..< 5 {
            probabilities.append(5.0)
        }
        for _ in 5 ..< 20 {
            probabilities.append(10.0)
        }
        for _ in 20 ..< 50 {
            probabilities.append(1.0)
        }
        return probabilities
    }
    
    /**
     * return random number from 0 to probabilities.count each number with probability in array probabilities
     */
    func random(probabilities : [Double]) -> Double {
        let total = probabilities.reduce(0, +)
        let uniform = Double.random(in: 0 ..< total)
        var running : Double = 0.0
        
        for (value,probability) in probabilities.enumerated() {
            running += probability
            if uniform < running {
                return Double(value)
            }
        }
        
        return Double(probabilities.count - 1)
    }
    
    public func randomizeWind() {
        let windOffset = Int.random(in: -9...9)
        let runwayHeading = runwayHeading.heading
        let windHeading = round(runwayHeading/10)*10 + Double(windOffset * 10)
        let windSpeed = self.random(probabilities: self.speedProbabilities())
        // for gust compute % higher than wind
        let windGust = Double.random(in: 0...100)
        if( windGust > 25.0){
            self.windGust = Speed(speed: windSpeed * ( 1.0 + windGust / 100.0 ))
        }else{
            self.windGust = nil
        }
        self.windSpeed = Speed(speed: windSpeed )
        self.windHeading = Heading(heading: windHeading )
        self.windSource = nil
    }
    
    //MARK: - change values
    
    public func opposingRunway(){
        self.runwayHeading = self.runwayHeading.opposing
    }
    
    public func alreadyRefreshed(airport : Airport? = nil, icao : String? = nil) -> Bool {
        if let sourceDate = self.windSourceDate {
            if sourceDate.timeIntervalSinceNow > -600.0 {
                if let icao = icao {
                    return icao == self.windSource
                }
                if let airport = airport {
                    return airport.icao == self.windSource
                }
            }
        }
        return false
    }
    
    public func setupFrom(metar : Metar, airport : Airport? = nil, icao : String? = nil) {
        if let icao = icao {
            self.windSource = icao
        }
        if let airport = airport {
            self.windSource = airport.icao
        }
        self.windSourceDate = metar.time.dt
        
        self.windHeading = Heading(roundedHeading: metar.wind_direction.value)
        self.windSpeed = Speed(roundedSpeed: metar.wind_speed.value)
        
        if let gustSpeed = metar.gust_speed {
            self.windGust = Speed(roundedSpeed: gustSpeed.value)
        }else{
            self.windGust = nil
        }
    }
    
    public func rotateHeading(degree : Int){
        self.runwayHeading.rotate(degree: degree)
    }
    
    public func updateRunwayHeading(heading : Heading){
        self.runwayHeading = heading
    }
    
    public func rotateWind(degree : Int){
        self.windSource = nil
        self.windHeading.rotate(degree: degree)
    }
    
    public func increaseWind(speed : Int, maximumSpeed : Int = 75){
        self.windSource = nil
        self.windSpeed.increase(speed: speed)
        self.windSpeed.cap(at: maximumSpeed)
    }    
}


#if os(iOS)
extension RunwayWindModel : AVSpeechSynthesizerDelegate {
    @objc public func speechSynthesizer(_ synthesizer: AVSpeechSynthesizer, didFinish utterance: AVSpeechUtterance) {
        self.completion()
    }
}
#endif
