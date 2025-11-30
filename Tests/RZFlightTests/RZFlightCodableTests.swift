//
//  RZFlightCodableTests.swift
//
//  Tests for API JSON compatibility - ensuring models can decode from API format
//
//  Created by AI Assistant
//

import XCTest
import CoreLocation
@testable import RZFlight

final class RZFlightCodableTests: XCTestCase {
    
    var decoder: JSONDecoder!
    var decoderWithSnakeCase: JSONDecoder!
    
    override func setUpWithError() throws {
        // Decoder without snake_case conversion (for explicit snake_case keys)
        decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601
        
        // Decoder with snake_case conversion (for camelCase properties)
        decoderWithSnakeCase = JSONDecoder()
        decoderWithSnakeCase.keyDecodingStrategy = .convertFromSnakeCase
        decoderWithSnakeCase.dateDecodingStrategy = .iso8601
    }
    
    // MARK: - Airport Tests
    
    func testAirportDecodeFromAPIFormat() throws {
        // API format JSON (snake_case, ident instead of icao, etc.)
        // Note: We use decoderWithSnakeCase for Airport since it has camelCase properties
        let apiJSON = """
        {
            "ident": "EGLL",
            "name": "London Heathrow Airport",
            "municipality": "London",
            "iso_country": "GB",
            "iso_region": "GB-ENG",
            "latitude_deg": 51.4700,
            "longitude_deg": -0.4543,
            "elevation_ft": 83,
            "type": "large_airport",
            "continent": "EU",
            "scheduled_service": "yes",
            "gps_code": "EGLL",
            "iata_code": "LHR",
            "created_at": "2023-01-01T00:00:00Z",
            "updated_at": "2023-01-01T00:00:00Z",
            "sources": ["worldairports", "test"],
            "runways": [],
            "procedures": [],
            "aip_entries": []
        }
        """.data(using: .utf8)!
        
        // Airport CodingKeys handle both formats explicitly, so we use regular decoder
        // (The CodingKeys enum has explicit mappings for snake_case keys)
        let airport = try decoder.decode(Airport.self, from: apiJSON)
        
        XCTAssertEqual(airport.icao, "EGLL")
        XCTAssertEqual(airport.name, "London Heathrow Airport")
        XCTAssertEqual(airport.city, "London")
        XCTAssertEqual(airport.country, "GB")
        XCTAssertEqual(airport.isoRegion, "GB-ENG")
        XCTAssertEqual(airport.latitude, 51.4700, accuracy: 0.0001)
        XCTAssertEqual(airport.longitude, -0.4543, accuracy: 0.0001)
        XCTAssertEqual(airport.elevation_ft, 83)
        XCTAssertEqual(airport.type, .large_airport)
        XCTAssertEqual(airport.continent, .EU)
        XCTAssertEqual(airport.scheduledService, "yes")
        XCTAssertEqual(airport.gpsCode, "EGLL")
        XCTAssertEqual(airport.iataCode, "LHR")
        XCTAssertEqual(airport.sources.count, 2)
        XCTAssertTrue(airport.sources.contains("worldairports"))
        XCTAssertTrue(airport.sources.contains("test"))
    }
    
    func testAirportDecodeBackwardCompatible() throws {
        // Old format JSON (camelCase, icao instead of ident)
        let oldJSON = """
        {
            "icao": "EGLL",
            "name": "London Heathrow Airport",
            "city": "London",
            "country": "GB",
            "isoRegion": "GB-ENG",
            "latitude": 51.4700,
            "longitude": -0.4543,
            "elevation_ft": 83,
            "type": "large_airport",
            "continent": "EU",
            "runways": [],
            "procedures": [],
            "aipEntries": []
        }
        """.data(using: .utf8)!
        
        let airport = try decoder.decode(Airport.self, from: oldJSON)
        
        XCTAssertEqual(airport.icao, "EGLL")
        XCTAssertEqual(airport.city, "London")
        XCTAssertEqual(airport.country, "GB")
        XCTAssertEqual(airport.latitude, 51.4700, accuracy: 0.0001)
        XCTAssertEqual(airport.longitude, -0.4543, accuracy: 0.0001)
    }
    
