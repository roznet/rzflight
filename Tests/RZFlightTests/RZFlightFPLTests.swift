//
//  RZFlightFPLTests.swift
//  RZFlightTests
//
//  Tests for ICAOFlightPlanParser.
//

import XCTest
@testable import RZFlight
import CoreLocation

final class RZFlightFPLTests: XCTestCase {

    // MARK: - Sample FPL Strings

    static let sampleFPL = """
    (FPL-N122DR-VG
    -S22T/L-SBDGORVY/LB2
    -LFAT0930
    -N0166VFR DCT LYD DCT VESAN 4830N00210E DCT
    -EGTF0033 EGLL
    -PBN/B2C2D2 DOF/260318 RMK/FIKI EQUIPPED)
    """

    static let sampleIFR = """
    (FPL-GZIPM-IS
    -C172/L-S/C
    -EGTF1030
    -N0110F065 HAZEL UL9 ORTAC L28 DINARD
    -LFAT0130
    -DOF/260326 PBN/D2)
    """

    static let sampleMinimal = """
    (FPL-GABCD-VG
    -PA28/L
    -EGLL0800
    -N0120VFR DCT
    -EGSS0025
    -0)
    """

    static let sampleMetric = """
    (FPL-HBXYZ-VG
    -P28A/L-S/C
    -LSGG0900
    -K0200A055 DCT GVA DCT
    -LSZH0045
    -DOF/260401)
    """

    // MARK: - No FPL

    func testReturnsNilForNoFPL() {
        XCTAssertNil(ICAOFlightPlanParser.parse("no flight plan here"))
    }

    func testReturnsNilForEmpty() {
        XCTAssertNil(ICAOFlightPlanParser.parse(""))
    }

    // MARK: - Basic Parsing

    func testBasicFields() {
        let fpl = ICAOFlightPlanParser.parse(Self.sampleFPL)!
        XCTAssertEqual(fpl.aircraftRegistration, "N122DR")
        XCTAssertEqual(fpl.aircraftType, "S22T")
        XCTAssertEqual(fpl.flightRules, "V")
        XCTAssertEqual(fpl.flightType, "G")
    }

    func testDeparture() {
        let fpl = ICAOFlightPlanParser.parse(Self.sampleFPL)!
        XCTAssertEqual(fpl.route.departure, "LFAT")
    }

    func testDepartureTime() {
        let fpl = ICAOFlightPlanParser.parse(Self.sampleFPL)!
        XCTAssertEqual(fpl.departureTimeUTC?.hour, 9)
        XCTAssertEqual(fpl.departureTimeUTC?.minute, 30)
    }

    func testDestination() {
        let fpl = ICAOFlightPlanParser.parse(Self.sampleFPL)!
        XCTAssertEqual(fpl.route.destination, "EGTF")
    }

    func testEET() {
        let fpl = ICAOFlightPlanParser.parse(Self.sampleFPL)!
        XCTAssertEqual(fpl.eetMinutes, 33)
    }

    func testAlternates() {
        let fpl = ICAOFlightPlanParser.parse(Self.sampleFPL)!
        XCTAssertEqual(fpl.route.alternates, ["EGLL"])
    }

    func testSpeed() {
        let fpl = ICAOFlightPlanParser.parse(Self.sampleFPL)!
        XCTAssertEqual(fpl.speed, "N0166")
        XCTAssertEqual(fpl.speedKnots, 166)
    }

    func testVFRLevel() {
        let fpl = ICAOFlightPlanParser.parse(Self.sampleFPL)!
        XCTAssertEqual(fpl.level, "VFR")
        XCTAssertNil(fpl.altitudeFeet)
    }

    func testEquipment() {
        let fpl = ICAOFlightPlanParser.parse(Self.sampleFPL)!
        XCTAssertEqual(fpl.equipment, "SBDGORVY")
        XCTAssertEqual(fpl.surveillance, "LB2")
    }

    func testDateOfFlight() {
        // DOF/260318 = YYMMDD = 2026-03-18
        let fpl = ICAOFlightPlanParser.parse(Self.sampleFPL)!
        XCTAssertNotNil(fpl.dateOfFlight)
        let cal = Calendar(identifier: .gregorian)
        let components = cal.dateComponents(in: TimeZone(identifier: "UTC")!, from: fpl.dateOfFlight!)
        XCTAssertEqual(components.year, 2026)
        XCTAssertEqual(components.month, 3)
        XCTAssertEqual(components.day, 18)
    }

    func testPBNCodes() {
        let fpl = ICAOFlightPlanParser.parse(Self.sampleFPL)!
        XCTAssertNotNil(fpl.pbnCodes)
        XCTAssertTrue(fpl.pbnCodes!.contains("B2C2D2"))
    }

