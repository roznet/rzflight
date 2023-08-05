import XCTest
@testable import RZFlight

final class RZFlightTests: XCTestCase {
    
    func findResource( name : String) -> URL{
        let thisSourceFile = URL(fileURLWithPath: #file)
        let thisDirectory = thisSourceFile.deletingLastPathComponent()
        let resourceURL = thisDirectory.appendingPathComponent("samples").appendingPathComponent(name)
        return resourceURL
    }
    func testHeading() throws {
        let tests = [ (240, 60), (270, 90), (180,0), (20, 200)]
        for test in tests {
            let h1 = test.0
            let h2 = test.1
            XCTAssertEqual(Heading(roundedHeading: h1).opposing, Heading(roundedHeading: h2))
            XCTAssertEqual(Heading(roundedHeading: h2).opposing, Heading(roundedHeading: h1))
        }
    }

    @discardableResult func decodeAirport(icao : String) -> Airport? {
        let url = self.findResource(name: "station-\(icao).json")
        do {
            let data = try Data(contentsOf: url)
            let airport = try JSONDecoder().decode(Airport.self, from: data)
            XCTAssertEqual(airport.icao.uppercased(), icao.uppercased())
            return airport
        } catch {
            print( "\(error)" )
            XCTAssertTrue(false)
        }
        return nil
    }

    @discardableResult func decodeNear(location : String) -> [Airport]? {
        let url = self.findResource(name: "near-\(location).json")
        do {
            let data = try Data(contentsOf: url)
            let airports = try JSONDecoder().decode([AviationRemoteService.AVWX.Near].self, from: data)
            XCTAssertEqual(airports.count, 5)
            return airports.map { $0.station }
        } catch {
            print( "\(error)" )
            XCTAssertTrue(false)
        }
        return nil
    }

    @discardableResult func decodeMetar(icao : String) -> Metar? {
        
        let url = self.findResource(name: "metar-\(icao).json" )
        do {
            let data = try Data(contentsOf: url)
            let metar = try Metar.metar(json: data)
            
            XCTAssertGreaterThan(metar.wind_speed.value, 0)
            XCTAssertGreaterThan(metar.wind_direction.value, 0)
            return metar
        } catch {
            print( "\(error)" )
            XCTAssertTrue(false)
        }
        return nil
    }

    
    func testAirport(){
        decodeAirport(icao: "egll")
        decodeAirport(icao: "eglf")
        decodeAirport(icao: "egtf")
        decodeAirport(icao: "kpao")
    }
    
    func testNear(){
        decodeNear(location: "london")
        decodeNear(location: "paloalto")
    }
    
    func testMetar(){
        decodeMetar(icao: "eglf")
        decodeMetar(icao: "egll")
        decodeMetar(icao: "kpao")
        decodeMetar(icao: "ksfo")
    }
    
    func testRunway(){
        let icao = "ksfo"
        if let airport = decodeAirport(icao: icao) {
            print( airport.bestRunway(wind: Heading(heading: 180)) )
        }
        
        
    }

}
