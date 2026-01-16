//
//  Airport+AIP.swift
//  RZFlight
//
//  AIP entry extensions for Airport
//

import Foundation

extension Airport {

    // MARK: - AIP Entry Access

    /// Get AIP entries by section
    public func aipEntries(for section: AIPEntry.Section) -> [AIPEntry] {
        return aipEntries.filter { $0.section == section }
    }

    /// Get standardized AIP entries
    public var standardizedAIPEntries: [AIPEntry] {
        return aipEntries.filter { $0.isStandardized }
    }

    /// Get AIP entry by field name
    public func aipEntry(for fieldName: String, useStandardized: Bool = true) -> AIPEntry? {
        if useStandardized {
            if let entry = aipEntries.first(where: { $0.standardField?.name == fieldName }) {
                return entry
            }
        }
        return aipEntries.first { $0.field == fieldName }
    }
}
