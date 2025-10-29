//
//  Procedure.swift
//  RZFlight
//
//  Created by Brice Rosenzweig on 05/11/2023.
//

import Foundation
import FMDB

public struct Procedure: Codable {
    
    public enum ProcedureType: String, Codable, CaseIterable {
        case approach = "approach"
        case departure = "departure"
        case arrival = "arrival"
    }
    
    public enum ApproachType: String, Codable, CaseIterable {
        case ils = "ILS"
        case rnp = "RNP"
        case rnav = "RNAV"
        case vor = "VOR"
        case ndb = "NDB"
        case loc = "LOC"
        case lda = "LDA"
        case sdf = "SDF"
        
        /// Precision hierarchy (lower number = more precise)
        public var precisionRank: Int {
            switch self {
            case .ils: return 1
            case .rnp: return 2
            case .rnav: return 3
            case .vor: return 4
            case .ndb: return 5
            case .loc: return 6
            case .lda: return 7
            case .sdf: return 8
            }
        }
        
        /// Get precision category following memory requirement
        public var precisionCategory: PrecisionCategory {
            switch self {
            case .ils:
                return .precision
            case .rnp, .rnav:
                return .rnav
            default:
                return .nonPrecision
            }
        }
    }
    
    public enum PrecisionCategory: String, Codable {
        case precision = "precision"
        case rnav = "rnav"
        case nonPrecision = "non-precision"
    }
    
    public let name: String
    public let procedureType: ProcedureType
    public let approachType: ApproachType?
    public let runwayNumber: String?
    public let runwayLetter: String?
    public let runwayIdent: String?
    public let source: String?
    public let authority: String?
    public let rawName: String?
    
    /// Full runway identifier (e.g., "13L")
    public var fullRunwayIdent: String? {
        if let number = runwayNumber {
            if let letter = runwayLetter {
                return "\(number)\(letter)"
            }
            return number
        }
        return runwayIdent
    }
    
    /// Check if this is an approach procedure
    public var isApproach: Bool {
        return procedureType == .approach
    }
    
    /// Check if this is a departure procedure
    public var isDeparture: Bool {
        return procedureType == .departure
    }
    
    /// Check if this is an arrival procedure
    public var isArrival: Bool {
        return procedureType == .arrival
    }
    
    /// Get precision category for approach procedures
    public var precisionCategory: PrecisionCategory {
        return approachType?.precisionCategory ?? .nonPrecision
    }
    
    public init(res: FMResultSet) {
        self.name = res.string(forColumn: "name") ?? ""
        self.procedureType = ProcedureType(rawValue: res.string(forColumn: "procedure_type") ?? "") ?? .approach
        self.approachType = ApproachType(rawValue: res.string(forColumn: "approach_type") ?? "")
        self.runwayNumber = res.string(forColumn: "runway_number")
        self.runwayLetter = res.string(forColumn: "runway_letter")
        self.runwayIdent = res.string(forColumn: "runway_ident")
        self.source = res.string(forColumn: "source")
        self.authority = res.string(forColumn: "authority")
        self.rawName = res.string(forColumn: "raw_name")
    }
    
    public init(name: String, procedureType: ProcedureType, approachType: ApproachType? = nil,
                runwayNumber: String? = nil, runwayLetter: String? = nil, runwayIdent: String? = nil,
                source: String? = nil, authority: String? = nil, rawName: String? = nil) {
        self.name = name
        self.procedureType = procedureType
        self.approachType = approachType
        self.runwayNumber = runwayNumber
        self.runwayLetter = runwayLetter
        self.runwayIdent = runwayIdent
        self.source = source
        self.authority = authority
        self.rawName = rawName
    }
    
    /// Check if this procedure matches a specific runway
    public func matches(runway: Runway) -> Bool {
        guard let fullIdent = fullRunwayIdent else { return false }
        return runway.ident1 == fullIdent || runway.ident2 == fullIdent
    }
    
    /// Check if this procedure matches a runway identifier
    public func matches(runwayIdent: String) -> Bool {
        return fullRunwayIdent == runwayIdent
    }
    
    /// Compare precision with another procedure (for sorting)
    public func isMorePreciseThan(_ other: Procedure) -> Bool {
        guard let thisType = self.approachType,
              let otherType = other.approachType else {
            return false
        }
        return thisType.precisionRank < otherType.precisionRank
    }
}

extension Procedure: Hashable, Equatable, Identifiable {
    public static func ==(lhs: Procedure, rhs: Procedure) -> Bool {
        return lhs.name == rhs.name && 
               lhs.procedureType == rhs.procedureType &&
               lhs.fullRunwayIdent == rhs.fullRunwayIdent
    }
    
    public func hash(into hasher: inout Hasher) {
        hasher.combine(name)
        hasher.combine(procedureType)
        hasher.combine(fullRunwayIdent)
    }
    
    public var id: String {
        return "\(name)_\(procedureType.rawValue)_\(fullRunwayIdent ?? "none")"
    }
}

extension Procedure: CustomStringConvertible {
    public var description: String {
        let runway = fullRunwayIdent ?? "unknown"
        return "Procedure(\(name), \(procedureType.rawValue), runway: \(runway))"
    }
}
