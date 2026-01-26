//
//  NotamParser.swift
//  RZFlight
//
//  Native Swift parser for ICAO NOTAM format.
//  Port of Python euro_aip.briefing.parsers.notam_parser
//

import Foundation

/// Parser for ICAO NOTAM format.
///
/// Parses NOTAMs from text, extracting structured fields including:
/// - NOTAM ID and series
/// - Q-line (FIR, code, traffic, purpose, scope, limits, coordinates)
/// - A-line (location)
/// - B/C lines (effective times)
/// - D-line (schedule)
/// - E-line (message)
/// - F/G lines (altitude limits)
///
/// Example:
/// ```swift
/// let notam = NotamParser.parse("""
///     A1234/24 NOTAMN
///     Q) LFFF/QMRLC/IV/NBO/A/000/999/4901N00225E005
///     A) LFPG B) 2401150800 C) 2401152000
///     E) RWY 09L/27R CLSD DUE TO MAINTENANCE
/// """)
/// ```
public enum NotamParser {

    // MARK: - Regex Patterns

    /// Pattern for NOTAM ID: A1234/24
    private static let notamIdPattern = try! NSRegularExpression(
        pattern: #"([A-Z])(\d{4})/(\d{2})"#,
        options: [.caseInsensitive]
    )

    /// Full Q-line pattern: FIR/QCODE/TRAFFIC/PURPOSE/SCOPE/LOWER/UPPER/COORDS[RADIUS]
    /// Handles occasional whitespace before slashes
    private static let qLinePattern = try! NSRegularExpression(
        pattern: #"Q\)\s*([A-Z]{4})\s*/Q([A-Z]{2,5})\s*/([IVK]+)\s*/([NBOMK]+)\s*/([AEW]+)\s*/(\d{3})\s*/(\d{3})\s*/(\d{4}[NS]\d{5}[EW])(\d{3})?"#,
        options: [.caseInsensitive]
    )

    /// Simple Q-line pattern for abbreviated formats
    private static let qLineSimplePattern = try! NSRegularExpression(
        pattern: #"Q\)\s*([A-Z]{4})/Q([A-Z]{2,5})"#,
        options: [.caseInsensitive]
    )

    /// Coordinate pattern: DDMMN/S DDDMME/W
    private static let coordPattern = try! NSRegularExpression(
        pattern: #"(\d{2})(\d{2})([NS])(\d{3})(\d{2})([EW])"#,
        options: [.caseInsensitive]
    )

    /// Pattern to detect NOTAM references (NOTAMR/NOTAMC followed by ID)
    private static let notamRefPattern = try! NSRegularExpression(
        pattern: #"NOTAM[RC]\s*$"#,
        options: []
    )

    /// Q-code to category mapping using ICAO-aligned categories.
    /// Maps 2-letter Q-code subjects to NotamCategory enum values.
    /// For codes not in this mapping, NotamCategory.from(qCodeSubject:) provides fallback.
    private static let qCodeCategories: [String: NotamCategory] = [
        // M* - Movement Area (includes runway, taxiway, apron)
        "MR": .agaMovement,
        "MX": .agaMovement,
        "MA": .agaMovement,
        // L* - Lighting
        "LR": .agaLighting,
        "LL": .agaLighting,
        "LX": .agaLighting,
        // N* - Navigation facilities
        "NA": .navigation,
        "NV": .navigation,
        "ND": .navigation,
        "NI": .navigation,
        "NL": .navigation,
        "NM": .navigation,
        "NB": .navigation,
        // C* - Communications
        "CO": .cnsCommunications,
        // A* - ATM Airspace (FIR, TMA, CTR, routes)
        "FA": .atmAirspace,
        "AR": .atmAirspace,
        "AH": .atmAirspace,
        "AL": .atmAirspace,
        "AT": .atmAirspace,
        "AX": .atmAirspace,
        // R* - Airspace Restrictions (danger, prohibited, restricted areas)
        "RD": .airspaceRestrictions,
        "RT": .airspaceRestrictions,
        // O* - Other (obstacles, AIS)
        "OB": .otherInfo,
        "OL": .otherInfo,
        // P* - Procedures (SID, STAR, approaches)
        "PI": .atmProcedures,
        "PA": .atmProcedures,
        "PD": .atmProcedures,
        "PS": .atmProcedures,
        "PT": .atmProcedures,
        // S* - ATM Services (ATIS, TWR, APP)
        "SE": .atmServices,
        "SA": .atmServices,
        "SN": .atmServices,
        "SV": .atmServices,
        // W* - Warnings (non-standard, map to restrictions)
        "WA": .airspaceRestrictions,
        "WE": .airspaceRestrictions,
        "WM": .airspaceRestrictions,
        "WP": .airspaceRestrictions,
        "WU": .airspaceRestrictions,
        "WV": .airspaceRestrictions,
        "WZ": .airspaceRestrictions,
    ]

