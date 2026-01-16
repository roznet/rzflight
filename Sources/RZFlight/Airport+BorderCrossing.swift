//
//  Airport+BorderCrossing.swift
//  RZFlight
//
//  Border crossing / customs extensions for Airport
//

import Foundation
import FMDB

extension Airport {

    // MARK: - Border Crossing / Point of Entry

    /// Check if this airport is a border crossing point (requires database context)
    public func isBorderCrossing(db: FMDatabase) -> Bool {
        let query = "SELECT COUNT(*) as count FROM border_crossing_points WHERE matched_airport_icao = ? OR icao_code = ?"
        if let result = db.executeQuery(query, withArgumentsIn: [self.icao, self.icao]) {
            if result.next() {
                return result.int(forColumn: "count") > 0
            }
        }
        return false
    }

    /// Check if this airport can be used for customs/border crossing (requires database context)
    public func hasCustoms(db: FMDatabase) -> Bool {
        return isBorderCrossing(db: db)
    }
}
