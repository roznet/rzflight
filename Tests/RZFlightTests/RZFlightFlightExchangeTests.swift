//
//  RZFlightFlightExchangeTests.swift
//  RZFlightTests
//
//  Tests for FlightExchange — the cross-app flight interchange model.
//  Decodes the shared parity fixtures (emitted by the Python side) and checks
//  the round-trip invariant. See designs/flight_exchange_design.md.
//

import XCTest
@testable import RZFlight

final class RZFlightFlightExchangeTests: XCTestCase {

    // MARK: - Shared fixtures

    /// Shared cross-platform parity fixtures live at the repo root so both the
    /// Swift and Python test suites read the exact same JSON.
    static func fixturesDirectory() -> URL {
        // The fixtures intentionally live at <repo>/Tests/fixtures so the Python
        // and Swift suites read the byte-identical files. That path sits outside
        // the test target's directory, so it can't be an SPM `Bundle.module`
        // resource — resolve it relative to this source file instead.
        // Use #filePath (always a full filesystem path) rather than #file, which
        // can be a concise module-relative string under some build settings.
        return URL(fileURLWithPath: #filePath)
            .deletingLastPathComponent()   // RZFlightTests
            .deletingLastPathComponent()   // Tests
            .deletingLastPathComponent()   // <repo>
            .appendingPathComponent("Tests")
            .appendingPathComponent("fixtures")
            .appendingPathComponent("flight_exchange")
    }

    func loadFixture(_ name: String) throws -> Data {
        let url = Self.fixturesDirectory().appendingPathComponent(name)
        return try Data(contentsOf: url)
    }

    // MARK: - Decoding Python-emitted fixtures

    func testDecodeFullFixture() throws {
        let data = try loadFixture("full.json")
        let fx = try FlightExchange.decode(from: data)

        XCTAssertEqual(fx.schemaVersion, 1)
        XCTAssertEqual(fx.name, "Oxford -> Sion")

        // Envelope
        XCTAssertEqual(fx.source?.app, "weather")
        XCTAssertEqual(fx.source?.flightId, "egtk_lsgs-2026-06-01-a1b2")
        XCTAssertEqual(fx.source?.shareCode, "Ab3xY9k2")
        XCTAssertEqual(fx.aircraft?.registration, "HB-ABC")
        XCTAssertEqual(fx.aircraft?.type, "P28A")

        // Route embedded verbatim
        XCTAssertEqual(fx.route.departure, "EGTK")
        XCTAssertEqual(fx.route.destination, "LSGS")
        XCTAssertEqual(fx.route.alternates, ["LSGG"])
        XCTAssertEqual(fx.route.waypoints, ["BILGO", "XIDIL"])
        XCTAssertEqual(fx.route.aircraftType, "P28A")
        XCTAssertEqual(fx.route.cruiseAltitudeFt, 8000)
        XCTAssertNil(fx.route.flightLevel)
        XCTAssertEqual(fx.route.waypointCoords.count, 2)
        XCTAssertEqual(fx.route.waypointCoords.first?.name, "BILGO")

        // Coordinates resolve
        XCTAssertEqual(fx.route.departureCoordinate?.latitude ?? 0, 51.83, accuracy: 0.0001)
        XCTAssertEqual(fx.route.destinationCoordinate?.longitude ?? 0, 7.33, accuracy: 0.0001)
        XCTAssertEqual(fx.route.coordinate(for: "LSGG")?.latitude ?? 0, 46.24, accuracy: 0.0001)

        // Times — Python emits ISO-8601 with +00:00 offset; must decode as UTC.
        let expectedDeparture = ISO8601DateFormatter().date(from: "2026-06-01T09:00:00Z")
        XCTAssertEqual(fx.route.departureTime, expectedDeparture)
        let expectedArrival = ISO8601DateFormatter().date(from: "2026-06-01T11:15:00Z")
        XCTAssertEqual(fx.route.arrivalTime, expectedArrival)
    }

    func testDecodeMinimalFixture() throws {
        let data = try loadFixture("minimal.json")
        let fx = try FlightExchange.decode(from: data)

        XCTAssertEqual(fx.schemaVersion, 1)
        XCTAssertEqual(fx.route.departure, "EGTF")
        XCTAssertEqual(fx.route.destination, "EGLL")
        XCTAssertNil(fx.name)
        XCTAssertNil(fx.source)
        XCTAssertNil(fx.aircraft)
        XCTAssertNil(fx.route.departureTime)
        XCTAssertTrue(fx.route.alternates.isEmpty)
        XCTAssertTrue(fx.route.waypoints.isEmpty)
    }

    // MARK: - Round-trip invariant

    func testFullRoundTrip() throws {
        let data = try loadFixture("full.json")
        let original = try FlightExchange.decode(from: data)
        let reencoded = try original.encoded()
        let restored = try FlightExchange.decode(from: reencoded)

        assertEqual(restored, original)
    }

    func testMinimalRoundTrip() throws {
        let data = try loadFixture("minimal.json")
        let original = try FlightExchange.decode(from: data)
        let reencoded = try original.encoded()
        let restored = try FlightExchange.decode(from: reencoded)

        assertEqual(restored, original)
    }

    func testMemberwiseRoundTrip() throws {
        let route = Route(
            departure: "EGTK",
            destination: "LSGS",
            alternates: ["LSGG"],
            waypoints: ["BILGO"],
            departureCoords: [51.83, -1.32],
            destinationCoords: [46.22, 7.33],
            aircraftType: "P28A",
            departureTime: Date(timeIntervalSince1970: 1_780_000_000),
            cruiseAltitudeFt: 8000
        )
        let original = FlightExchange(
            route: route,
            name: "Test",
            source: FlightExchange.Source(app: "forms", flightId: "f-1"),
            aircraft: FlightExchange.Aircraft(registration: "G-ABCD", type: "P28A")
        )
        let restored = try FlightExchange.decode(from: original.encoded())
        assertEqual(restored, original)
    }

    // MARK: - Defaults

    func testSchemaVersionDefaultsWhenMissing() throws {
        let json = """
        { "route": { "departure": "EGTF", "destination": "EGLL" } }
        """.data(using: .utf8)!
        let fx = try FlightExchange.decode(from: json)
        XCTAssertEqual(fx.schemaVersion, FlightExchange.currentSchemaVersion)
    }

    /// A payload from a newer (unknown) schema version is rejected rather than
    /// silently decoded — the design doc says consumers reject unknown versions.
    func testRejectsNewerSchemaVersion() throws {
        let json = """
        { "schema_version": 999, "route": { "departure": "EGTF", "destination": "EGLL" } }
        """.data(using: .utf8)!
        XCTAssertThrowsError(try FlightExchange.decode(from: json))
    }

    // MARK: - Helpers

    private func assertEqual(_ a: FlightExchange, _ b: FlightExchange,
                             file: StaticString = #file, line: UInt = #line) {
        XCTAssertEqual(a.schemaVersion, b.schemaVersion, file: file, line: line)
        XCTAssertEqual(a.name, b.name, file: file, line: line)
        XCTAssertEqual(a.source?.app, b.source?.app, file: file, line: line)
        XCTAssertEqual(a.source?.flightId, b.source?.flightId, file: file, line: line)
        XCTAssertEqual(a.source?.shareCode, b.source?.shareCode, file: file, line: line)
        XCTAssertEqual(a.aircraft?.registration, b.aircraft?.registration, file: file, line: line)
        XCTAssertEqual(a.aircraft?.type, b.aircraft?.type, file: file, line: line)
        XCTAssertEqual(a.route.departure, b.route.departure, file: file, line: line)
        XCTAssertEqual(a.route.destination, b.route.destination, file: file, line: line)
        XCTAssertEqual(a.route.alternates, b.route.alternates, file: file, line: line)
        XCTAssertEqual(a.route.waypoints, b.route.waypoints, file: file, line: line)
        XCTAssertEqual(a.route.aircraftType, b.route.aircraftType, file: file, line: line)
        XCTAssertEqual(a.route.cruiseAltitudeFt, b.route.cruiseAltitudeFt, file: file, line: line)
        XCTAssertEqual(a.route.flightLevel, b.route.flightLevel, file: file, line: line)
        XCTAssertEqual(a.route.departureTime, b.route.departureTime, file: file, line: line)
        XCTAssertEqual(a.route.arrivalTime, b.route.arrivalTime, file: file, line: line)
        XCTAssertEqual(a.route.waypointCoords, b.route.waypointCoords, file: file, line: line)
    }
}