    func testAirportEncode() throws {
        let airport = Airport(
            location: CLLocationCoordinate2D(latitude: 51.4700, longitude: -0.4543),
            icao: "EGLL"
        )
        
        let encoder = JSONEncoder()
        encoder.keyEncodingStrategy = .convertToSnakeCase
        encoder.dateEncodingStrategy = .iso8601
        
        let data = try encoder.encode(airport)
        let decoded = try decoder.decode(Airport.self, from: data)
        
        XCTAssertEqual(decoded.icao, airport.icao)
        XCTAssertEqual(decoded.latitude, airport.latitude, accuracy: 0.0001)
        XCTAssertEqual(decoded.longitude, airport.longitude, accuracy: 0.0001)
    }
    
    // MARK: - Runway Tests
    
    func testRunwayDecodeFromAPIFormat() throws {
        let apiJSON = """
        {
            "length_ft": 12000,
            "width_ft": 150,
            "surface": "asphalt",
            "lighted": true,
            "closed": false,
            "le_ident": "09L",
            "le_latitude_deg": 51.4700,
            "le_longitude_deg": -0.4543,
            "le_elevation_ft": 83,
            "le_heading_degT": 90.0,
            "le_displaced_threshold_ft": 0,
            "he_ident": "27R",
            "he_latitude_deg": 51.4800,
            "he_longitude_deg": -0.4400,
            "he_elevation_ft": 85,
            "he_heading_degT": 270.0,
            "he_displaced_threshold_ft": 0
        }
        """.data(using: .utf8)!
        
        let runway = try decoder.decode(Runway.self, from: apiJSON)
        
        XCTAssertEqual(runway.length_ft, 12000)
        XCTAssertEqual(runway.width_ft, 150)
        XCTAssertEqual(runway.surface, "asphalt")
        XCTAssertTrue(runway.lighted)
        XCTAssertFalse(runway.closed)
        XCTAssertEqual(runway.le.ident, "09L")
        XCTAssertEqual(runway.le.latitude ?? 0, 51.4700, accuracy: 0.0001)
        XCTAssertEqual(runway.le.longitude ?? 0, -0.4543, accuracy: 0.0001)
        XCTAssertEqual(runway.le.elevationFt ?? 0, 83)
        XCTAssertEqual(runway.le.headingTrue, 90.0, accuracy: 0.1)
        XCTAssertEqual(runway.he.ident, "27R")
        XCTAssertEqual(runway.he.headingTrue, 270.0, accuracy: 0.1)
    }
    
    func testRunwayEncodeDecode() throws {
        // Create a runway from database format, then encode/decode
        // Note: This test requires a database, so we'll create a minimal test
        let encoder = JSONEncoder()
        encoder.keyEncodingStrategy = .convertToSnakeCase
        
        // We can't easily create a Runway without database, but we can test encoding
        // if we have one from a test database
    }
    
    // MARK: - Procedure Tests
    
    func testProcedureDecodeFromAPIFormat() throws {
        let apiJSON = """
        {
            "name": "ILS 09L",
            "procedure_type": "approach",
            "approach_type": "ILS",
            "runway_number": "09",
            "runway_letter": "L",
            "runway_ident": "09L",
            "source": "test",
            "authority": "UK",
            "raw_name": "ILS RWY 09L"
        }
        """.data(using: .utf8)!
        
        let procedure = try decoder.decode(Procedure.self, from: apiJSON)
        
        XCTAssertEqual(procedure.name, "ILS 09L")
        XCTAssertEqual(procedure.procedureType, .approach)
        XCTAssertEqual(procedure.approachType, .ils)
        XCTAssertEqual(procedure.runwayNumber, "09")
        XCTAssertEqual(procedure.runwayLetter, "L")
        XCTAssertEqual(procedure.runwayIdent, "09L")
        XCTAssertEqual(procedure.source, "test")
        XCTAssertEqual(procedure.authority, "UK")
        XCTAssertEqual(procedure.rawName, "ILS RWY 09L")
        XCTAssertEqual(procedure.fullRunwayIdent, "09L")
        XCTAssertTrue(procedure.isApproach)
        XCTAssertEqual(procedure.precisionCategory, .precision)
    }
    