    // MARK: - Public Interface

    /// Parse a single NOTAM from text.
    ///
    /// - Parameters:
    ///   - text: Raw NOTAM text
    ///   - source: Optional source identifier
    /// - Returns: Parsed Notam object or nil if parsing fails
    public static func parse(_ text: String, source: String? = nil) -> Notam? {
        let text = text.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !text.isEmpty else { return nil }

        // Extract NOTAM ID
        let (notamId, series, number, year) = parseNotamId(text)
        let finalId = notamId ?? "X\(String(format: "%04d", stableHash(text) % 10000))/00"

        // Parse Q-line
        let qData = parseQLine(text)

        // Parse location (A-line)
        var location = parseLocation(text)
        if location == nil {
            location = qData.fir
        }
        let finalLocation = location ?? "ZZZZ"

        // Parse effective times
        let (effectiveFrom, effectiveTo) = parseEffectiveTimes(text)

        // Check if permanent
        let isPermanent = checkIsPermanent(text, effectiveTo: effectiveTo)

        // Parse schedule
        let scheduleText = parseSchedule(text)

        // Parse message (E-line)
        let message = parseMessage(text)

        // Parse altitude limits
        let (lowerLimit, upperLimit) = parseAltitudeLimits(text, qData: qData)

        // Determine category from Q-code
        let category = determineCategory(qData.qCode)

        // Look up Q-code meanings
        let qCodeInfo = QCodeLookup.lookup(qData.qCode)

        // Extract document references (AIP supplements, etc.)
        let documentReferences = DocumentReferenceExtractor.extract(from: text)

        return Notam(
            id: finalId,
            location: finalLocation,
            rawText: text,
            message: message,
            series: series,
            number: number,
            year: year,
            fir: qData.fir,
            affectedLocations: finalLocation != "ZZZZ" ? [finalLocation] : [],
            qCode: qData.qCode,
            trafficType: qData.trafficType,
            purpose: qData.purpose,
            scope: qData.scope,
            lowerLimit: lowerLimit,
            upperLimit: upperLimit,
            radiusNm: qData.radiusNm,
            coordinates: qData.coordinates,
            category: category,
            subcategory: nil,
            qCodeInfo: qCodeInfo,
            effectiveFrom: effectiveFrom,
            effectiveTo: effectiveTo,
            isPermanent: isPermanent,
            scheduleText: scheduleText,
            source: source,
            parsedAt: Date(),
            parseConfidence: 1.0,
            primaryCategory: nil,
            customCategories: [],
            customTags: [],
            documentReferences: documentReferences
        )
    }

    /// Parse multiple NOTAMs from a text block.
    ///
    /// - Parameters:
    ///   - text: Text containing multiple NOTAMs
    ///   - source: Optional source identifier
    /// - Returns: List of parsed Notam objects
    public static func parseMany(_ text: String, source: String? = nil) -> [Notam] {
        let chunks = splitNotams(text)
        return chunks.compactMap { parse($0, source: source) }
    }

    // MARK: - Private Parsing Methods

    private static func parseNotamId(_ text: String) -> (String?, String?, Int?, Int?) {
        guard let match = notamIdPattern.firstMatch(
            in: text,
            range: NSRange(text.startIndex..., in: text)
        ) else {
            return (nil, nil, nil, nil)
        }

        guard let seriesRange = Range(match.range(at: 1), in: text),
              let numberRange = Range(match.range(at: 2), in: text),
              let yearRange = Range(match.range(at: 3), in: text) else {
            return (nil, nil, nil, nil)
        }

        let series = String(text[seriesRange]).uppercased()
        let number = Int(text[numberRange])!
        let year = Int(text[yearRange])!
        let notamId = "\(series)\(String(format: "%04d", number))/\(String(format: "%02d", year))"

        return (notamId, series, number, year)
    }

