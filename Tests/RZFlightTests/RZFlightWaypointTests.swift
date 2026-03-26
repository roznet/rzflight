//
//  RZFlightWaypointTests.swift
//  RZFlightTests
//
//  Tests for Waypoint, KnownWaypoints, and RoutePointResolver.
//

import XCTest
import FMDB
@testable import RZFlight
import CoreLocation

final class RZFlightWaypointTests: XCTestCase {

    // MARK: - Waypoint Model Tests

    func testWaypointCreation() {
        let wp = Waypoint(name: "BILGO", latitude: 48.5, longitude: 2.3,
                          pointType: "5LNC", firCodes: "LFFF")
        XCTAssertEqual(wp.name, "BILGO")
        XCTAssertEqual(wp.latitude, 48.5)
        XCTAssertEqual(wp.longitude, 2.3)
        XCTAssertEqual(wp.pointType, "5LNC")
        XCTAssertFalse(wp.isNavaid)
    }

    func testWaypointNavaid() {
        let wp = Waypoint(name: "REM", latitude: 49.3, longitude: 3.1, pointType: "VOR")
        XCTAssertTrue(wp.isNavaid)
    }

    func testWaypointFirList() {
        let wp = Waypoint(name: "REM", latitude: 0, longitude: 0, firCodes: "LFFF,LFBB")
        XCTAssertEqual(wp.firList, ["LFFF", "LFBB"])

        let wp2 = Waypoint(name: "A", latitude: 0, longitude: 0)
        XCTAssertEqual(wp2.firList, [])
    }

    func testWaypointEquality() {
        let a = Waypoint(name: "BILGO", latitude: 48.5, longitude: 2.3)
        let b = Waypoint(name: "BILGO", latitude: 48.5, longitude: 2.3)
        XCTAssertEqual(a, b)
    }

    func testWaypointDescription() {
        let wp5 = Waypoint(name: "BILGO", latitude: 0, longitude: 0, pointType: "5LNC")
        XCTAssertEqual(wp5.description, "BILGO")

        let wpVor = Waypoint(name: "REM", latitude: 0, longitude: 0, pointType: "VOR")
        XCTAssertEqual(wpVor.description, "REM (VOR)")
    }

    func testWaypointSearch() {
        let wp = Waypoint(name: "BILGO", latitude: 0, longitude: 0)
        XCTAssertTrue(wp.contains("bil"))
        XCTAssertTrue(wp.contains("BILGO"))
        XCTAssertFalse(wp.contains("xyz"))
    }

    // MARK: - KnownWaypoints Tests

    func testKnownWaypointsLoad() throws {
        guard let wps = TestSupport.shared.knownWaypoints else {
            XCTFail("No waypoints database available")
            return
        }
        XCTAssertGreaterThan(wps.count, 0, "Should have loaded waypoints from test DB")
    }

    func testKnownWaypointsLookup() throws {
        guard let wps = TestSupport.shared.knownWaypoints else {
            XCTFail("No waypoints database available")
            return
        }

        let vesan = wps.waypoint(name: "VESAN")
        XCTAssertNotNil(vesan)
        XCTAssertEqual(vesan?.name, "VESAN")
        XCTAssertEqual(vesan?.pointType, "5LNC")

        // Case insensitive via uppercased()
        let rem = wps.waypoint(name: "rem")
        XCTAssertNotNil(rem)
        XCTAssertEqual(rem?.pointType, "VOR")

        // Non-existent
        XCTAssertNil(wps.waypoint(name: "XYZZY"))
    }

    func testKnownWaypointsNearest() throws {
        guard let wps = TestSupport.shared.knownWaypoints else {
            XCTFail("No waypoints database available")
            return
        }

        let paris = CLLocationCoordinate2D(latitude: 48.8566, longitude: 2.3522)
        let nearest = wps.nearest(coord: paris, count: 3)
        XCTAssertEqual(nearest.count, 3)
    }

    func testKnownWaypointsSearch() throws {
        guard let wps = TestSupport.shared.knownWaypoints else {
            XCTFail("No waypoints database available")
            return
        }

        let results = wps.rankedSearch(needle: "VES", limit: 5)
        XCTAssertTrue(results.contains(where: { $0.name == "VESAN" }))
    }

    func testKnownWaypointsByType() throws {
        guard let wps = TestSupport.shared.knownWaypoints else {
            XCTFail("No waypoints database available")
            return
        }

        let vors = wps.byType("VOR")
        XCTAssertTrue(vors.allSatisfy { $0.pointType == "VOR" })
        XCTAssertTrue(vors.contains(where: { $0.name == "REM" }))
    }

    func testKnownWaypointsByFIR() throws {
        guard let wps = TestSupport.shared.knownWaypoints else {
            XCTFail("No waypoints database available")
            return
        }

        let lfff = wps.byFIR("LFFF")
        XCTAssertGreaterThan(lfff.count, 0)
        XCTAssertTrue(lfff.allSatisfy { $0.firList.contains("LFFF") })
    }

    func testKnownWaypointsGracefulNoTable() throws {
        // Create an in-memory DB without waypoints table
        let db = FMDatabase()
        db.open()
        db.executeStatements("CREATE TABLE airports (icao_code TEXT PRIMARY KEY)")

        let wps = KnownWaypoints(db: db)
        XCTAssertEqual(wps.count, 0)
        XCTAssertNil(wps.waypoint(name: "BILGO"))
        db.close()
    }

    // MARK: - RoutePointResolver Tests

