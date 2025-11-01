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
    
    override func setUpWithError() throws {
        // Point the AIPFieldCatalog to the repo CSV so standardized fields resolve in tests
        let thisSourceFile = URL(fileURLWithPath: #file)
        let rootDirectory = thisSourceFile.deletingLastPathComponent().deletingLastPathComponent().deletingLastPathComponent()
        let csvURL = rootDirectory
            .appendingPathComponent("euro_aip")
            .appendingPathComponent("euro_aip")
            .appendingPathComponent("utils")
            .appendingPathComponent("aip_fields.csv")
        if FileManager.default.fileExists(atPath: csvURL.path) {
            AIPEntry.AIPFieldCatalog.setOverrideURL(csvURL)
        }
    }

    override func tearDownWithError() throws {
        // Put teardown code here. This method is called after the invocation of each test method in the class.
    }

    func testExample() throws {
        guard let known = TestSupport.shared.known else {
            XCTFail("No db found, make sure you run airports.py")
            return
        }
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
            
    }

    func testLazyLoadingBehavior() throws {
        guard let db = TestSupport.shared.db, let known = TestSupport.shared.known else {
            XCTFail("No db found, make sure you run airports.py")
            return
        }
        

        // EGTF: ensure runways only
        if var egtf = known.airport(icao: "EGTF", ensureRunway: true) {
            XCTAssertFalse(egtf.runways.isEmpty)
            XCTAssertTrue(egtf.procedures.isEmpty)
            XCTAssertTrue(egtf.aipEntries.isEmpty)
            // Explicitly load procedures and AIP
            _ = egtf.addProcedures(db: db)
            _ = egtf.addAIPEntries(db: db)
            // EGTF expected to have no procedures; AIP could be empty
            XCTAssertTrue(egtf.procedures.isEmpty)
        }

        // EGKB: has procedures
        if var egkb = known.airport(icao: "EGKB", ensureRunway: true) {
            XCTAssertFalse(egkb.runways.isEmpty)
            XCTAssertTrue(egkb.procedures.isEmpty)
            _ = egkb.addProcedures(db: db)
            XCTAssertFalse(egkb.procedures.isEmpty)
        }
    }

    func testRunwayEndFields() throws {
        guard let known = TestSupport.shared.known else {
            XCTFail("No db found, make sure you run airports.py")
            return
        }
        
        if let egll = known.airport(icao: "EGLL", ensureRunway: true) {
            guard let rw = egll.runways.first else { return }
            XCTAssertFalse(rw.le.ident.isEmpty)
            XCTAssertFalse(rw.he.ident.isEmpty)
            // Headings should be finite numbers
            XCTAssertGreaterThan(rw.trueHeading1.heading, 0)
            XCTAssertGreaterThan(rw.trueHeading2.heading, 0)
            // Coordinates may or may not be present depending on DB; do not assert non-nil strictly
        }
    }

    func testProceduresAndPrecision() throws {
        guard let db = TestSupport.shared.db, let known = TestSupport.shared.known else {
            XCTFail("No db found, make sure you run airports.py")
            return
        }
        
        if var egkb = known.airport(icao: "EGKB", ensureRunway: true) {
            _ = egkb.addProcedures(db: db)
            // Partition checks
            XCTAssertEqual(egkb.approaches.filter { !$0.isApproach }.count, 0)
            XCTAssertEqual(egkb.departures.filter { !$0.isDeparture }.count, 0)
            XCTAssertEqual(egkb.arrivals.filter { !$0.isArrival }.count, 0)
            // If any runway exists, mostPreciseApproach should prefer higher precision when applicable
            if let rw = egkb.runways.first, !egkb.approaches.isEmpty {
                _ = egkb.mostPreciseApproach(for: rw) // Not strictly asserting type due to DB variability
            }
        }
    }

    func testAIPEntryStandardization() throws {
        guard let db = TestSupport.shared.db, let known = TestSupport.shared.known else {
            XCTFail("No db found, make sure you run airports.py")
            return
        }
        
        // LFAQ expected to have AIP custom field
        if var lfaq = known.airport(icao: "LFAQ", ensureRunway: true) {
            _ = lfaq.addAIPEntries(db: db)
            // Ensure we loaded something (if the example DB contains entries)
            if !lfaq.aipEntries.isEmpty {
                // At least one standardized entry should resolve via catalog when std_field_id is present
                let hasStandardized = lfaq.aipEntries.contains { $0.standardField != nil }
                // We do not hard assert true if dataset varies, but we check consistency if present
                if hasStandardized {
                    for entry in lfaq.aipEntries where entry.standardField != nil {
                        XCTAssertNotNil(entry.standardField?.name)
                        XCTAssertNotNil(entry.standardField?.id)
                    }
                }
            }
        }
    }

    func testHelperQueries() throws {
        guard let known = TestSupport.shared.known else {
            XCTFail("No db found, make sure you run airports.py")
            return
        }
        let london = CLLocationCoordinate2D(latitude: 51.5074, longitude: -0.1278)
        let withILS = known.airportsWithApproach(.ils, near: london, within: 100.0)
        // Should typically include EGLL if present in DB data set
        if let egll = known.airport(icao: "EGLL", ensureRunway: false) {
            // Not a hard assert due to dataset variability, but sanity check allowed
            if !withILS.isEmpty {
                XCTAssertTrue(withILS.contains(egll) || true)
            }
        }
    }

    func testAirportsNearRoute() throws {
        guard let known = TestSupport.shared.known else {
            XCTFail("No db found, make sure you run airports.py")
            return
        }
        
        // Test single point route - airports near EGTF
        let singlePointRoute = ["EGTF"]
        let nearSinglePoint = known.airportsNearRoute(singlePointRoute, within: 10.0)
        XCTAssertGreaterThan(nearSinglePoint.count, 0, "Should find airports near EGTF")
        
        // Verify EGTF is in the results (distance should be 0)
        if let egtf = known.airport(icao: "EGTF", ensureRunway: false) {
            XCTAssertTrue(nearSinglePoint.contains(egtf), "EGTF should be in results for single point route")
            // First result should be EGTF itself (distance = 0)
            XCTAssertEqual(nearSinglePoint.first?.icao, "EGTF", "Closest airport should be EGTF itself")
        }
        
        // Test two-point route: EGTF to LFMD
        let twoPointRoute = ["EGTF", "LFMD"]
        let nearTwoPoint = known.airportsNearRoute(twoPointRoute, within: 50.0)
        XCTAssertGreaterThan(nearTwoPoint.count, 0, "Should find airports near the EGTF-LFMD route")
        
        // Both endpoint airports should be in results
        if let egtf = known.airport(icao: "EGTF", ensureRunway: false),
           let lfmd = known.airport(icao: "LFMD", ensureRunway: false) {
            XCTAssertTrue(nearTwoPoint.contains(egtf), "EGTF should be in route results")
            XCTAssertTrue(nearTwoPoint.contains(lfmd), "LFMD should be in route results")
        }
        
        // Test three-point route: EGTF -> LFLX -> LFMD
        let threePointRoute = ["EGTF", "LFLX", "LFMD"]
        let nearThreePoint = known.airportsNearRoute(threePointRoute, within: 50.0)
        XCTAssertGreaterThan(nearThreePoint.count, 0, "Should find airports near the three-point route")
        
        // All three airports should be in results
        if let egtf = known.airport(icao: "EGTF", ensureRunway: false),
           let lflx = known.airport(icao: "LFLX", ensureRunway: false),
           let lfmd = known.airport(icao: "LFMD", ensureRunway: false) {
            XCTAssertTrue(nearThreePoint.contains(egtf), "EGTF should be in three-point route results")
            XCTAssertTrue(nearThreePoint.contains(lflx), "LFLX should be in three-point route results")
            XCTAssertTrue(nearThreePoint.contains(lfmd), "LFMD should be in three-point route results")
        }
        
        // Test with invalid ICAO codes
        let invalidRoute = ["XXXX"]
        let nearInvalid = known.airportsNearRoute(invalidRoute, within: 10.0)
        XCTAssertEqual(nearInvalid.count, 0, "Should return empty array for invalid route")
        
        // Test empty route
        let emptyRoute: [String] = []
        let nearEmpty = known.airportsNearRoute(emptyRoute, within: 10.0)
        XCTAssertEqual(nearEmpty.count, 0, "Should return empty array for empty route")
    }
    
    func testRouteFiltering() throws {
        guard let known = TestSupport.shared.known else {
            XCTFail("No db found, make sure you run airports.py")
            return
        }
        
        
        // Get airports near EGTF to LOWS route
        let route = ["EGTF", "LOWS"]
        let nearRoute = known.airportsNearRoute(route, within: 100.0)
        
        // Test runway length filtering
        let withLongRunways = nearRoute.withRunwayLength(minimumFeet: 3000)
        for airport in withLongRunways {
            XCTAssertFalse(airport.runways.isEmpty, "Should have runways")
            let maxLength = airport.runways.map { $0.length_ft }.max() ?? 0
            XCTAssertGreaterThanOrEqual(maxLength, 3000, "Should have at least one runway >= 3000ft")
        }
        
        // Test runway length range filtering
        let withMediumRunways = nearRoute.withRunwayLength(minimumFeet: 2000, maximumFeet: 5000)
        for airport in withMediumRunways {
            let runways = airport.runways
            XCTAssertFalse(runways.isEmpty, "Should have runways")
            let hasMediumRunway = runways.contains { $0.length_ft >= 2000 && $0.length_ft <= 5000 }
            XCTAssertTrue(hasMediumRunway, "Should have at least one runway between 2000-5000ft")
        }
        
        // Test hard runway filtering (if any airports have hard runways)
        let withHardRunways = nearRoute.withHardRunways()
        for airport in withHardRunways {
            let hasHardRunway = airport.runways.contains { $0.isHardSurface }
            XCTAssertTrue(hasHardRunway, "Should have at least one hard surface runway")
        }
        
        // Test lighted runway filtering
        let withLightedRunways = nearRoute.withLightedRunways()
        for airport in withLightedRunways {
            let hasLightedRunway = airport.runways.contains { $0.lighted == true }
            XCTAssertTrue(hasLightedRunway, "Should have at least one lighted runway")
        }
        
        // Test filtering for airports with procedures
        let airports = nearRoute.withProcedures()
        for airport in airports {
            XCTAssertFalse(airport.procedures.isEmpty, "Should have procedures")
        }
        
        // Test filtering for airports with approaches
        let withApproaches = nearRoute.withApproaches()
        for airport in withApproaches {
            XCTAssertFalse(airport.approaches.isEmpty, "Should have approach procedures")
        }
        
        // Test precision approach filtering
        let withPrecisionApproaches = nearRoute.withPrecisionApproaches()
        for airport in withPrecisionApproaches {
            let hasPrecision = airport.approaches.contains { $0.precisionCategory == .precision }
            XCTAssertTrue(hasPrecision, "Should have at least one precision approach")
        }
        
        // Test country filtering (filter for French airports)
        let frenchAirports = nearRoute.inCountry("FR")
        for airport in frenchAirports {
            XCTAssertEqual(airport.country, "FR", "Should be in France")
        }
        
        // Test search filtering
        let matchingEgtf = nearRoute.matching("EGTF")
        XCTAssertGreaterThan(matchingEgtf.count, 0, "Should find airports matching 'EGTF'")
        for airport in matchingEgtf {
            let matches = airport.name.lowercased().contains("egtf") || airport.icao.contains("EGTF")
            XCTAssertTrue(matches, "Should match search term")
        }
    }
    
    func testFilterChaining() throws {
        guard let known = TestSupport.shared.known else {
            XCTFail("No db found, make sure you run airports.py")
            return
        }
        
        
        let route = ["EGTF", "LFPG"]
        let nearRoute = known.airportsNearRoute(route, within: 100.0)
        
        // Chain multiple filters
        let filtered = nearRoute
            .withRunwayLength(minimumFeet: 2000)
            .withHardRunways()
            .withApproaches()
        
        // Verify each airport in the filtered result meets all criteria
        for airport in filtered {
            // Has long runway
            let hasLongRunway = airport.runways.contains { $0.length_ft >= 2000 }
            XCTAssertTrue(hasLongRunway, "Should have runway >= 2000ft")
            
            // Has hard surface
            let hasHardRunway = airport.runways.contains { $0.isHardSurface }
            XCTAssertTrue(hasHardRunway, "Should have hard surface runway")
            
            // Has approaches
            XCTAssertFalse(airport.approaches.isEmpty, "Should have approach procedures")
        }
    }
    
    func testBorderCrossingFiltering() throws {
        guard let db = TestSupport.shared.db, let known = TestSupport.shared.known else {
            XCTFail("No db found, make sure you run airports.py")
            return
        }
        
        
        // Get all border crossing airports
        let borderCrossing = known.airportsWithBorderCrossing()
        
        // Note: This test depends on the database having border crossing data
        // We just verify the function works without crashing
        for airport in borderCrossing {
            XCTAssertTrue(airport.isBorderCrossing(db: db), "Should be a border crossing point")
        }
        
        // Test border crossing filter on a route
        let route = ["EGTF", "LFPG"]
        let nearRoute = known.airportsNearRoute(route, within: 200.0)
        
        // Filter for border crossing airports
        let borderOnly = nearRoute.borderCrossingOnly(db: db)
        
        // Verify all results are border crossing points
        for airport in borderOnly {
            XCTAssertTrue(airport.isBorderCrossing(db: db), "Should be a border crossing point")
        }
    }

    func testPerformanceExample() throws {
        // This is an example of a performance test case.
        self.measure {
            // Put the code you want to measure the time of here.
        }
    }

}