    private struct QLineData {
        var fir: String?
        var qCode: String?
        var trafficType: String?
        var purpose: String?
        var scope: String?
        var lowerFL: Int?
        var upperFL: Int?
        var coordinates: [Double]?
        var radiusNm: Double?
    }

    private static func parseQLine(_ text: String) -> QLineData {
        var result = QLineData()

        // Try full Q-line pattern
        if let match = qLinePattern.firstMatch(
            in: text,
            range: NSRange(text.startIndex..., in: text)
        ) {
            if let firRange = Range(match.range(at: 1), in: text) {
                result.fir = String(text[firRange]).uppercased()
            }
            if let qCodeRange = Range(match.range(at: 2), in: text) {
                result.qCode = "Q" + String(text[qCodeRange]).uppercased()
            }
            if let trafficRange = Range(match.range(at: 3), in: text) {
                result.trafficType = String(text[trafficRange]).uppercased()
            }
            if let purposeRange = Range(match.range(at: 4), in: text) {
                result.purpose = String(text[purposeRange]).uppercased()
            }
            if let scopeRange = Range(match.range(at: 5), in: text) {
                result.scope = String(text[scopeRange]).uppercased()
            }
            if let lowerRange = Range(match.range(at: 6), in: text) {
                result.lowerFL = Int(text[lowerRange])
            }
            if let upperRange = Range(match.range(at: 7), in: text) {
                result.upperFL = Int(text[upperRange])
            }
            if let coordsRange = Range(match.range(at: 8), in: text) {
                result.coordinates = parseCoordinates(String(text[coordsRange]))
            }
            if match.range(at: 9).location != NSNotFound,
               let radiusRange = Range(match.range(at: 9), in: text) {
                result.radiusNm = Double(text[radiusRange])
            }

            return result
        }

        // Try simple Q-line pattern
        if let match = qLineSimplePattern.firstMatch(
            in: text,
            range: NSRange(text.startIndex..., in: text)
        ) {
            if let firRange = Range(match.range(at: 1), in: text) {
                result.fir = String(text[firRange]).uppercased()
            }
            if let qCodeRange = Range(match.range(at: 2), in: text) {
                result.qCode = "Q" + String(text[qCodeRange]).uppercased()
            }
        }

        return result
    }

    private static func parseCoordinates(_ coordsStr: String) -> [Double]? {
        guard let match = coordPattern.firstMatch(
            in: coordsStr,
            range: NSRange(coordsStr.startIndex..., in: coordsStr)
        ) else {
            return nil
        }

        guard let latDegRange = Range(match.range(at: 1), in: coordsStr),
              let latMinRange = Range(match.range(at: 2), in: coordsStr),
              let latDirRange = Range(match.range(at: 3), in: coordsStr),
              let lonDegRange = Range(match.range(at: 4), in: coordsStr),
              let lonMinRange = Range(match.range(at: 5), in: coordsStr),
              let lonDirRange = Range(match.range(at: 6), in: coordsStr) else {
            return nil
        }

        let latDeg = Double(coordsStr[latDegRange])!
        let latMin = Double(coordsStr[latMinRange])!
        let latDir = String(coordsStr[latDirRange]).uppercased()
        let lonDeg = Double(coordsStr[lonDegRange])!
        let lonMin = Double(coordsStr[lonMinRange])!
        let lonDir = String(coordsStr[lonDirRange]).uppercased()

        var lat = latDeg + latMin / 60.0
        if latDir == "S" {
            lat = -lat
        }

        var lon = lonDeg + lonMin / 60.0
        if lonDir == "W" {
            lon = -lon
        }

        return [lat, lon]
    }

    private static func parseLocation(_ text: String) -> String? {
        let pattern = try! NSRegularExpression(
            pattern: #"A\)\s*([A-Z]{4})"#,
            options: [.caseInsensitive]
        )

        guard let match = pattern.firstMatch(
            in: text,
            range: NSRange(text.startIndex..., in: text)
        ),
              let locationRange = Range(match.range(at: 1), in: text) else {
            return nil
        }

        return String(text[locationRange]).uppercased()
    }

