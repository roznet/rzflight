//
//  ForeFlightParser.swift
//  RZFlight
//
//  Native Swift parser for ForeFlight PDF briefings.
//  Uses PDFKit for text extraction and ports logic from Python ForeFlightSource.
//

import Foundation
import PDFKit

/// Parser for ForeFlight briefing PDFs.
///
/// Extracts text from ForeFlight PDF briefings using PDFKit, handling:
/// - Two-column landscape layouts
/// - Route information (departure, destination, alternates, waypoints)
/// - NOTAM sections organized by location
///
/// Example:
/// ```swift
/// let parser = ForeFlightParser()
///
/// // Parse from file URL
/// let briefing = try parser.parse(url: fileURL)
///
/// // Or from raw PDF data
/// let briefing = try parser.parse(data: pdfData)
///
/// // Access extracted data
/// print(briefing.route?.departure)
/// let runwayNotams = briefing.notams.runwayRelated()
/// ```
public final class ForeFlightParser: Sendable {

    /// Errors that can occur during parsing
    public enum ParserError: Error, LocalizedError {
        case fileNotFound(URL)
        case invalidPDF
        case textExtractionFailed
        case noContent

        public var errorDescription: String? {
            switch self {
            case .fileNotFound(let url):
                return "PDF file not found: \(url.path)"
            case .invalidPDF:
                return "Invalid or corrupted PDF file"
            case .textExtractionFailed:
                return "Failed to extract text from PDF"
            case .noContent:
                return "No content found in PDF"
            }
        }
    }

    // MARK: - Initialization

    public init() {}

    // MARK: - Public Parsing Interface

    /// Parse a ForeFlight briefing PDF from a file URL.
    ///
    /// - Parameter url: URL to the PDF file
    /// - Returns: Parsed Briefing object
    /// - Throws: ParserError if parsing fails
    public func parse(url: URL) throws -> Briefing {
        guard FileManager.default.fileExists(atPath: url.path) else {
            throw ParserError.fileNotFound(url)
        }

        guard let document = PDFDocument(url: url) else {
            throw ParserError.invalidPDF
        }

        return try parse(document: document)
    }

    /// Parse a ForeFlight briefing PDF from raw data.
    ///
    /// - Parameter data: Raw PDF data
    /// - Returns: Parsed Briefing object
    /// - Throws: ParserError if parsing fails
    public func parse(data: Data) throws -> Briefing {
        guard let document = PDFDocument(data: data) else {
            throw ParserError.invalidPDF
        }

        return try parse(document: document)
    }

    /// Parse briefing from pre-extracted text.
    ///
    /// Useful when text has already been extracted from PDF.
    ///
    /// - Parameter text: Extracted text from briefing
    /// - Returns: Parsed Briefing object
    public func parse(text: String) -> Briefing {
        let route = extractRoute(from: text)
        let notams = extractNotams(from: text)

        return Briefing(
            source: "foreflight",
            route: route,
            notams: notams
        )
    }

    // MARK: - Private PDF Extraction

    private func parse(document: PDFDocument) throws -> Briefing {
        let text = try extractText(from: document)

        guard !text.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else {
            throw ParserError.noContent
        }

        return parse(text: text)
    }

    /// Extract text from PDF, handling multi-column layouts.
    private func extractText(from document: PDFDocument) throws -> String {
        var textParts: [String] = []

        for pageIndex in 0..<document.pageCount {
            guard let page = document.page(at: pageIndex) else { continue }
            if let pageText = extractPageText(from: page), !pageText.isEmpty {
                textParts.append(pageText)
            }
        }

        guard !textParts.isEmpty else {
            throw ParserError.textExtractionFailed
        }

        return textParts.joined(separator: "\n\n")
    }

    /// Extract text from a single page, handling multi-column layouts.
    ///
    /// ForeFlight briefings often use two-column layouts in landscape mode.
    /// This method detects such layouts and extracts columns separately.
    private func extractPageText(from page: PDFPage) -> String? {
        let bounds = page.bounds(for: .mediaBox)
        let width = bounds.width
        let height = bounds.height

        // Check if landscape orientation (likely two-column NOTAM pages)
        if width > height {
            // Extract left and right columns separately using selection
            let leftRect = CGRect(
                x: bounds.minX,
                y: bounds.minY,
                width: width / 2,
                height: height
            )
            let rightRect = CGRect(
                x: bounds.midX,
                y: bounds.minY,
                width: width / 2,
                height: height
            )

            let leftText = page.selection(for: leftRect)?.string ?? ""
            let rightText = page.selection(for: rightRect)?.string ?? ""

            // Combine columns - left first, then right
            if !leftText.isEmpty && !rightText.isEmpty {
                return leftText + "\n\n" + rightText
            }
            return leftText.isEmpty ? rightText : leftText
        }

        // Portrait mode - extract normally
        return page.string
    }

