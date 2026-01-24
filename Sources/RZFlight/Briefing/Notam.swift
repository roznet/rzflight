//
//  Notam.swift
//  RZFlight
//
//  NOTAM data model for flight briefings.
//  Decodes from Python euro_aip.briefing JSON format.
//

import Foundation
import CoreLocation

/// NOTAM (Notice to Airmen) data model.
///
/// Represents a parsed NOTAM with all extracted fields. Designed to decode
/// from JSON produced by Python's `euro_aip.briefing` module.
///
/// Example:
/// ```swift
/// let briefing = try Briefing.load(from: url)
/// let runwayNotams = briefing.notams.forAirport("LFPG").runwayRelated()
/// ```
public struct Notam: Codable, Sendable {

    // MARK: - Identity

    /// Unique NOTAM identifier (e.g., "A1234/24")
    public let id: String

    /// Primary ICAO code from A) line
    public let location: String

    /// Full original NOTAM text
    public let rawText: String

    /// E) line content - the main message
    public let message: String

    /// NOTAM series letter (A, B, C, etc.)
    public let series: String?

    /// NOTAM number within series
    public let number: Int?

    /// NOTAM year (2-digit)
    public let year: Int?

    // MARK: - Location Details

    /// FIR code from Q-line
    public let fir: String?

    /// Additional affected ICAO locations
    public let affectedLocations: [String]

    // MARK: - Q-Line Decoded Fields

    /// 5-letter Q-code (e.g., "QMRLC" for runway closed)
    public let qCode: String?

    /// Traffic type: I (IFR), V (VFR), IV (both)
    public let trafficType: String?

    /// Purpose: N (immediate), B (briefing), O (ops), M (misc), K (checklist)
    public let purpose: String?

    /// Scope: A (aerodrome), E (enroute), W (warning)
    public let scope: String?

    /// Lower altitude limit in feet
    public let lowerLimit: Int?

    /// Upper altitude limit in feet
    public let upperLimit: Int?

    /// Affected radius in nautical miles
    public let radiusNm: Double?

    /// Coordinates (latitude, longitude) - stored as array for Codable
    private let coordinates: [Double]?

    // MARK: - Category

    /// ICAO category derived from Q-code
    public let category: NotamCategory?

    /// Subcategory string
    public let subcategory: String?

    // MARK: - Schedule

    /// Start of validity (UTC)
    public let effectiveFrom: Date?

    /// End of validity (UTC)
    public let effectiveTo: Date?

    /// True if NOTAM has no end date
    public let isPermanent: Bool

    /// Variable schedule text (e.g., "SR-SS")
    public let scheduleText: String?

    // MARK: - Parsing Metadata

    /// Source identifier (e.g., "foreflight", "avwx")
    public let source: String?

    /// When the NOTAM was parsed
    public let parsedAt: Date

    /// Confidence score from parser (0-1)
    public let parseConfidence: Double

    // MARK: - Custom Categorization (from CategorizationPipeline)

    /// Primary category assigned by categorization pipeline
    public let primaryCategory: String?

    /// All applicable categories from pipeline
    public let customCategories: [String]

    /// Granular tags from pipeline (e.g., "crane", "closed", "ils")
    public let customTags: [String]

    // MARK: - Computed Properties

    /// Coordinates as CLLocationCoordinate2D (nil if not available)
    public var coordinate: CLLocationCoordinate2D? {
        guard let coords = coordinates, coords.count == 2 else { return nil }
        return CLLocationCoordinate2D(latitude: coords[0], longitude: coords[1])
    }

    /// Check if NOTAM is currently active
    public var isActiveNow: Bool {
        return isActive(at: Date())
    }

    /// Check if NOTAM is active at a specific time
    public func isActive(at date: Date) -> Bool {
        if isPermanent {
            return effectiveFrom == nil || effectiveFrom! <= date
        }
        let fromOk = effectiveFrom == nil || effectiveFrom! <= date
        let toOk = effectiveTo == nil || effectiveTo! >= date
        return fromOk && toOk
    }

    /// Check if NOTAM is active during any part of a time window
    public func isActive(during start: Date, to end: Date) -> Bool {
        if isPermanent {
            return effectiveFrom == nil || effectiveFrom! <= end
        }

        // Check for overlap: NOT (notam ends before window OR notam starts after window)
        if let notamEnd = effectiveTo, notamEnd < start {
            return false
        }
        if let notamStart = effectiveFrom, notamStart > end {
            return false
        }
        return true
    }