    private static func parseEffectiveTimes(_ text: String) -> (Date?, Date?) {
        var effectiveFrom: Date?
        var effectiveTo: Date?

        // B) line - effective from
        let bPattern = try! NSRegularExpression(
            pattern: #"B\)\s*(\d{10})"#,
            options: []
        )
        if let match = bPattern.firstMatch(
            in: text,
            range: NSRange(text.startIndex..., in: text)
        ),
           let dateRange = Range(match.range(at: 1), in: text) {
            effectiveFrom = parseNotamDateTime(String(text[dateRange]))
        }

        // C) line - effective to
        let cPattern = try! NSRegularExpression(
            pattern: #"C\)\s*(\d{10}|PERM|UFN)"#,
            options: [.caseInsensitive]
        )
        if let match = cPattern.firstMatch(
            in: text,
            range: NSRange(text.startIndex..., in: text)
        ),
           let valueRange = Range(match.range(at: 1), in: text) {
            let value = String(text[valueRange]).uppercased()
            if value != "PERM" && value != "UFN" {
                effectiveTo = parseNotamDateTime(value)
            }
        }

        return (effectiveFrom, effectiveTo)
    }

    private static func parseNotamDateTime(_ dtStr: String) -> Date? {
        guard dtStr.count == 10 else { return nil }

        let yearStr = String(dtStr.prefix(2))
        let monthStr = String(dtStr.dropFirst(2).prefix(2))
        let dayStr = String(dtStr.dropFirst(4).prefix(2))
        let hourStr = String(dtStr.dropFirst(6).prefix(2))
        let minuteStr = String(dtStr.dropFirst(8).prefix(2))

        guard let year = Int(yearStr),
              let month = Int(monthStr),
              let day = Int(dayStr),
              let hour = Int(hourStr),
              let minute = Int(minuteStr) else {
            return nil
        }

        var components = DateComponents()
        components.year = 2000 + year
        components.month = month
        components.day = day
        components.hour = hour
        components.minute = minute
        components.timeZone = TimeZone(identifier: "UTC")

        return Calendar(identifier: .gregorian).date(from: components)
    }

    private static func checkIsPermanent(_ text: String, effectiveTo: Date?) -> Bool {
        if effectiveTo == nil {
            // Check for PERM or UFN indicators
            let permPattern = try! NSRegularExpression(
                pattern: #"\b(PERM|UFN)\b"#,
                options: [.caseInsensitive]
            )
            if permPattern.firstMatch(
                in: text,
                range: NSRange(text.startIndex..., in: text)
            ) != nil {
                return true
            }
        }
        return false
    }

    private static func parseSchedule(_ text: String) -> String? {
        let pattern = try! NSRegularExpression(
            pattern: #"D\)\s*(.+?)(?=\n[A-G]\)|$)"#,
            options: [.caseInsensitive, .dotMatchesLineSeparators]
        )

        guard let match = pattern.firstMatch(
            in: text,
            range: NSRange(text.startIndex..., in: text)
        ),
              let scheduleRange = Range(match.range(at: 1), in: text) else {
            return nil
        }

        let schedule = String(text[scheduleRange])
            .trimmingCharacters(in: .whitespacesAndNewlines)
            .replacingOccurrences(of: "\\s+", with: " ", options: .regularExpression)

        return schedule.isEmpty ? nil : schedule
    }

    private static func parseMessage(_ text: String) -> String {
        // Look for E) line
        let pattern = try! NSRegularExpression(
            pattern: #"E\)\s*(.+?)(?=\n[FG]\)|$)"#,
            options: [.caseInsensitive, .dotMatchesLineSeparators]
        )

        if let match = pattern.firstMatch(
            in: text,
            range: NSRange(text.startIndex..., in: text)
        ),
           let messageRange = Range(match.range(at: 1), in: text) {
            return String(text[messageRange])
                .trimmingCharacters(in: .whitespacesAndNewlines)
                .replacingOccurrences(of: "\\s+", with: " ", options: .regularExpression)
        }

        // Fallback: try to extract message after NOTAM ID
        let idPattern = try! NSRegularExpression(
            pattern: #"^[A-Z]\d{4}/\d{2}"#,
            options: [.anchorsMatchLines]
        )

        let lines = text.components(separatedBy: "\n")
        for (i, line) in lines.enumerated() {
            if idPattern.firstMatch(
                in: line,
                range: NSRange(line.startIndex..., in: line)
            ) != nil {
                // Found NOTAM ID line, message is likely after
                var remaining = lines.dropFirst(i + 1).joined(separator: "\n")
                // Remove Q), A), B), C) lines
                let cleanPattern = try! NSRegularExpression(
                    pattern: #"[QABCD]\)[^\n]*"#,
                    options: []
                )
                remaining = cleanPattern.stringByReplacingMatches(
                    in: remaining,
                    range: NSRange(remaining.startIndex..., in: remaining),
                    withTemplate: ""
                )
                let cleaned = remaining
                    .trimmingCharacters(in: .whitespacesAndNewlines)
                    .replacingOccurrences(of: "\\s+", with: " ", options: .regularExpression)
                if !cleaned.isEmpty {
                    return cleaned
                }
            }
        }

        return ""
    }