    func testRemarks() {
        let fpl = ICAOFlightPlanParser.parse(Self.sampleFPL)!
        XCTAssertNotNil(fpl.remarks)
        XCTAssertTrue(fpl.remarks!.contains("FIKI"))
    }

    // MARK: - Derived Properties

    func testIsVFR() {
        let fpl = ICAOFlightPlanParser.parse(Self.sampleFPL)!
        XCTAssertTrue(fpl.isVFR)
        XCTAssertFalse(fpl.isIFR)
    }

    func testIsIFR() {
        let fpl = ICAOFlightPlanParser.parse(Self.sampleIFR)!
        XCTAssertTrue(fpl.isIFR)
        XCTAssertFalse(fpl.isVFR)
    }

    func testHasGNSS() {
        let fpl = ICAOFlightPlanParser.parse(Self.sampleFPL)!
        XCTAssertTrue(fpl.hasGNSS)
    }

    func testHasADSB() {
        let fpl = ICAOFlightPlanParser.parse(Self.sampleFPL)!
        XCTAssertTrue(fpl.hasADSB)
    }

    func testHasRNAV() {
        let fpl = ICAOFlightPlanParser.parse(Self.sampleFPL)!
        XCTAssertTrue(fpl.hasRNAV)
    }

    func testHasRVSM() {
        let fpl = ICAOFlightPlanParser.parse(Self.sampleFPL)!
        XCTAssertFalse(fpl.hasRVSM)
    }

    // MARK: - IFR Flight Plan

    func testIFRFields() {
        let fpl = ICAOFlightPlanParser.parse(Self.sampleIFR)!
        XCTAssertEqual(fpl.aircraftRegistration, "GZIPM")
        XCTAssertEqual(fpl.aircraftType, "C172")
        XCTAssertEqual(fpl.flightRules, "I")
        XCTAssertEqual(fpl.flightType, "S")
    }

    func testIFRSpeedAndLevel() {
        let fpl = ICAOFlightPlanParser.parse(Self.sampleIFR)!
        XCTAssertEqual(fpl.speed, "N0110")
        XCTAssertEqual(fpl.speedKnots, 110)
        XCTAssertEqual(fpl.level, "F065")
        XCTAssertEqual(fpl.altitudeFeet, 6500)
    }

    func testIFRAirwaysFiltered() {
        let fpl = ICAOFlightPlanParser.parse(Self.sampleIFR)!
        XCTAssertTrue(fpl.route.waypoints.contains("HAZEL"))
        XCTAssertTrue(fpl.route.waypoints.contains("ORTAC"))
        XCTAssertTrue(fpl.route.waypoints.contains("DINARD"))
        // Airways should not be in waypoints
        XCTAssertFalse(fpl.route.waypoints.contains("UL9"))
        XCTAssertFalse(fpl.route.waypoints.contains("L28"))
    }

    func testIFRDepartureTime() {
        let fpl = ICAOFlightPlanParser.parse(Self.sampleIFR)!
        XCTAssertEqual(fpl.departureTimeUTC?.hour, 10)
        XCTAssertEqual(fpl.departureTimeUTC?.minute, 30)
    }

    func testIFREET() {
        let fpl = ICAOFlightPlanParser.parse(Self.sampleIFR)!
        XCTAssertEqual(fpl.eetMinutes, 90)
    }

    // MARK: - Minimal FPL

    func testMinimalParse() {
        let fpl = ICAOFlightPlanParser.parse(Self.sampleMinimal)!
        XCTAssertEqual(fpl.aircraftRegistration, "GABCD")
        XCTAssertEqual(fpl.route.departure, "EGLL")
        XCTAssertEqual(fpl.route.destination, "EGSS")
    }

    func testMinimalNoEquipment() {
        let fpl = ICAOFlightPlanParser.parse(Self.sampleMinimal)!
        XCTAssertNil(fpl.equipment)
    }

    func testMinimalField18Zero() {
        let fpl = ICAOFlightPlanParser.parse(Self.sampleMinimal)!
        XCTAssertNil(fpl.dateOfFlight)
    }

    // MARK: - Metric Speed

    func testMetricSpeedConversion() {
        let fpl = ICAOFlightPlanParser.parse(Self.sampleMetric)!
        XCTAssertEqual(fpl.speed, "K0200")
        XCTAssertEqual(fpl.speedKnots, Int(round(200.0 / 1.852)))
    }

    func testAltitudeHundredsOfFeet() {
        let fpl = ICAOFlightPlanParser.parse(Self.sampleMetric)!
        XCTAssertEqual(fpl.level, "A055")
        XCTAssertEqual(fpl.altitudeFeet, 5500)
    }

    // MARK: - Route Tokens

