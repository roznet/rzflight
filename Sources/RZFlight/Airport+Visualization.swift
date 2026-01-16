//
//  Airport+Visualization.swift
//  RZFlight
//
//  Procedure visualization extensions for Airport
//

import Foundation
import CoreLocation

extension Airport {

    // MARK: - Procedure Lines

    /// Procedure line data for visualization
    public struct ProcedureLine: Codable {
        public let runwayEnd: String
        public let startCoordinate: CLLocationCoordinate2D
        public let endCoordinate: CLLocationCoordinate2D
        public let approachType: Procedure.ApproachType
        public let procedureName: String
        public let precisionCategory: Procedure.PrecisionCategory
        public let distanceNm: Double

        public init(runwayEnd: String,
                   startCoordinate: CLLocationCoordinate2D,
                   endCoordinate: CLLocationCoordinate2D,
                   approachType: Procedure.ApproachType,
                   procedureName: String,
                   precisionCategory: Procedure.PrecisionCategory,
                   distanceNm: Double) {
            self.runwayEnd = runwayEnd
            self.startCoordinate = startCoordinate
            self.endCoordinate = endCoordinate
            self.approachType = approachType
            self.procedureName = procedureName
            self.precisionCategory = precisionCategory
            self.distanceNm = distanceNm
        }

        enum CodingKeys: String, CodingKey {
            case runwayEnd = "runway_end"
            case startLat = "start_lat"
            case startLon = "start_lon"
            case endLat = "end_lat"
            case endLon = "end_lon"
            case approachType = "approach_type"
            case procedureName = "procedure_name"
            case precisionCategory = "precision_category"
            case distanceNm = "distance_nm"
        }

        public init(from decoder: Decoder) throws {
            let container = try decoder.container(keyedBy: CodingKeys.self)
            self.runwayEnd = try container.decode(String.self, forKey: .runwayEnd)
            let startLat = try container.decode(Double.self, forKey: .startLat)
            let startLon = try container.decode(Double.self, forKey: .startLon)
            let endLat = try container.decode(Double.self, forKey: .endLat)
            let endLon = try container.decode(Double.self, forKey: .endLon)
            self.startCoordinate = CLLocationCoordinate2D(latitude: startLat, longitude: startLon)
            self.endCoordinate = CLLocationCoordinate2D(latitude: endLat, longitude: endLon)
            self.approachType = try container.decode(Procedure.ApproachType.self, forKey: .approachType)
            self.procedureName = try container.decode(String.self, forKey: .procedureName)
            self.precisionCategory = try container.decode(Procedure.PrecisionCategory.self, forKey: .precisionCategory)
            self.distanceNm = try container.decode(Double.self, forKey: .distanceNm)
        }

        public func encode(to encoder: Encoder) throws {
            var container = encoder.container(keyedBy: CodingKeys.self)
            try container.encode(runwayEnd, forKey: .runwayEnd)
            try container.encode(startCoordinate.latitude, forKey: .startLat)
            try container.encode(startCoordinate.longitude, forKey: .startLon)
            try container.encode(endCoordinate.latitude, forKey: .endLat)
            try container.encode(endCoordinate.longitude, forKey: .endLon)
            try container.encode(approachType, forKey: .approachType)
            try container.encode(procedureName, forKey: .procedureName)
            try container.encode(precisionCategory, forKey: .precisionCategory)
            try container.encode(distanceNm, forKey: .distanceNm)
        }
    }

    /// Procedure lines result structure
    public struct ProcedureLinesResult: Codable {
        public let airportIdent: String
        public let procedureLines: [ProcedureLine]

        enum CodingKeys: String, CodingKey {
            case airportIdent = "airport_ident"
            case procedureLines = "procedure_lines"
        }
    }

    /// Get procedure lines for visualization
    /// - Parameter distanceNm: Distance in nautical miles for the procedure lines (default: 10.0)
    /// - Returns: ProcedureLinesResult containing airport ident and list of procedure line data
    public func procedureLines(distanceNm: Double = 10.0) -> ProcedureLinesResult {
        var lines: [ProcedureLine] = []

        for runway in runways {
            // Process each runway end (le and he)
            let ends: [(end: Runway.RunwayEnd, other: Runway.RunwayEnd)] = [
                (runway.le, runway.he),
                (runway.he, runway.le)
            ]

            for (end, other) in ends {
                // Skip if missing required data
                guard let endCoord = end.coordinate,
                      !end.ident.isEmpty else {
                    continue
                }

                // Get the most precise approach for this runway end
                guard let mostPreciseApproach = mostPreciseApproach(for: end),
                      let approachType = mostPreciseApproach.approachType else {
                    continue
                }

                // Calculate end point using great circle calculation
                // Use the opposite heading (other end's heading) to extend the line
                let endPoint = endCoord.pointFromBearingDistance(
                    bearing: other.headingTrue,
                    distanceNm: distanceNm
                )

                // Create procedure line data
                let lineData = ProcedureLine(
                    runwayEnd: end.ident,
                    startCoordinate: endCoord,
                    endCoordinate: endPoint,
                    approachType: approachType,
                    procedureName: mostPreciseApproach.name,
                    precisionCategory: mostPreciseApproach.precisionCategory,
                    distanceNm: distanceNm
                )

                lines.append(lineData)
            }
        }

        return ProcedureLinesResult(
            airportIdent: icao,
            procedureLines: lines
        )
    }
}

// MARK: - CLLocationCoordinate2D Extension for Great Circle Calculations

extension CLLocationCoordinate2D {
    /// Calculate a new coordinate from this point using bearing and distance (great circle calculation)
    /// - Parameters:
    ///   - bearing: Bearing in degrees (0-360, where 0/360 is North, 90 is East, etc.)
    ///   - distanceNm: Distance in nautical miles
    /// - Returns: A new CLLocationCoordinate2D at the calculated position
    ///
    /// Uses the great circle calculation for accurate navigation distances.
    /// Earth radius: 3440.065 nautical miles (matching Python NavPoint implementation)
    func pointFromBearingDistance(bearing: Double, distanceNm: Double) -> CLLocationCoordinate2D {
        let earthRadiusNm: Double = 3440.065 // Earth's radius in nautical miles

        // Convert to radians
        let lat1 = latitude * .pi / 180.0
        let lon1 = longitude * .pi / 180.0
        let bearingRad = bearing * .pi / 180.0

        // Calculate new latitude
        let lat2 = asin(
            sin(lat1) * cos(distanceNm / earthRadiusNm) +
            cos(lat1) * sin(distanceNm / earthRadiusNm) * cos(bearingRad)
        )

        // Calculate new longitude
        let lon2 = lon1 + atan2(
            sin(bearingRad) * sin(distanceNm / earthRadiusNm) * cos(lat1),
            cos(distanceNm / earthRadiusNm) - sin(lat1) * sin(lat2)
        )

        return CLLocationCoordinate2D(
            latitude: lat2 * 180.0 / .pi,
            longitude: lon2 * 180.0 / .pi
        )
    }
}