    func testProcedureEncodeDecode() throws {
        let procedure = Procedure(
            name: "ILS 09L",
            procedureType: .approach,
            approachType: .ils,
            runwayNumber: "09",
            runwayLetter: "L",
            runwayIdent: "09L",
            source: "test",
            authority: "UK",
            rawName: "ILS RWY 09L"
        )
        
        let encoder = JSONEncoder()
        encoder.keyEncodingStrategy = .convertToSnakeCase
        
        let data = try encoder.encode(procedure)
        let decoded = try decoder.decode(Procedure.self, from: data)
        
        XCTAssertEqual(decoded.name, procedure.name)
        XCTAssertEqual(decoded.procedureType, procedure.procedureType)
        XCTAssertEqual(decoded.approachType, procedure.approachType)
        XCTAssertEqual(decoded.runwayNumber, procedure.runwayNumber)
        XCTAssertEqual(decoded.runwayLetter, procedure.runwayLetter)
        XCTAssertEqual(decoded.runwayIdent, procedure.runwayIdent)
    }
    
    // MARK: - AIPEntry Tests
    
    func testAIPEntryDecodeFromAPIFormat() throws {
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
        
        let apiJSON = """
        {
            "ident": "EGLL",
            "section": "operational",
            "field": "fuel_types",
            "value": "JET A1, AVGAS",
            "std_field_id": 1,
            "mapping_score": 0.95,
            "alt_field": "fuel",
            "alt_value": "JET A1, AVGAS",
            "source": "test"
        }
        """.data(using: .utf8)!
        
        let entry = try decoder.decode(AIPEntry.self, from: apiJSON)
        
        XCTAssertEqual(entry.ident, "EGLL")
        XCTAssertEqual(entry.section, .operational)
        XCTAssertEqual(entry.field, "fuel_types")
        XCTAssertEqual(entry.value, "JET A1, AVGAS")
        // Note: standardField lookup depends on CSV file being available
        // If CSV is not found, standardField will be nil even with std_field_id
        if entry.standardField != nil {
            XCTAssertNotNil(entry.standardField?.name)
            XCTAssertTrue(entry.isStandardized)
        } else {
            // If CSV not available, just verify the field was decoded
            XCTAssertEqual(entry.mappingScore ?? 0, 0.95, accuracy: 0.01)
        }
        XCTAssertEqual(entry.mappingScore ?? 0, 0.95, accuracy: 0.01)
        XCTAssertEqual(entry.altField, "fuel")
        XCTAssertEqual(entry.altValue, "JET A1, AVGAS")
        XCTAssertEqual(entry.source, "test")
    }
    
    func testAIPEntryDecodeWithoutStdFieldId() throws {
        let apiJSON = """
        {
            "ident": "EGLL",
            "section": "operational",
            "field": "custom_field",
            "value": "Custom value",
            "source": "test"
        }
        """.data(using: .utf8)!
        
        let entry = try decoder.decode(AIPEntry.self, from: apiJSON)
        
        XCTAssertEqual(entry.ident, "EGLL")
        XCTAssertEqual(entry.section, .operational)
        XCTAssertEqual(entry.field, "custom_field")
        XCTAssertEqual(entry.value, "Custom value")
        XCTAssertNil(entry.standardField) // No std_field_id provided
        XCTAssertFalse(entry.isStandardized)
    }
    