    private static func parseAltitudeLimits(
        _ text: String,
        qData: QLineData
    ) -> (Int?, Int?) {
        var lowerLimit: Int?
        var upperLimit: Int?

        // Try Q-line flight levels first (convert to feet)
        if let lowerFL = qData.lowerFL {
            lowerLimit = lowerFL * 100
        }
        if let upperFL = qData.upperFL {
            upperLimit = upperFL * 100
        }

        // F) line - lower limit
        let fPattern = try! NSRegularExpression(
            pattern: #"F\)\s*(SFC|GND|FL\s*(\d+)|(\d+)\s*(FT|M)?)"#,
            options: [.caseInsensitive]
        )
        if let match = fPattern.firstMatch(
            in: text,
            range: NSRange(text.startIndex..., in: text)
        ),
           let fullRange = Range(match.range(at: 1), in: text) {
            let fullMatch = String(text[fullRange]).uppercased()
            if fullMatch == "SFC" || fullMatch == "GND" {
                lowerLimit = 0
            } else if fullMatch.hasPrefix("FL") {
                if match.range(at: 2).location != NSNotFound,
                   let flRange = Range(match.range(at: 2), in: text),
                   let fl = Int(text[flRange]) {
                    lowerLimit = fl * 100
                }
            } else if match.range(at: 3).location != NSNotFound,
                      let valueRange = Range(match.range(at: 3), in: text),
                      let value = Int(text[valueRange]) {
                var unit = ""
                if match.range(at: 4).location != NSNotFound,
                   let unitRange = Range(match.range(at: 4), in: text) {
                    unit = String(text[unitRange]).uppercased()
                }
                if unit == "M" {
                    lowerLimit = Int(Double(value) * 3.28084)
                } else {
                    lowerLimit = value
                }
            }
        }

        // G) line - upper limit
        let gPattern = try! NSRegularExpression(
            pattern: #"G\)\s*(UNL|FL\s*(\d+)|(\d+)\s*(FT|M)?)"#,
            options: [.caseInsensitive]
        )
        if let match = gPattern.firstMatch(
            in: text,
            range: NSRange(text.startIndex..., in: text)
        ),
           let fullRange = Range(match.range(at: 1), in: text) {
            let fullMatch = String(text[fullRange]).uppercased()
            if fullMatch == "UNL" {
                upperLimit = 99999
            } else if fullMatch.hasPrefix("FL") {
                if match.range(at: 2).location != NSNotFound,
                   let flRange = Range(match.range(at: 2), in: text),
                   let fl = Int(text[flRange]) {
                    upperLimit = fl * 100
                }
            } else if match.range(at: 3).location != NSNotFound,
                      let valueRange = Range(match.range(at: 3), in: text),
                      let value = Int(text[valueRange]) {
                var unit = ""
                if match.range(at: 4).location != NSNotFound,
                   let unitRange = Range(match.range(at: 4), in: text) {
                    unit = String(text[unitRange]).uppercased()
                }
                if unit == "M" {
                    upperLimit = Int(Double(value) * 3.28084)
                } else {
                    upperLimit = value
                }
            }
        }

        return (lowerLimit, upperLimit)
    }

    private static func determineCategory(_ qCode: String?) -> NotamCategory? {
        guard var code = qCode?.uppercased() else { return nil }

        // Remove 'Q' prefix if present
        if code.hasPrefix("Q") {
            code = String(code.dropFirst())
        }

        // Check first 2 letters against explicit mapping
        let prefix = String(code.prefix(2))
        if let category = qCodeCategories[prefix] {
            return category
        }

        // Fallback: use ICAO standard first-letter detection
        return NotamCategory.from(qCodeSubject: prefix) ?? .otherInfo
    }

