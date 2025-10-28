//
//  AIPEntry.swift
//  RZFlight
//
//  Created by Brice Rosenzweig on 05/11/2023.
//

import Foundation
import FMDB

public struct AIPEntry: Codable {
    
    public enum Section: String, Codable, CaseIterable {
        case admin = "admin"
        case operational = "operational" 
        case handling = "handling"
        case passenger = "passenger"
        
        public var displayName: String {
            switch self {
            case .admin: return "Administrative"
            case .operational: return "Operational"
            case .handling: return "Handling"
            case .passenger: return "Passenger"
            }
        }
    }
    
    public let ident: String          // ICAO code
    public let section: Section       // admin, operational, handling, passenger
    public let field: String          // Original field name
    public let value: String          // Field value
    public let stdField: String?      // Standardized field name
    public let stdFieldId: Int?       // Standard field ID
    public let mappingScore: Double?  // Similarity score from field mapper
    public let altField: String?      // Field name in alternative language
    public let altValue: String?      // Value in alternative language
    public let source: String?        // Source of the data (e.g., 'uk_eaip', 'france_eaip')
    
    /// Check if this entry has been standardized
    public var isStandardized: Bool {
        return stdField != nil && stdFieldId != nil
    }
    
    /// Get effective field name (standardized if available, otherwise original)
    public var effectiveFieldName: String {
        return stdField ?? field
    }
    
    /// Get effective value (alternative if available, otherwise main)
    public var effectiveValue: String {
        return altValue ?? value
    }
    
    public init(res: FMResultSet) {
        self.ident = res.string(forColumn: "airport_icao") ?? ""
        
        let sectionStr = res.string(forColumn: "section") ?? ""
        self.section = Section(rawValue: sectionStr) ?? .operational
        
        self.field = res.string(forColumn: "field") ?? ""
        self.value = res.string(forColumn: "value") ?? ""
        self.stdField = res.string(forColumn: "std_field")
        
        let fieldId = res.int(forColumn: "std_field_id")
        self.stdFieldId = fieldId > 0 ? Int(fieldId) : nil
        
        let score = res.double(forColumn: "mapping_score")
        self.mappingScore = score > 0 ? score : nil
        
        self.altField = res.string(forColumn: "alt_field")
        self.altValue = res.string(forColumn: "alt_value")
        self.source = res.string(forColumn: "source")
    }
    
    public init(ident: String, section: Section, field: String, value: String,
                stdField: String? = nil, stdFieldId: Int? = nil, mappingScore: Double? = nil,
                altField: String? = nil, altValue: String? = nil, source: String? = nil) {
        self.ident = ident
        self.section = section
        self.field = field
        self.value = value
        self.stdField = stdField
        self.stdFieldId = stdFieldId
        self.mappingScore = mappingScore
        self.altField = altField
        self.altValue = altValue
        self.source = source
    }
    
    /// Get a user-friendly description
    public var displayDescription: String {
        let fieldName = effectiveFieldName.capitalized
        let sectionName = section.displayName
        return "\(sectionName): \(fieldName)"
    }
}

extension AIPEntry: Hashable, Equatable, Identifiable {
    public static func ==(lhs: AIPEntry, rhs: AIPEntry) -> Bool {
        return lhs.ident == rhs.ident &&
               lhs.section == rhs.section &&
               lhs.field == rhs.field &&
               lhs.source == rhs.source
    }
    
    public func hash(into hasher: inout Hasher) {
        hasher.combine(ident)
        hasher.combine(section)
        hasher.combine(field)
        hasher.combine(source)
    }
    
    public var id: String {
        let sourceId = source ?? "unknown"
        return "\(ident)_\(section.rawValue)_\(field)_\(sourceId)"
    }
}

extension AIPEntry: CustomStringConvertible {
    public var description: String {
        let standardized = isStandardized ? " (standardized)" : ""
        return "AIPEntry(\(ident), \(section.rawValue).\(field)\(standardized))"
    }
}