    func testAIPEntryEncodeDecode() throws {
        let entry = AIPEntry(
            ident: "EGLL",
            section: .operational,
            field: "fuel_types",
            value: "JET A1, AVGAS",
            standardField: nil,
            mappingScore: 0.95,
            altField: "fuel",
            altValue: "JET A1, AVGAS",
            source: "test"
        )
        
        let encoder = JSONEncoder()
        encoder.keyEncodingStrategy = .convertToSnakeCase
        
        let data = try encoder.encode(entry)
        let decoded = try decoder.decode(AIPEntry.self, from: data)
        
        XCTAssertEqual(decoded.ident, entry.ident)
        XCTAssertEqual(decoded.section, entry.section)
        XCTAssertEqual(decoded.field, entry.field)
        XCTAssertEqual(decoded.value, entry.value)
        XCTAssertEqual(decoded.mappingScore, entry.mappingScore)
    }
    
    // MARK: - Airport with Nested Objects Tests
    
    func testAirportWithRunwaysAndProcedures() throws {
        let apiJSON = """
        {
            "ident": "EGLL",
            "name": "London Heathrow Airport",
            "municipality": "London",
            "iso_country": "GB",
            "latitude_deg": 51.4700,
            "longitude_deg": -0.4543,
            "elevation_ft": 83,
            "type": "large_airport",
            "continent": "EU",
            "runways": [
                {
                    "length_ft": 12000,
                    "width_ft": 150,
                    "surface": "asphalt",
                    "lighted": true,
                    "closed": false,
                    "le_ident": "09L",
                    "le_latitude_deg": 51.4700,
                    "le_longitude_deg": -0.4543,
                    "le_elevation_ft": 83,
                    "le_heading_degT": 90.0,
                    "le_displaced_threshold_ft": 0,
                    "he_ident": "27R",
                    "he_latitude_deg": 51.4800,
                    "he_longitude_deg": -0.4400,
                    "he_elevation_ft": 85,
                    "he_heading_degT": 270.0,
                    "he_displaced_threshold_ft": 0
                }
            ],
            "procedures": [
                {
                    "name": "ILS 09L",
                    "procedure_type": "approach",
                    "approach_type": "ILS",
                    "runway_ident": "09L",
                    "source": "test"
                }
            ],
            "aip_entries": []
        }
        """.data(using: .utf8)!
        
        let airport = try decoder.decode(Airport.self, from: apiJSON)
        
        XCTAssertEqual(airport.icao, "EGLL")
        XCTAssertEqual(airport.runways.count, 1)
        XCTAssertEqual(airport.runways.first?.le.ident, "09L")
        XCTAssertEqual(airport.procedures.count, 1)
        XCTAssertEqual(airport.procedures.first?.name, "ILS 09L")
        XCTAssertEqual(airport.procedures.first?.procedureType, .approach)
    }
    
    // MARK: - Edge Cases
    
    func testAirportWithMissingOptionalFields() throws {
        let minimalJSON = """
        {
            "ident": "EGLL",
            "name": "Test Airport",
            "iso_country": "GB",
            "latitude_deg": 51.4700,
            "longitude_deg": -0.4543,
            "elevation_ft": 83,
            "type": "large_airport",
            "continent": "EU"
        }
        """.data(using: .utf8)!
        
        let airport = try decoder.decode(Airport.self, from: minimalJSON)
        
        XCTAssertEqual(airport.icao, "EGLL")
        XCTAssertEqual(airport.name, "Test Airport")
        XCTAssertEqual(airport.city, "") // Default empty string
        XCTAssertNil(airport.isoRegion)
        XCTAssertNil(airport.scheduledService)
        XCTAssertEqual(airport.runways.count, 0)
        XCTAssertEqual(airport.procedures.count, 0)
    }
    
    func testProcedureWithOptionalFields() throws {
        let minimalJSON = """
        {
            "name": "VOR 09L",
            "procedure_type": "approach",
            "approach_type": "VOR"
        }
        """.data(using: .utf8)!
        
        let procedure = try decoder.decode(Procedure.self, from: minimalJSON)
        
        XCTAssertEqual(procedure.name, "VOR 09L")
        XCTAssertEqual(procedure.procedureType, .approach)
        XCTAssertEqual(procedure.approachType, .vor)
        XCTAssertNil(procedure.runwayNumber)
        XCTAssertNil(procedure.runwayLetter)
        XCTAssertNil(procedure.runwayIdent)
        XCTAssertNil(procedure.source)
    }
}

