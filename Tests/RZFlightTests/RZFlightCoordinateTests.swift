//
//  RZFlightCoordinateTests.swift
//  RZFlightTests
//
//  Public coordinate helpers. Imported without @testable so the test fails to
//  compile if they stop being public.
//

import XCTest
import RZFlight
import CoreLocation

final class RZFlightCoordinateTests: XCTestCase {

    func testPointFromBearingDistance() {
        // 1 nm east at the equator is about one arc minute of longitude
        let east = CLLocationCoordinate2D(latitude: 0.0, longitude: 0.0).pointFromBearingDistance(bearing: 90.0, distanceNm: 1.0)
        XCTAssertEqual(east.latitude, 0.0, accuracy: 1.0e-9)
        XCTAssertEqual(east.longitude, 1.0 / 60.0, accuracy: 1.0e-4)

        // 2 nm north is two arc minutes of latitude anywhere
        let north = CLLocationCoordinate2D(latitude: 51.5, longitude: -0.2).pointFromBearingDistance(bearing: 0.0, distanceNm: 2.0)
        XCTAssertEqual(north.latitude, 51.5 + 2.0 / 60.0, accuracy: 1.0e-4)
        XCTAssertEqual(north.longitude, -0.2, accuracy: 1.0e-9)

        // distance is preserved along a diagonal bearing
        let start = CLLocation(latitude: 48.0, longitude: 2.0)
        let sw = start.coordinate.pointFromBearingDistance(bearing: 225.0, distanceNm: 10.0)
        let distance = start.distance(from: CLLocation(latitude: sw.latitude, longitude: sw.longitude))
        XCTAssertEqual(distance, 18520.0, accuracy: 18520.0 * 0.005)
        XCTAssertLessThan(sw.latitude, 48.0)
        XCTAssertLessThan(sw.longitude, 2.0)
    }
}