    // MARK: - Route Extraction

    private func extractRoute(from text: String) -> Route? {
        var departure: String?
        var destination: String?

        // First, try to find explicit Departure and Destination labels
        // These are the most reliable indicators in ForeFlight briefings
        let depPattern = try! NSRegularExpression(
            pattern: #"\bDeparture\s+([A-Z]{4})\b"#,
            options: [.caseInsensitive]
        )
        let destPattern = try! NSRegularExpression(
            pattern: #"\bDestination\s+([A-Z]{4})\b"#,
            options: [.caseInsensitive]
        )

        if let depMatch = depPattern.firstMatch(
            in: text,
            range: NSRange(text.startIndex..., in: text)
        ),
           let destMatch = destPattern.firstMatch(
            in: text,
            range: NSRange(text.startIndex..., in: text)
        ) {
            if let depRange = Range(depMatch.range(at: 1), in: text) {
                departure = String(text[depRange]).uppercased()
            }
            if let destRange = Range(destMatch.range(at: 1), in: text) {
                destination = String(text[destRange]).uppercased()
            }
        } else {
            // Try other common patterns (in order of reliability)
            let patterns = [
                // "From: LFPG To: EGLL"
                #"From:?\s*([A-Z]{4}).*?To:?\s*([A-Z]{4})"#,
                // Route header "LFPG EGLL"
                #"^Route:?\s*([A-Z]{4})\s+([A-Z]{4})"#,
                // "LFPG to EGLL" or "LFPG - EGLL"
                #"([A-Z]{4})\s*(?:to|->|→)\s*([A-Z]{4})"#,
            ]

            for pattern in patterns {
                let regex = try! NSRegularExpression(
                    pattern: pattern,
                    options: [.caseInsensitive, .anchorsMatchLines, .dotMatchesLineSeparators]
                )
                if let match = regex.firstMatch(
                    in: text,
                    range: NSRange(text.startIndex..., in: text)
                ) {
                    if let depRange = Range(match.range(at: 1), in: text) {
                        departure = String(text[depRange]).uppercased()
                    }
                    if let destRange = Range(match.range(at: 2), in: text) {
                        destination = String(text[destRange]).uppercased()
                    }
                    break
                }
            }
        }

        // Fallback: try to find ICAO codes mentioned early in document
        if departure == nil || destination == nil {
            let icaoPattern = try! NSRegularExpression(
                pattern: #"\b([A-Z]{4})\b"#,
                options: []
            )
            let searchRange = String(text.prefix(2000))
            let matches = icaoPattern.matches(
                in: searchRange,
                range: NSRange(searchRange.startIndex..., in: searchRange)
            )

            let excludedWords = Set([
                "NOTAM", "METAR", "SPECI", "TEMPO", "BECMG", "NOSIG", "CAVOK",
                "PROB", "FROM", "WIND", "AUTO"
            ])

            var airportCodes: [String] = []
            for match in matches {
                if let range = Range(match.range(at: 1), in: searchRange) {
                    let code = String(searchRange[range])
                    if !excludedWords.contains(code) {
                        airportCodes.append(code)
                    }
                }
            }

            if airportCodes.count >= 2 {
                if departure == nil {
                    departure = airportCodes[0]
                }
                if destination == nil {
                    destination = airportCodes[1]
                }
            }
        }

        guard let dep = departure else { return nil }

        var route = Route(
            departure: dep,
            destination: destination ?? dep
        )

        // Try to extract alternates
        let alternates = extractAlternates(from: text)
        if !alternates.isEmpty {
            route = Route(
                departure: route.departure,
                destination: route.destination,
                alternates: alternates,
                waypoints: route.waypoints
            )
        }

        // Try to extract waypoints
        let waypoints = extractWaypoints(from: text)
        if !waypoints.isEmpty {
            route = Route(
                departure: route.departure,
                destination: route.destination,
                alternates: route.alternates,
                waypoints: waypoints
            )
        }

        return route
    }

