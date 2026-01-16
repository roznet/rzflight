//
//  Airport+Procedures.swift
//  RZFlight
//
//  Procedure-related extensions for Airport
//

import Foundation

extension Airport {

    // MARK: - Procedure Filtering

    /// Get all approach procedures
    public var approaches: [Procedure] {
        return procedures.filter { $0.isApproach }
    }

    /// Get all departure procedures
    public var departures: [Procedure] {
        return procedures.filter { $0.isDeparture }
    }

    /// Get all arrival procedures
    public var arrivals: [Procedure] {
        return procedures.filter { $0.isArrival }
    }

    // MARK: - Procedure Queries

    /// Get procedures for a specific runway
    public func procedures(for runway: Runway) -> [Procedure] {
        return procedures.filter { $0.matches(runway: runway) }
    }

    /// Get procedures for a specific runway identifier
    public func procedures(for runwayIdent: String) -> [Procedure] {
        return procedures.filter { $0.matches(runwayIdent: runwayIdent) }
    }

    /// Get approaches for a specific runway
    public func approaches(for runway: Runway) -> [Procedure] {
        return approaches.filter { $0.matches(runway: runway) }
    }

    // MARK: - Most Precise Approach

    /// Get the most precise approach for a runway
    public func mostPreciseApproach(for runway: Runway) -> Procedure? {
        let runwayApproaches = approaches(for: runway)
        return runwayApproaches.min { $0.isMorePreciseThan($1) }
    }

    /// Get the most precise approach for a runway identifier
    public func mostPreciseApproach(for runwayIdent: String) -> Procedure? {
        let runwayApproaches = approaches.filter { $0.matches(runwayIdent: runwayIdent) }
        return runwayApproaches.min { $0.isMorePreciseThan($1) }
    }

    /// Get the most precise approach for a specific runway end
    public func mostPreciseApproach(for runwayEnd: Runway.RunwayEnd) -> Procedure? {
        let runwayEndIdent = runwayEnd.ident
        let runwayApproaches = approaches.filter { $0.matches(runwayIdent: runwayEndIdent) }
        return runwayApproaches.min { $0.isMorePreciseThan($1) }
    }
}
