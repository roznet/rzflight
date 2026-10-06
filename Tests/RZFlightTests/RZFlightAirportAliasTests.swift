//
//  RZFlightAirportAliasTests.swift
//
//  An airport stored under its current ICAO code stays findable by its previous
//  one (alt_ident), as Python's EuroAipModel.find_airport_by_code.
//

import XCTest
import FMDB
@testable import RZFlight

final class RZFlightAirportAliasTests: XCTestCase {

    /// In-memory airports.db holding LERJ (formerly LELO) and LEMD, with the
    /// alt_ident column the Python build writes.
    private func makeDB() -> FMDatabase {
        let db = FMDatabase()
        db.open()
        db.executeStatements("""
            CREATE TABLE airports (
                icao_code TEXT PRIMARY KEY, name TEXT, type TEXT,
                latitude_deg REAL, longitude_deg REAL, elevation_ft INTEGER,
                continent TEXT, iso_country TEXT, municipality TEXT, alt_ident TEXT
            );
            CREATE TABLE runways (
                id INTEGER PRIMARY KEY, airport_icao TEXT, le_ident TEXT, he_ident TEXT,
                length_ft INTEGER, width_ft INTEGER, surface TEXT, lighted INTEGER, closed INTEGER,
                le_latitude_deg REAL, le_longitude_deg REAL, le_elevation_ft REAL,
                le_heading_degT REAL, le_displaced_threshold_ft REAL,
                he_latitude_deg REAL, he_longitude_deg REAL, he_elevation_ft REAL,
                he_heading_degT REAL, he_displaced_threshold_ft REAL
            );
            INSERT INTO airports VALUES ('LERJ', 'Logroño-Agoncillo Airport', 'medium_airport',
                42.4610, -2.3222, 1161, 'EU', 'ES', 'Logroño', 'LELO');
            INSERT INTO airports VALUES ('LEMD', 'Adolfo Suárez Madrid–Barajas Airport', 'large_airport',
                40.4719, -3.5626, 1998, 'EU', 'ES', 'Madrid', NULL);
            INSERT INTO runways (airport_icao, le_ident, he_ident, length_ft, width_ft, surface,
                lighted, closed, le_heading_degT, he_heading_degT)
                VALUES ('LERJ', '11', '29', 6562, 148, 'ASP', 1, 0, 113.0, 293.0);
            """)
        return db
    }

    func testAirportFromDBByPreviousCode() throws {
        let db = makeDB()
        defer { db.close() }

        let airport = try Airport(db: db, ident: "LELO")
        XCTAssertEqual(airport.icao, "LERJ")
        XCTAssertEqual(airport.altIdent, "LELO")
        XCTAssertEqual(airport.name, "Logroño-Agoncillo Airport")
        XCTAssertEqual(airport.runways.count, 1)
    }

    func testAirportFromDBIsCaseInsensitiveAndReturnsDBCode() throws {
        let db = makeDB()
        defer { db.close() }

        XCTAssertEqual(try Airport(db: db, ident: "lerj").icao, "LERJ")
        XCTAssertEqual(try Airport(db: db, ident: " lelo ").icao, "LERJ")
        let madrid = try Airport(db: db, ident: "lemd")
        XCTAssertEqual(madrid.icao, "LEMD")
        XCTAssertNil(madrid.altIdent)
        XCTAssertThrowsError(try Airport(db: db, ident: "EGTN"))
    }

    func testKnownAirportsByPreviousCode() {
        let db = makeDB()
        defer { db.close() }
        let known = KnownAirports(db: db)

        XCTAssertEqual(known.airport(icao: "LELO", ensureRunway: false)?.icao, "LERJ")
        XCTAssertEqual(known.airport(icao: "lelo", ensureRunway: true)?.runways.count, 1)
        XCTAssertEqual(known.airport(icao: "lemd", ensureRunway: false)?.icao, "LEMD")
        XCTAssertEqual(known.airportWithExtendedData(icao: "LELO")?.icao, "LERJ")
        XCTAssertNil(known.knownAirport(code: "EGTN"))
    }

    func testExactCodeWinsOverPreviousCode() {
        let db = makeDB()
        defer { db.close() }
        // EKAB was previously EKBH, but EKBH is also a current code.
        db.executeStatements("""
            INSERT INTO airports (icao_code, name, latitude_deg, longitude_deg, alt_ident)
                VALUES ('EKBH', 'Bolhede Glider Field', 55.96, 8.81, NULL);
            INSERT INTO airports (icao_code, name, latitude_deg, longitude_deg, alt_ident)
                VALUES ('EKAB', 'Arnborg', 56.00, 9.00, 'EKBH');
            """)

        XCTAssertEqual(KnownAirports(db: db).knownAirport(code: "EKBH")?.name, "Bolhede Glider Field")
        XCTAssertEqual(try Airport(db: db, ident: "EKBH").name, "Bolhede Glider Field")
    }

    func testRouteResolverNamesPreviousCodeByCurrentCode() {
        let db = makeDB()
        defer { db.close() }
        let resolver = RoutePointResolver(airports: KnownAirports(db: db))

        let point = resolver.resolve("LELO")
        XCTAssertEqual(point?.name, "LERJ")
        XCTAssertEqual(point?.pointType, "airport")
    }

    func testDatabaseWithoutAltIdentColumn() throws {
        // The bundled sample predates alt_ident: lookups by current code still work.
        guard let db = TestSupport.shared.db, let known = TestSupport.shared.known else {
            XCTFail("No database available")
            return
        }
        let egtf = try Airport(db: db, ident: "egtf")
        XCTAssertEqual(egtf.icao, "EGTF")
        XCTAssertNil(egtf.altIdent)
        XCTAssertEqual(known.airport(icao: "egtf", ensureRunway: false)?.icao, "EGTF")
        XCTAssertThrowsError(try Airport(db: db, ident: "LELO"))
    }

    func testAltIdentCodableRoundTrip() throws {
        let db = makeDB()
        defer { db.close() }
        let airport = try Airport(db: db, ident: "LELO")

        let decoded = try JSONDecoder().decode(Airport.self, from: JSONEncoder().encode(airport))
        XCTAssertEqual(decoded.altIdent, "LELO")
        XCTAssertEqual(decoded.icao, "LERJ")
    }
}