    private func extractAlternates(from text: String) -> [String] {
        var alternates: [String] = []

        let patterns = [
            #"Alternate[s]?:?\s*([A-Z]{4}(?:\s*,?\s*[A-Z]{4})*)"#,
            #"ALT:?\s*([A-Z]{4}(?:\s*,?\s*[A-Z]{4})*)"#,
        ]

        let icaoPattern = try! NSRegularExpression(
            pattern: #"[A-Z]{4}"#,
            options: []
        )

        for pattern in patterns {
            let regex = try! NSRegularExpression(
                pattern: pattern,
                options: [.caseInsensitive]
            )
            if let match = regex.firstMatch(
                in: text,
                range: NSRange(text.startIndex..., in: text)
            ),
               let groupRange = Range(match.range(at: 1), in: text) {
                let group = String(text[groupRange])
                let codes = icaoPattern.matches(
                    in: group,
                    range: NSRange(group.startIndex..., in: group)
                )
                for codeMatch in codes {
                    if let codeRange = Range(codeMatch.range, in: group) {
                        alternates.append(String(group[codeRange]))
                    }
                }
            }
        }

        // Remove duplicates while preserving order
        var seen = Set<String>()
        return alternates.filter { seen.insert($0).inserted }
    }

    private func extractWaypoints(from text: String) -> [String] {
        // Look for route string like "DCT POGOL DCT VESAN DCT"
        let routePattern = try! NSRegularExpression(
            pattern: #"Route:?\s*(.+?)(?:\n\n|\n[A-Z]{4}:|\nNOTAM)"#,
            options: [.caseInsensitive, .dotMatchesLineSeparators]
        )

        guard let match = routePattern.firstMatch(
            in: text,
            range: NSRange(text.startIndex..., in: text)
        ),
              let groupRange = Range(match.range(at: 1), in: text) else {
            return []
        }

        let routeStr = String(text[groupRange])

        // Extract waypoint names (2-5 letter fixes, airways, etc.)
        let waypointPattern = try! NSRegularExpression(
            pattern: #"\b([A-Z]{2,5})\b"#,
            options: []
        )
        let matches = waypointPattern.matches(
            in: routeStr,
            range: NSRange(routeStr.startIndex..., in: routeStr)
        )

        let excluded = Set([
            "DCT", "VIA", "THEN", "TO", "FROM", "AND", "OR",
            "IFR", "VFR", "FL", "ALT", "ROUTE"
        ])

        var waypoints: [String] = []
        for wpMatch in matches {
            if let range = Range(wpMatch.range(at: 1), in: routeStr) {
                let wp = String(routeStr[range])
                if !excluded.contains(wp) {
                    waypoints.append(wp)
                }
            }
        }

        return waypoints
    }

    // MARK: - NOTAM Extraction

    private func extractNotams(from text: String) -> [Notam] {
        var notams: [Notam] = []

        // Find NOTAM sections
        let notamSections = findNotamSections(in: text)

        for (sectionText, location) in notamSections {
            let sectionNotams = parseNotamSection(sectionText, location: location)
            notams.append(contentsOf: sectionNotams)
        }

        // Deduplicate by NOTAM ID
        var seenIds = Set<String>()
        var uniqueNotams: [Notam] = []
        for notam in notams {
            if !seenIds.contains(notam.id) {
                seenIds.insert(notam.id)
                uniqueNotams.append(notam)
            }
        }

        return uniqueNotams
    }