    func testResolveAirport() throws {
        guard let known = TestSupport.shared.known,
              let wps = TestSupport.shared.knownWaypoints else {
            XCTFail("No database available")
            return
        }

        let resolver = RoutePointResolver(airports: known, waypoints: wps)
        let point = resolver.resolve("EGTF")
        XCTAssertNotNil(point)
        XCTAssertEqual(point?.pointType, "airport")
        XCTAssertEqual(point?.name, "EGTF")
    }

    func testResolveWaypoint() throws {
        guard let known = TestSupport.shared.known,
              let wps = TestSupport.shared.knownWaypoints else {
            XCTFail("No database available")
            return
        }

        let resolver = RoutePointResolver(airports: known, waypoints: wps)
        let point = resolver.resolve("VESAN")
        XCTAssertNotNil(point)
        XCTAssertEqual(point?.pointType, "5LNC")
    }

    func testResolveNotFound() throws {
        guard let known = TestSupport.shared.known,
              let wps = TestSupport.shared.knownWaypoints else {
            XCTFail("No database available")
            return
        }

        let resolver = RoutePointResolver(airports: known, waypoints: wps)
        XCTAssertNil(resolver.resolve("XYZZY"))
    }

    func testResolveAirportFirst() throws {
        guard let known = TestSupport.shared.known,
              let wps = TestSupport.shared.knownWaypoints else {
            XCTFail("No database available")
            return
        }

        // EGTF exists as both airport and (hypothetically) waypoint
        // Airport should win
        let resolver = RoutePointResolver(airports: known, waypoints: wps)
        let point = resolver.resolve("EGTF")
        XCTAssertEqual(point?.pointType, "airport")
    }

    func testResolveRoute() throws {
        guard let known = TestSupport.shared.known,
              let wps = TestSupport.shared.knownWaypoints else {
            XCTFail("No database available")
            return
        }

        let resolver = RoutePointResolver(airports: known, waypoints: wps)
        let route = resolver.resolveRoute(
            departure: "EGTF",
            destination: "LFAT",
            waypoints: ["VESAN", "POGOL"]
        )

        XCTAssertEqual(route.departure, "EGTF")
        XCTAssertEqual(route.destination, "LFAT")
        XCTAssertNotNil(route.departureCoordinate)
        XCTAssertNotNil(route.destinationCoordinate)
        XCTAssertEqual(route.waypoints, ["VESAN", "POGOL"])
        XCTAssertEqual(route.waypointCoords.count, 2)
        XCTAssertEqual(route.waypointCoords[0].name, "VESAN")
        XCTAssertEqual(route.waypointCoords[1].name, "POGOL")

        // All coordinates should form a valid path
        XCTAssertEqual(route.allCoordinates.count, 4)
    }

    func testResolveRouteString() throws {
        guard let known = TestSupport.shared.known,
              let wps = TestSupport.shared.knownWaypoints else {
            XCTFail("No database available")
            return
        }

        let resolver = RoutePointResolver(airports: known, waypoints: wps)
        let route = resolver.resolveRouteString("EGTF VESAN POGOL LFAT")

        XCTAssertNotNil(route)
        XCTAssertEqual(route?.departure, "EGTF")
        XCTAssertEqual(route?.destination, "LFAT")
        XCTAssertEqual(route?.waypoints, ["VESAN", "POGOL"])
    }

    func testResolveRouteStringFiltersDCT() throws {
        guard let known = TestSupport.shared.known,
              let wps = TestSupport.shared.knownWaypoints else {
            XCTFail("No database available")
            return
        }

        let resolver = RoutePointResolver(airports: known, waypoints: wps)
        let route = resolver.resolveRouteString("EGTF DCT VESAN DCT LFAT")

        XCTAssertNotNil(route)
        XCTAssertEqual(route?.waypoints, ["VESAN"])
    }

    func testResolveRouteStringTooShort() throws {
        guard let known = TestSupport.shared.known else {
            XCTFail("No database available")
            return
        }

        let resolver = RoutePointResolver(airports: known)
        XCTAssertNil(resolver.resolveRouteString("EGTF"))
    }

    func testResolveRouteWithMixedAirportWaypoint() throws {
        guard let known = TestSupport.shared.known,
              let wps = TestSupport.shared.knownWaypoints else {
            XCTFail("No database available")
            return
        }

        let resolver = RoutePointResolver(airports: known, waypoints: wps)
        // LFQA is an airport used as intermediate waypoint
        let route = resolver.resolveRoute(
            departure: "EGTF",
            destination: "LFAT",
            waypoints: ["LFQA", "VESAN"]
        )

        // LFQA should be resolved but with pointType "waypoint" (not "airport")
        XCTAssertEqual(route.waypointCoords.count, 2)
        XCTAssertEqual(route.waypointCoords[0].pointType, "waypoint")
    }

    func testCombinedSearch() throws {
        guard let known = TestSupport.shared.known,
              let wps = TestSupport.shared.knownWaypoints else {
            XCTFail("No database available")
            return
        }

        let resolver = RoutePointResolver(airports: known, waypoints: wps)
        let results = resolver.search(needle: "VES", limit: 10)
        XCTAssertTrue(results.contains(where: { $0.name == "VESAN" }))
    }

    func testResolverWithoutWaypoints() throws {
        guard let known = TestSupport.shared.known else {
            XCTFail("No database available")
            return
        }

        // Backward compatibility: resolver without waypoints
        let resolver = RoutePointResolver(airports: known)
        let point = resolver.resolve("VESAN")
        XCTAssertNil(point, "Should not resolve waypoints without waypoint database")

        let airport = resolver.resolve("EGTF")
        XCTAssertNotNil(airport, "Should still resolve airports")
    }
}