    /// Deterministic hash function (DJB2) for generating stable fallback IDs.
    ///
    /// Unlike Swift's `hashValue` which is randomized per app launch,
    /// this produces consistent results across sessions.
    private static func stableHash(_ string: String) -> Int {
        var hash: UInt64 = 5381
        for byte in string.utf8 {
            hash = ((hash << 5) &+ hash) &+ UInt64(byte)
        }
        return Int(hash & 0x7FFFFFFF)  // Ensure positive
    }

    /// Split text containing multiple NOTAMs into individual NOTAM chunks.
    ///
    /// Filters out NOTAM IDs that appear as references (after NOTAMR/NOTAMC),
    /// only splitting on IDs that start a new NOTAM.
    private static func splitNotams(_ text: String) -> [String] {
        // First try: look for NOTAM IDs followed by NOTAM[NRC] (most reliable)
        let startPattern = try! NSRegularExpression(
            pattern: #"([A-Z]\d{4}/\d{2})\s*NOTAM[NRC]"#,
            options: []
        )
        let startMatches = startPattern.matches(
            in: text,
            range: NSRange(text.startIndex..., in: text)
        )

        if !startMatches.isEmpty {
            var chunks: [String] = []
            for (i, match) in startMatches.enumerated() {
                guard let startRange = Range(match.range, in: text) else { continue }
                let start = startRange.lowerBound

                let end: String.Index
                if i + 1 < startMatches.count,
                   let nextRange = Range(startMatches[i + 1].range, in: text) {
                    end = nextRange.lowerBound
                } else {
                    end = text.endIndex
                }

                let chunk = String(text[start..<end]).trimmingCharacters(in: .whitespacesAndNewlines)
                if !chunk.isEmpty {
                    chunks.append(chunk)
                }
            }
            if !chunks.isEmpty {
                return chunks
            }
        }

        // Fallback: find all NOTAM ID positions
        let idPattern = try! NSRegularExpression(
            pattern: #"[A-Z]\d{4}/\d{2}"#,
            options: []
        )
        let matches = idPattern.matches(
            in: text,
            range: NSRange(text.startIndex..., in: text)
        )

        if matches.isEmpty {
            // No NOTAM IDs found - try splitting on double newlines
            let parts = text.components(separatedBy: "\n\n")
            let chunks = parts
                .map { $0.trimmingCharacters(in: .whitespacesAndNewlines) }
                .filter { !$0.isEmpty && $0.count > 20 }
            if !chunks.isEmpty {
                return chunks
            }
            // Fallback: treat entire text as one NOTAM
            return text.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty ? [] : [text]
        }

        // Filter out IDs that appear after NOTAMR/NOTAMC (these are references, not new NOTAMs)
        var validStarts: [NSTextCheckingResult] = []
        for match in matches {
            // Check what comes before this ID (look back up to 10 chars)
            let prefixStart = max(0, match.range.location - 10)
            let prefixLength = match.range.location - prefixStart
            let prefixRange = NSRange(location: prefixStart, length: prefixLength)

            if let prefixStringRange = Range(prefixRange, in: text) {
                let prefix = String(text[prefixStringRange])
                // Only include if NOT preceded by NOTAMR or NOTAMC
                if notamRefPattern.firstMatch(
                    in: prefix,
                    range: NSRange(prefix.startIndex..., in: prefix)
                ) == nil {
                    validStarts.append(match)
                }
            } else {
                validStarts.append(match)
            }
        }

        if validStarts.isEmpty {
            // All IDs were references - treat entire text as one chunk
            let trimmed = text.trimmingCharacters(in: .whitespacesAndNewlines)
            return trimmed.isEmpty ? [] : [trimmed]
        }

        // Extract text from each valid NOTAM ID to the next
        var chunks: [String] = []
        for (i, match) in validStarts.enumerated() {
            guard let startRange = Range(match.range, in: text) else { continue }
            let start = startRange.lowerBound

            let end: String.Index
            if i + 1 < validStarts.count,
               let nextRange = Range(validStarts[i + 1].range, in: text) {
                end = nextRange.lowerBound
            } else {
                end = text.endIndex
            }

            let chunk = String(text[start..<end]).trimmingCharacters(in: .whitespacesAndNewlines)
            if !chunk.isEmpty {
                chunks.append(chunk)
            }
        }

        return chunks
    }
}