    func testGPSCoordinateInRoute() {
        let fpl = ICAOFlightPlanParser.parse(Self.sampleFPL)!
        let gps = fpl.route.waypointCoords.filter { $0.pointType == "gps" }
        XCTAssertEqual(gps.count, 1)
        XCTAssertEqual(gps[0].name, "4830N00210E")
        XCTAssertEqual(gps[0].latitude, 48.5, accuracy: 0.001)
        XCTAssertEqual(gps[0].longitude, 2.1667, accuracy: 0.001)
    }

    func testDCTFiltered() {
        let fpl = ICAOFlightPlanParser.parse(Self.sampleFPL)!
        XCTAssertFalse(fpl.route.waypoints.contains("DCT"))
    }

    func testNamedWaypointsInRoute() {
        let fpl = ICAOFlightPlanParser.parse(Self.sampleFPL)!
        XCTAssertTrue(fpl.route.waypoints.contains("LYD"))
        XCTAssertTrue(fpl.route.waypoints.contains("VESAN"))
    }

    func testRawRoutePreserved() {
        let fpl = ICAOFlightPlanParser.parse(Self.sampleFPL)!
        XCTAssertNotNil(fpl.rawRoute)
        XCTAssertTrue(fpl.rawRoute!.contains("LYD"))
        XCTAssertTrue(fpl.rawRoute!.contains("4830N00210E"))
    }

    // MARK: - Altitude Parsing

    func testParseAltitudeFlightLevel() {
        XCTAssertEqual(ICAOFlightPlanParser.parseAltitude("F350"), 35000)
        XCTAssertEqual(ICAOFlightPlanParser.parseAltitude("F065"), 6500)
    }

    func testParseAltitudeA() {
        XCTAssertEqual(ICAOFlightPlanParser.parseAltitude("A055"), 5500)
        XCTAssertEqual(ICAOFlightPlanParser.parseAltitude("A100"), 10000)
    }

    func testParseAltitudeVFR() {
        XCTAssertNil(ICAOFlightPlanParser.parseAltitude("VFR"))
        XCTAssertNil(ICAOFlightPlanParser.parseAltitude("IFR"))
    }

    func testParseAltitudeMetric() {
        let alt = ICAOFlightPlanParser.parseAltitude("S0850")
        XCTAssertNotNil(alt)
        XCTAssertTrue(alt! > 27000 && alt! < 28000)
    }

    // MARK: - ICAO Coordinate Parsing

    func testICAOCoordDM() {
        let coord = ICAOFlightPlanParser.parseICAOCoordinate("4830N00210E")
        XCTAssertNotNil(coord)
        XCTAssertEqual(coord!.latitude, 48.5, accuracy: 0.001)
        XCTAssertEqual(coord!.longitude, 2.1667, accuracy: 0.001)
    }

    func testICAOCoordDMS() {
        let coord = ICAOFlightPlanParser.parseICAOCoordinate("483012N0021034E")
        XCTAssertNotNil(coord)
        XCTAssertEqual(coord!.latitude, 48.5033, accuracy: 0.001)
        XCTAssertEqual(coord!.longitude, 2.1761, accuracy: 0.001)
    }

    func testICAOCoordSouthWest() {
        let coord = ICAOFlightPlanParser.parseICAOCoordinate("3345S05830W")
        XCTAssertNotNil(coord)
        XCTAssertTrue(coord!.latitude < 0)
        XCTAssertTrue(coord!.longitude < 0)
    }

    func testICAOCoordInvalid() {
        XCTAssertNil(ICAOFlightPlanParser.parseICAOCoordinate("VESAN"))
        XCTAssertNil(ICAOFlightPlanParser.parseICAOCoordinate("DCT"))
    }

    // MARK: - Computed Times

    func testDepartureDateTime() {
        let fpl = ICAOFlightPlanParser.parse(Self.sampleFPL)!
        XCTAssertNotNil(fpl.route.departureTime)
        let cal = Calendar(identifier: .gregorian)
        let comp = cal.dateComponents(in: TimeZone(identifier: "UTC")!, from: fpl.route.departureTime!)
        XCTAssertEqual(comp.year, 2026)
        XCTAssertEqual(comp.month, 3)
        XCTAssertEqual(comp.day, 18)
        XCTAssertEqual(comp.hour, 9)
        XCTAssertEqual(comp.minute, 30)
    }

    func testArrivalDateTime() {
        let fpl = ICAOFlightPlanParser.parse(Self.sampleFPL)!
        XCTAssertNotNil(fpl.route.arrivalTime)
        let cal = Calendar(identifier: .gregorian)
        let comp = cal.dateComponents(in: TimeZone(identifier: "UTC")!, from: fpl.route.arrivalTime!)
        // 09:30 + 33min = 10:03
        XCTAssertEqual(comp.hour, 10)
        XCTAssertEqual(comp.minute, 3)
    }

    func testNoDateNoDateTime() {
        let fpl = ICAOFlightPlanParser.parse(Self.sampleMinimal)!
        XCTAssertNil(fpl.route.departureTime)
    }
}