    // MARK: - CodingKeys

    enum CodingKeys: String, CodingKey {
        case id
        case location
        case rawText = "raw_text"
        case message
        case series
        case number
        case year
        case fir
        case affectedLocations = "affected_locations"
        case qCode = "q_code"
        case trafficType = "traffic_type"
        case purpose
        case scope
        case lowerLimit = "lower_limit"
        case upperLimit = "upper_limit"
        case radiusNm = "radius_nm"
        case coordinates
        case category
        case subcategory
        case effectiveFrom = "effective_from"
        case effectiveTo = "effective_to"
        case isPermanent = "is_permanent"
        case scheduleText = "schedule_text"
        case source
        case parsedAt = "parsed_at"
        case parseConfidence = "parse_confidence"
        case primaryCategory = "primary_category"
        case customCategories = "custom_categories"
        case customTags = "custom_tags"
    }

    // MARK: - Decoding

    public init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)

        // Required fields
        self.id = try container.decode(String.self, forKey: .id)
        self.location = try container.decode(String.self, forKey: .location)

        // Optional strings with defaults
        self.rawText = try container.decodeIfPresent(String.self, forKey: .rawText) ?? ""
        self.message = try container.decodeIfPresent(String.self, forKey: .message) ?? ""

        // Optional identity fields
        self.series = try container.decodeIfPresent(String.self, forKey: .series)
        self.number = try container.decodeIfPresent(Int.self, forKey: .number)
        self.year = try container.decodeIfPresent(Int.self, forKey: .year)

        // Location details
        self.fir = try container.decodeIfPresent(String.self, forKey: .fir)
        self.affectedLocations = try container.decodeIfPresent([String].self, forKey: .affectedLocations) ?? []

        // Q-line fields
        self.qCode = try container.decodeIfPresent(String.self, forKey: .qCode)
        self.trafficType = try container.decodeIfPresent(String.self, forKey: .trafficType)
        self.purpose = try container.decodeIfPresent(String.self, forKey: .purpose)
        self.scope = try container.decodeIfPresent(String.self, forKey: .scope)
        self.lowerLimit = try container.decodeIfPresent(Int.self, forKey: .lowerLimit)
        self.upperLimit = try container.decodeIfPresent(Int.self, forKey: .upperLimit)
        self.radiusNm = try container.decodeIfPresent(Double.self, forKey: .radiusNm)
        self.coordinates = try container.decodeIfPresent([Double].self, forKey: .coordinates)

        // Category
        self.category = try container.decodeIfPresent(NotamCategory.self, forKey: .category)
        self.subcategory = try container.decodeIfPresent(String.self, forKey: .subcategory)

        // Schedule
        self.effectiveFrom = try container.decodeIfPresent(Date.self, forKey: .effectiveFrom)
        self.effectiveTo = try container.decodeIfPresent(Date.self, forKey: .effectiveTo)
        self.isPermanent = try container.decodeIfPresent(Bool.self, forKey: .isPermanent) ?? false
        self.scheduleText = try container.decodeIfPresent(String.self, forKey: .scheduleText)

        // Parsing metadata
        self.source = try container.decodeIfPresent(String.self, forKey: .source)
        self.parsedAt = try container.decodeIfPresent(Date.self, forKey: .parsedAt) ?? Date()
        self.parseConfidence = try container.decodeIfPresent(Double.self, forKey: .parseConfidence) ?? 1.0

        // Custom categorization
        self.primaryCategory = try container.decodeIfPresent(String.self, forKey: .primaryCategory)
        self.customCategories = try container.decodeIfPresent([String].self, forKey: .customCategories) ?? []
        self.customTags = try container.decodeIfPresent([String].self, forKey: .customTags) ?? []
    }
}

// MARK: - Protocol Conformances

extension Notam: Hashable, Equatable, Identifiable {
    public static func == (lhs: Notam, rhs: Notam) -> Bool {
        return lhs.id == rhs.id && lhs.location == rhs.location
    }

    public func hash(into hasher: inout Hasher) {
        hasher.combine(id)
        hasher.combine(location)
    }
}

extension Notam: CustomStringConvertible {
    public var description: String {
        let truncatedMessage = message.count > 50 ? "\(message.prefix(50))..." : message
        return "\(id) (\(location)): \(truncatedMessage)"
    }
}
