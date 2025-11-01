import XCTest
@testable import RZFlight
import FMDB

final class RZFlightTests: XCTestCase {
    
    // Optional: set RZFLIGHT_REGENERATE_SAMPLES=1 to rewrite JSON fixtures from DB
    private var shouldRegenerateSamples: Bool {
        return ProcessInfo.processInfo.environment["RZFLIGHT_REGENERATE_SAMPLES"] == "1"
    }
    
    func findAirportDb() -> FMDatabase? {
        let thisSourceFile = URL(fileURLWithPath: #file)
        let rootDirectory = thisSourceFile.deletingLastPathComponent().deletingLastPathComponent().deletingLastPathComponent()
        let resourceURL = rootDirectory.appendingPathComponent("euro_aip/example").appendingPathComponent("airports.db")
        if FileManager.default.fileExists(atPath: resourceURL.path) {
            let db = FMDatabase(url: resourceURL)
            db.open()
            return db
        }
        return nil
    }
    
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
        // 1) Try reading existing fixture in new format
        if let data = try? Data(contentsOf: url), let airport = try? JSONDecoder().decode(Airport.self, from: data) {
            XCTAssertEqual(airport.icao.uppercased(), icao.uppercased())
            return airport
        }
        // 2) If missing or incompatible, try to load from DB and (optionally) regenerate fixture
        if shouldRegenerateSamples {
            if let db = self.findAirportDb() {
                let known = KnownAirports(db: db)
                if let airport = known.airport(icao: icao.uppercased(), ensureRunway: true) {
                    XCTAssertEqual(airport.icao.uppercased(), icao.uppercased())
                    let encoder = JSONEncoder()
                    encoder.outputFormatting = [.prettyPrinted, .sortedKeys]
                    if let encoded = try? encoder.encode(airport) {
                        // Ensure directory exists then write
                        try? FileManager.default.createDirectory(at: url.deletingLastPathComponent(), withIntermediateDirectories: true)
                        try? encoded.write(to: url)
                    }
                    return airport
                }
            }
        }
        // 3) Give a helpful failure
        XCTAssertTrue(false, "Unable to load airport \(icao). Provide fixture at \(url.lastPathComponent) or set RZFLIGHT_REGENERATE_SAMPLES=1 with a valid euro_aip/example/airports.db")
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
        decodeAirport(icao: "lfmd")
        decodeAirport(icao: "lfpt")
    }
    
    func testMetar(){
        decodeMetar(icao: "eglf")
        decodeMetar(icao: "egll")
        decodeMetar(icao: "kpao")
        decodeMetar(icao: "ksfo")
    }
    

}

