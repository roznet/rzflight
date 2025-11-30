//
//  AIPEntry.swift
//  RZFlight
//
//  Created by Brice Rosenzweig on 05/11/2023.
//

import Foundation
import FMDB

public struct AIPEntry: Codable {
    
    public struct AIPField: Codable, Hashable {
        public let id: Int
        public let name: String
        public let section: Section
    }
    
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
    
    public enum AIPFieldCatalog {
        private static var overrideURL: URL?
        
        /// Set a custom CSV URL for the field catalog (e.g., in tests). Pass nil to clear and revert to the packaged CSV.
        public static func setOverrideURL(_ url: URL?) {
            overrideURL = url
            cache = loadCatalog()
        }
        
        private static func loadCatalog() -> [Int: AIPField] {
            // Note: When this package is used via SwiftPM with resources, callers should
            // call setOverrideURL(Bundle.module.url(forResource: "aip_fields", withExtension: "csv")).
            // Here we default to the main bundle for non-SPM integration.
            let csvURL: URL? = overrideURL ?? Bundle.module.url(forResource: "aip_fields", withExtension: "csv")
            guard let url = csvURL,
                  let data = try? Data(contentsOf: url),
                  let csv = String(data: data, encoding: .utf8)
            else { return [:] }
            var dict: [Int: AIPField] = [:]
            let lines = csv.split(whereSeparator: \.isNewline)
            guard let header = lines.first else { return [:] }
            let cols = header.split(separator: ",").map { $0.trimmingCharacters(in: .whitespaces) }
            let sectionIdx = cols.firstIndex(of: "section")
            let fieldIdIdx = cols.firstIndex(of: "field_id")
            let fieldNameIdx = cols.firstIndex(of: "field_name")
            for line in lines.dropFirst() {
                let parts = line.split(separator: ",", omittingEmptySubsequences: false)
                guard let sIdx = sectionIdx, let idIdx = fieldIdIdx, let nIdx = fieldNameIdx,
                      parts.indices.contains(sIdx), parts.indices.contains(idIdx), parts.indices.contains(nIdx),
                      let id = Int(parts[idIdx].trimmingCharacters(in: .whitespaces))
                else { continue }
                let sectionRaw = parts[sIdx].trimmingCharacters(in: .whitespaces)
                let name = parts[nIdx].trimmingCharacters(in: .whitespaces)
                guard let section = Section(rawValue: sectionRaw), !name.isEmpty else { continue }
                dict[id] = AIPField(id: id, name: name, section: section)
            }
            return dict
        }
        
        private static var cache: [Int: AIPField] = loadCatalog()
        
        public static func field(for id: Int) -> AIPField? { cache[id] }
    }
    
    public let ident: String
    public let section: Section
    public let field: String
    public let value: String
    public let standardField: AIPField?
    public let mappingScore: Double?
    public let altField: String?
    public let altValue: String?
    public let source: String?
    
    public var isStandardized: Bool { standardField != nil }
    public var effectiveFieldName: String { standardField?.name ?? field }
    public var effectiveValue: String { altValue ?? value }
    
    public init(res: FMResultSet) {
        self.ident = res.string(forColumn: "airport_icao") ?? ""
        let sectionStr = res.string(forColumn: "section") ?? ""
        self.section = Section(rawValue: sectionStr) ?? .operational
        self.field = res.string(forColumn: "field") ?? ""
        self.value = res.string(forColumn: "value") ?? ""
        let stdId = Int(res.int(forColumn: "std_field_id"))
        self.standardField = stdId > 0 ? AIPFieldCatalog.field(for: stdId) : nil
        let score = res.double(forColumn: "mapping_score")
        self.mappingScore = score > 0 ? score : nil
        self.altField = res.string(forColumn: "alt_field")
        self.altValue = res.string(forColumn: "alt_value")
        self.source = res.string(forColumn: "source")
    }
    
    public init(ident: String, section: Section, field: String, value: String,
                standardField: AIPField? = nil, mappingScore: Double? = nil,
                altField: String? = nil, altValue: String? = nil, source: String? = nil) {
        self.ident = ident
        self.section = section
        self.field = field
        self.value = value
        self.standardField = standardField
        self.mappingScore = mappingScore
        self.altField = altField
        self.altValue = altValue
        self.source = source
    }
    
    enum CodingKeys: String, CodingKey {
        case ident
        case section
        case field
        case value
        case std_field_id  // API format - used to lookup standardField
        case std_field  // Alternative API format
        case mappingScore = "mapping_score"  // API format (snake_case)
        case altField = "alt_field"  // API format (snake_case)
        case altValue = "alt_value"  // API format (snake_case)
        case source
    }
    
    public init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        
        self.ident = try container.decode(String.self, forKey: .ident)
        self.section = try container.decode(Section.self, forKey: .section)
        self.field = try container.decode(String.self, forKey: .field)
        self.value = try container.decode(String.self, forKey: .value)
        
        // Handle standardField - API provides std_field_id, we look it up
        if let stdFieldId = try container.decodeIfPresent(Int.self, forKey: .std_field_id), stdFieldId > 0 {
            self.standardField = AIPFieldCatalog.field(for: stdFieldId)
        } else {
            self.standardField = nil
        }
        
        self.mappingScore = try container.decodeIfPresent(Double.self, forKey: .mappingScore)
        self.altField = try container.decodeIfPresent(String.self, forKey: .altField)
        self.altValue = try container.decodeIfPresent(String.self, forKey: .altValue)
        self.source = try container.decodeIfPresent(String.self, forKey: .source)
    }
    
    public func encode(to encoder: Encoder) throws {
        var container = encoder.container(keyedBy: CodingKeys.self)
        
        try container.encode(ident, forKey: .ident)
        try container.encode(section, forKey: .section)
        try container.encode(field, forKey: .field)
        try container.encode(value, forKey: .value)
        
        // Encode std_field_id if we have a standardField
        if let stdField = standardField {
            try container.encode(stdField.id, forKey: .std_field_id)
        }
        
        try container.encodeIfPresent(mappingScore, forKey: .mappingScore)
        try container.encodeIfPresent(altField, forKey: .altField)
        try container.encodeIfPresent(altValue, forKey: .altValue)
        try container.encodeIfPresent(source, forKey: .source)
    }
    
    public var displayDescription: String {
        let fieldName = effectiveFieldName.capitalized
        let sectionName = section.displayName
        return "\(sectionName): \(fieldName)"
    }
}

extension AIPEntry: Hashable, Equatable, Identifiable {
    public static func ==(lhs: AIPEntry, rhs: AIPEntry) -> Bool {
        return lhs.ident == rhs.ident && lhs.section == rhs.section && lhs.field == rhs.field && lhs.source == rhs.source
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
