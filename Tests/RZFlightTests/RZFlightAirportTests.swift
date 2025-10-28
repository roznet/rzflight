//
//  RZFlightAirportTests.swift
//
//
//  Created by Brice Rosenzweig on 05/08/2023.
//

import XCTest
import FMDB
@testable import RZFlight
import CoreLocation

//Airports in test db:
//  EGTF (no proc) EGMD (proc)
//  LFAT (ppf) LFQA (not ppf)
final class RZFlightAirportTests: XCTestCase {
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
    
    override func setUpWithError() throws {
        // Put setup code here. This method is called before the invocation of each test method in the class.
    }

    override func tearDownWithError() throws {
        // Put teardown code here. This method is called after the invocation of each test method in the class.
    }

    func testExample() throws {
        if let db = self.findAirportDb() {
            let known = KnownAirports(db: db)
            XCTAssertEqual(known.airport(icao: "LFPG")?.name, "Charles de Gaulle International Airport")
 
            let uk = known.matching(needle: "fairo")
            XCTAssertEqual(uk.count, 1)
            XCTAssertEqual(uk.first?.icao, "EGTF")
            
            let ock = CLLocationCoordinate2D(latitude: 51.3050,  longitude: -0.4471)
            var near = known.nearest(coord: ock, count: 10)
            XCTAssertEqual(near.count, 10)
            if let egtf = uk.first, let egll = known.airport(icao: "EGLL") {
                // by default should contain heathrow
                XCTAssertTrue(near.contains(egtf))
                XCTAssertTrue(near.contains(egll))
                near = known.nearestMatching(coord: ock, needle: "EGT", count: 10)
                XCTAssertEqual(near.count,10)
                for one in near {
                    XCTAssertTrue(one.icao.hasPrefix("EGT"))
                    // because of needle match, should not contain heathrow
                    XCTAssertFalse(one.icao.hasPrefix("EGL"))
                }
            }
            
            if let lfat = known.airportWithExtendedData(icao: "LFAT") {
                XCTAssert(lfat.approaches.count > 0)
                XCTAssert(lfat.runways.count > 0)
                XCTAssert(lfat.aipEntries.count > 0)
            }
            
            
        }else{
            XCTAssertTrue(false, "No db found, make sure you run airports.py")
        }
    }

    func testPerformanceExample() throws {
        // This is an example of a performance test case.
        self.measure {
            // Put the code you want to measure the time of here.
        }
    }

}
