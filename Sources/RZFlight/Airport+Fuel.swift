//
//  Airport+Fuel.swift
//  RZFlight
//
//  Fuel availability extensions for Airport
//

import Foundation

extension Airport {

    // MARK: - Fuel Availability

    /// Check if airport has AVGAS fuel (from AIP entries)
    /// Looks for "AVGAS" or "100LL" mentions in fuel-related AIP entries
    public var hasAvgas: Bool {
        aipEntries.contains { entry in
            let v = entry.value.uppercased()
            return v.contains("AVGAS") || v.contains("100LL")
        }
    }

    /// Check if airport has Jet-A fuel
    /// Looks for "JET" or "JETA1" mentions in fuel-related AIP entries
    public var hasJetA: Bool {
        aipEntries.contains { entry in
            let v = entry.value.uppercased()
            return v.contains("JET") || v.contains("JETA1")
        }
    }
}

// MARK: - Airport Collection Fuel Filters

extension Array where Element == Airport {

    /// Filter airports to only those with AVGAS fuel
    public func withAvgas() -> [Airport] {
        filter { $0.hasAvgas }
    }

    /// Filter airports to only those with Jet-A fuel
    public func withJetA() -> [Airport] {
        filter { $0.hasJetA }
    }
}
