//
//  NotamCategory.swift
//  RZFlight
//
//  ICAO NOTAM category enumeration based on Q-code subject first letter.
//  Matches the categories defined in q_codes.json for consistency.
//

import Foundation

/// ICAO NOTAM categories based on Q-code subject first letter.
///
/// These are standard ICAO categories derived from the Q-code structure.
/// The first letter of the 2-letter subject code determines the category.
///
/// Example: QMRLC → subject "MR" → first letter "M" → .agaMovement
public enum NotamCategory: String, Codable, CaseIterable, Sendable {
    /// ATM Airspace Organization (A* codes)
    /// Includes: FIR, TMA, CTR, ATS routes, reporting points
    case atmAirspace = "A"

    /// CNS Communications and Surveillance (C* codes)
    /// Includes: Radar, ADS-B, CPDLC, SELCAL
    case cnsCommunications = "C"

    /// AGA Facilities and Services (F* codes)
    /// Includes: Aerodrome, fuel, fire/rescue, de-icing, helicopter facilities
    case agaFacilities = "F"

    /// CNS GNSS Services (G* codes)
    /// Includes: GNSS airfield and area-wide operations
    case cnsGNSS = "G"

    /// CNS ILS/MLS (I* codes)
    /// Includes: ILS, localizer, glide path, markers, MLS
    case cnsILS = "I"

    /// AGA Lighting (L* codes)
    /// Includes: ALS, PAPI, VASIS, runway/taxiway lights, heliport lighting
    case agaLighting = "L"

    /// AGA Movement Area (M* codes)
    /// Includes: Runway, taxiway, apron, parking, threshold
    case agaMovement = "M"

    /// Navigation Facilities (N* codes)
    /// Includes: VOR, DME, NDB, TACAN, VORTAC
    case navigation = "N"

    /// Other Information (O* codes)
    /// Includes: Obstacles, obstacle lights, AIS, entry requirements
    case otherInfo = "O"

    /// ATM Procedures (P* codes)
    /// Includes: SID, STAR, holding, instrument approaches, missed approach
    case atmProcedures = "P"

    /// Airspace Restrictions (R* codes)
    /// Includes: Danger areas, prohibited areas, restricted areas, TRA
    case airspaceRestrictions = "R"

    /// ATM Services (S* codes)
    /// Includes: ATIS, ACC, TWR, approach control, ground control
    case atmServices = "S"

    /// Human-readable display name
    public var displayName: String {
        switch self {
        case .atmAirspace: return "Airspace"
        case .cnsCommunications: return "Communications"
        case .agaFacilities: return "Facilities"
        case .cnsGNSS: return "GNSS"
        case .cnsILS: return "ILS/MLS"
        case .agaLighting: return "Lighting"
        case .agaMovement: return "Movement Area"
        case .navigation: return "Navigation"
        case .otherInfo: return "Other"
        case .atmProcedures: return "Procedures"
        case .airspaceRestrictions: return "Restrictions"
        case .atmServices: return "Services"
        }
    }

    /// Short display name for compact UI
    public var shortName: String {
        switch self {
        case .atmAirspace: return "Airspace"
        case .cnsCommunications: return "Comms"
        case .agaFacilities: return "Facilities"
        case .cnsGNSS: return "GNSS"
        case .cnsILS: return "ILS"
        case .agaLighting: return "Lighting"
        case .agaMovement: return "Movement"
        case .navigation: return "Nav"
        case .otherInfo: return "Other"
        case .atmProcedures: return "Procedures"
        case .airspaceRestrictions: return "Restrict"
        case .atmServices: return "Services"
        }
    }

    /// SF Symbol icon for UI
    public var icon: String {
        switch self {
        case .atmAirspace: return "square.3.layers.3d"
        case .cnsCommunications: return "antenna.radiowaves.left.and.right"
        case .agaFacilities: return "building.2"
        case .cnsGNSS: return "location.circle"
        case .cnsILS: return "arrow.down.to.line"
        case .agaLighting: return "lightbulb"
        case .agaMovement: return "road.lanes"
        case .navigation: return "location.north"
        case .otherInfo: return "info.circle"
        case .atmProcedures: return "arrow.triangle.turn.up.right.diamond"
        case .atmServices: return "headphones"
        case .airspaceRestrictions: return "exclamationmark.triangle"
        }
    }

    /// Create category from Q-code subject (2-letter code)
    ///
    /// - Parameter subject: 2-letter Q-code subject (e.g., "MR", "IC", "OB")
    /// - Returns: Category based on first letter, or nil if invalid
    public static func from(qCodeSubject subject: String) -> NotamCategory? {
        guard let firstChar = subject.first else { return nil }
        return NotamCategory(rawValue: String(firstChar).uppercased())
    }

    /// Create category from full Q-code (5-letter code)
    ///
    /// - Parameter qCode: 5-letter Q-code (e.g., "QMRLC")
    /// - Returns: Category based on subject first letter, or nil if invalid
    public static func from(qCode: String) -> NotamCategory? {
        // Q-code format: Q + 2-letter subject + 2-letter condition
        // Extract subject (characters at index 1-2)
        guard qCode.count >= 3 else { return nil }
        let startIndex = qCode.index(qCode.startIndex, offsetBy: 1)
        let subject = String(qCode[startIndex])
        return NotamCategory(rawValue: subject.uppercased())
    }
}