    /// Find NOTAM sections in the briefing text.
    ///
    /// - Returns: Array of (sectionText, location) tuples
    private func findNotamSections(in text: String) -> [(String, String)] {
        var sections: [(String, String)] = []

        // Pattern 1: "LFPG NOTAMs" or "NOTAMs for LFPG"
        let pattern1 = try! NSRegularExpression(
            pattern: #"(?:([A-Z]{4})\s+NOTAMs?|NOTAMs?\s+(?:for\s+)?([A-Z]{4}))\s*[:\n](.+?)(?=(?:[A-Z]{4}\s+NOTAMs?|NOTAMs?\s+(?:for\s+)?[A-Z]{4}|\z))"#,
            options: [.caseInsensitive, .dotMatchesLineSeparators]
        )

        for match in pattern1.matches(
            in: text,
            range: NSRange(text.startIndex..., in: text)
        ) {
            var location: String?
            if match.range(at: 1).location != NSNotFound,
               let locRange = Range(match.range(at: 1), in: text) {
                location = String(text[locRange]).uppercased()
            } else if match.range(at: 2).location != NSNotFound,
                      let locRange = Range(match.range(at: 2), in: text) {
                location = String(text[locRange]).uppercased()
            }

            if let loc = location,
               let sectionRange = Range(match.range(at: 3), in: text) {
                let sectionText = String(text[sectionRange])
                sections.append((sectionText, loc))
            }
        }

        // Pattern 2: Section headers with ICAO
        let pattern2 = try! NSRegularExpression(
            pattern: #"^\s*([A-Z]{4})\s*$\s*\n((?:(?![A-Z]{4}\s*$).)+)"#,
            options: [.anchorsMatchLines, .dotMatchesLineSeparators]
        )

        let notamContentPattern = try! NSRegularExpression(
            pattern: #"[A-Z]\d{4}/\d{2}|NOTAM"#,
            options: [.caseInsensitive]
        )

        for match in pattern2.matches(
            in: text,
            range: NSRange(text.startIndex..., in: text)
        ) {
            if let locRange = Range(match.range(at: 1), in: text),
               let sectionRange = Range(match.range(at: 2), in: text) {
                let location = String(text[locRange]).uppercased()
                let sectionText = String(text[sectionRange])

                // Only add if contains NOTAM-like content
                if notamContentPattern.firstMatch(
                    in: sectionText,
                    range: NSRange(sectionText.startIndex..., in: sectionText)
                ) != nil {
                    sections.append((sectionText, location))
                }
            }
        }

        // Pattern 3: FDC NOTAMs section
        let fdcPattern = try! NSRegularExpression(
            pattern: #"FDC\s+NOTAMs?\s*[:\n](.+?)(?=\n\n[A-Z]|\z)"#,
            options: [.caseInsensitive, .dotMatchesLineSeparators]
        )

        if let match = fdcPattern.firstMatch(
            in: text,
            range: NSRange(text.startIndex..., in: text)
        ),
           let sectionRange = Range(match.range(at: 1), in: text) {
            sections.append((String(text[sectionRange]), "FDC"))
        }

        // If no sections found, try to find NOTAMs in the entire text
        if sections.isEmpty {
            let idPattern = try! NSRegularExpression(
                pattern: #"[A-Z]\d{4}/\d{2}"#,
                options: []
            )
            if idPattern.firstMatch(
                in: text,
                range: NSRange(text.startIndex..., in: text)
            ) != nil {
                sections.append((text, "UNKNOWN"))
            }
        }

        return sections
    }

    /// Parse NOTAMs from a section of text.
    private func parseNotamSection(_ sectionText: String, location: String) -> [Notam] {
        var notams: [Notam] = []

        // Split section into individual NOTAMs
        let notamChunks = splitNotamSection(sectionText)

        for chunk in notamChunks {
            if var notam = NotamParser.parse(chunk, source: "foreflight") {
                // Use section location if NOTAM location is unknown
                if notam.location == "ZZZZ" && location != "UNKNOWN" {
                    notam = Notam(
                        id: notam.id,
                        location: location,
                        rawText: notam.rawText,
                        message: notam.message,
                        series: notam.series,
                        number: notam.number,
                        year: notam.year,
                        fir: notam.fir,
                        affectedLocations: notam.affectedLocations.isEmpty ? [location] : notam.affectedLocations,
                        qCode: notam.qCode,
                        trafficType: notam.trafficType,
                        purpose: notam.purpose,
                        scope: notam.scope,
                        lowerLimit: notam.lowerLimit,
                        upperLimit: notam.upperLimit,
                        radiusNm: notam.radiusNm,
                        coordinates: notam.coordinate.map { [$0.latitude, $0.longitude] },
                        category: notam.category,
                        subcategory: notam.subcategory,
                        qCodeInfo: notam.qCodeInfo,
                        effectiveFrom: notam.effectiveFrom,
                        effectiveTo: notam.effectiveTo,
                        isPermanent: notam.isPermanent,
                        scheduleText: notam.scheduleText,
                        source: notam.source,
                        parsedAt: notam.parsedAt,
                        parseConfidence: notam.parseConfidence,
                        primaryCategory: notam.primaryCategory,
                        customCategories: notam.customCategories,
                        customTags: notam.customTags
                    )
                }
                notams.append(notam)
            }
        }

        return notams
    }

