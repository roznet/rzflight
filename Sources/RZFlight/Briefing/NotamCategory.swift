//
//  NotamCategory.swift
//  RZFlight
//
//  NOTAM category enumeration matching Python euro_aip.briefing
//

import Foundation

/// NOTAM categories based on ICAO Q-code first two letters.
///
/// These are standard ICAO categories derived from the Q-code.
/// Matches Python `NotamCategory` enum for JSON interoperability.
public enum NotamCategory: String, Codable, CaseIterable, Sendable {
    case movementArea = "MX"    // Taxiway, apron, movement area
    case lighting = "LX"        // Lighting systems
    case navigation = "NA"      // Navigation aids (VOR, ILS, DME)
    case communication = "CO"   // Communication facilities
    case airspace = "AR"        // Airspace restrictions, TFRs
    case runway = "RW"          // Runway related
    case obstacle = "OB"        // Obstacles (cranes, towers)
    case procedure = "PI"       // Instrument procedures (SID, STAR, approach)
    case services = "SE"        // Services (fuel, ATC)
    case warning = "WA"         // Warnings
    case other = "XX"           // Other/unknown

    /// Human-readable description
    public var displayName: String {
        switch self {
        case .movementArea: return "Movement Area"
        case .lighting: return "Lighting"
        case .navigation: return "Navigation"
        case .communication: return "Communication"
        case .airspace: return "Airspace"
        case .runway: return "Runway"
        case .obstacle: return "Obstacle"
        case .procedure: return "Procedure"
        case .services: return "Services"
        case .warning: return "Warning"
        case .other: return "Other"
        }
    }
}