    /// Split a NOTAM section into individual NOTAM texts.
    ///
    /// Only splits on NOTAM IDs that start a new NOTAM (followed by NOTAM[NRC]),
    /// not on IDs that appear as references (after NOTAMR/NOTAMC).
    private func splitNotamSection(_ sectionText: String) -> [String] {
        // Pattern for NOTAM ID at start of a new NOTAM
        // Must be followed by NOTAM[NRC] (with possible space)
        let startPattern = try! NSRegularExpression(
            pattern: #"([A-Z]\d{4}/\d{2})\s*NOTAM[NRC]"#,
            options: []
        )
        let matches = startPattern.matches(
            in: sectionText,
            range: NSRange(sectionText.startIndex..., in: sectionText)
        )

        if !matches.isEmpty {
            var chunks: [String] = []
            for (i, match) in matches.enumerated() {
                guard let startRange = Range(match.range, in: sectionText) else { continue }
                let start = startRange.lowerBound

                let end: String.Index
                if i + 1 < matches.count,
                   let nextRange = Range(matches[i + 1].range, in: sectionText) {
                    end = nextRange.lowerBound
                } else {
                    end = sectionText.endIndex
                }

                let chunk = String(sectionText[start..<end])
                    .trimmingCharacters(in: .whitespacesAndNewlines)
                if !chunk.isEmpty {
                    chunks.append(chunk)
                }
            }
            if !chunks.isEmpty {
                return chunks
            }
        }

        // Fallback: try the simple ID pattern if no NOTAM[NRC] markers found
        let idPattern = try! NSRegularExpression(
            pattern: #"[A-Z]\d{4}/\d{2}"#,
            options: []
        )
        let idMatches = idPattern.matches(
            in: sectionText,
            range: NSRange(sectionText.startIndex..., in: sectionText)
        )

        if !idMatches.isEmpty {
            // Filter out IDs that appear after NOTAMR/NOTAMC (references)
            let notamRefPattern = try! NSRegularExpression(
                pattern: #"NOTAM[RC]\s*$"#,
                options: []
            )

            var validStarts: [NSTextCheckingResult] = []
            for match in idMatches {
                // Check what comes before this ID
                let prefixStart = max(0, match.range.location - 10)
                let prefixLength = match.range.location - prefixStart
                let prefixRange = NSRange(location: prefixStart, length: prefixLength)

                if let prefixStringRange = Range(prefixRange, in: sectionText) {
                    let prefix = String(sectionText[prefixStringRange])
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

            if !validStarts.isEmpty {
                var chunks: [String] = []
                for (i, match) in validStarts.enumerated() {
                    guard let startRange = Range(match.range, in: sectionText) else { continue }
                    let start = startRange.lowerBound

                    let end: String.Index
                    if i + 1 < validStarts.count,
                       let nextRange = Range(validStarts[i + 1].range, in: sectionText) {
                        end = nextRange.lowerBound
                    } else {
                        end = sectionText.endIndex
                    }

                    let chunk = String(sectionText[start..<end])
                        .trimmingCharacters(in: .whitespacesAndNewlines)
                    if !chunk.isEmpty {
                        chunks.append(chunk)
                    }
                }
                if !chunks.isEmpty {
                    return chunks
                }
            }
        }

        // Fallback: try splitting on double newline
        let parts = sectionText.components(separatedBy: "\n\n")
        var chunks: [String] = []
        for part in parts {
            let trimmed = part.trimmingCharacters(in: .whitespacesAndNewlines)
            if !trimmed.isEmpty && trimmed.count > 20 {
                chunks.append(trimmed)
            }
        }

        // If still nothing, return whole section
        if chunks.isEmpty {
            let trimmed = sectionText.trimmingCharacters(in: .whitespacesAndNewlines)
            if !trimmed.isEmpty {
                chunks = [trimmed]
            }
        }

        return chunks
    }
}
