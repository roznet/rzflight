//
//  ICAOFlightPlanParser.swift
//  RZFlight
//
//  Parses ICAO FPL format strings into ICAOFlightPlan with a populated Route.
//

import Foundation
import CoreLocation

/// Parsed ICAO flight plan with all extractable fields.
public struct ICAOFlightPlan: Sendable {

    // MARK: - Parsed Fields

    /// Aircraft registration (field 7), e.g. "N122DR"
    public let aircraftRegistration: String?

    /// Aircraft type code (field 9), e.g. "S22T"
    public let aircraftType: String?

    /// Flight rules: V=VFR, I=IFR, Y/Z=mixed
    public let flightRules: String?

    /// Flight type: G=general, S=scheduled, N=non-scheduled, M=military, X=other
    public let flightType: String?

    /// Raw speed string, e.g. "N0166" or "K0280"
    public let speed: String?

    /// Speed in knots (K prefix converted)
    public let speedKnots: Int?

    /// Raw level string, e.g. "VFR", "F350", "A055"
    public let level: String?

    /// Altitude in feet (F350→35000, A055→5500, VFR→nil)
    public let altitudeFeet: Int?

    /// COM/NAV equipment codes (field 10a), e.g. "SBDGORVY"
    public let equipment: String?

    /// Surveillance equipment codes (field 10b), e.g. "LB2"
    public let surveillance: String?

    /// Date of flight from field 18 DOF/
    public let dateOfFlight: Date?

    /// Departure time UTC (hours and minutes)
    public let departureTimeUTC: (hour: Int, minute: Int)?

    /// Estimated elapsed time in minutes
    public let eetMinutes: Int?

    /// Unparsed route string from field 15
    public let rawRoute: String?

    /// Field 18 key/value pairs
    public let otherInfo: [String: String]

    /// Original FPL text
    public let rawText: String

    /// Populated route with departure, destination, waypoints, coordinates, times
    public let route: Route

    // MARK: - Derived Properties

    /// True if flight rules include IFR (I, Y, or Z)
    public var isIFR: Bool {
        guard let rules = flightRules else { return false }
        return rules == "I" || rules == "Y" || rules == "Z"
    }

    /// True if flight rules are pure VFR
    public var isVFR: Bool { flightRules == "V" }

    /// True if GNSS/GPS equipped
    public var hasGNSS: Bool { equipment?.contains("G") ?? false }

    /// True if PBN/RNAV approved
    public var hasRNAV: Bool { equipment?.contains("R") ?? false }

    /// True if ADS-B out capable
    public var hasADSB: Bool {
        guard let s = surveillance else { return false }
        return s.contains("B") || s.contains("1") || s.contains("2")
    }

    /// True if RVSM approved
    public var hasRVSM: Bool { equipment?.contains("W") ?? false }

    /// PBN capability codes from field 18
    public var pbnCodes: String? { otherInfo["PBN"] }

    /// Remarks from field 18
    public var remarks: String? { otherInfo["RMK"] }
}

// MARK: - Parser

/// Parses ICAO FPL format strings.
public struct ICAOFlightPlanParser {

    // MARK: - Token Classification

    private static let skipTokens: Set<String> = ["DCT", "IFR", "VFR", "->", "TO", "STAY"]

    private static let speedPattern = try! NSRegularExpression(pattern: #"^([NK])(\d{4})"#)
    private static let levelPattern = try! NSRegularExpression(pattern: #"^([FASM]\d{3,4}|VFR|IFR)\b"#)
    private static let airwayPattern = try! NSRegularExpression(pattern: #"^[A-Z]{1,2}\d{1,4}$"#)
    private static let icaoCoordDM = try! NSRegularExpression(pattern: #"^(\d{2})(\d{2})([NS])(\d{3})(\d{2})([EW])$"#)
    private static let icaoCoordDMS = try! NSRegularExpression(pattern: #"^(\d{2})(\d{2})(\d{2})([NS])(\d{3})(\d{2})(\d{2})([EW])$"#)

    private static let field18Keys: Set<String> = [
        "DOF", "PBN", "NAV", "COM", "DAT", "SUR", "DEP", "DEST", "ALTN",
        "REG", "EET", "SEL", "TYP", "CODE", "DLE", "OPR", "ORGN", "PER",
        "RMK", "RIF", "RVR", "STS", "TALT",
    ]

    /// Parse an ICAO FPL string.
    ///
    /// - Parameters:
    ///   - text: String containing (FPL-...) block
    ///   - resolver: Optional RoutePointResolver for coordinate resolution
    /// - Returns: Parsed flight plan, or nil if no FPL block found
    public static func parse(
        _ text: String,
        resolver: RoutePointResolver? = nil
    ) -> ICAOFlightPlan? {
        // Step 1: Extract FPL block
        guard let fplRange = text.range(of: #"\(FPL[^)]*\)"#, options: .regularExpression) else {
            return nil
        }
        let rawText = String(text[fplRange])

        // Strip parens and collapse whitespace
        var body = rawText
        body.removeFirst()
        body.removeLast()
        body = body.replacingOccurrences(of: "\n", with: " ")
            .replacingOccurrences(of: "\r", with: " ")
        // Collapse multiple spaces
        while body.contains("  ") {
            body = body.replacingOccurrences(of: "  ", with: " ")
        }
        body = body.trimmingCharacters(in: .whitespaces)

        // Step 2: Split fields
        let fields = splitFields(body)
        guard fields.count >= 6 else { return nil }

        // Step 3: Parse fields
        let registration = fields[0].trimmingCharacters(in: .whitespaces).uppercased()

        let (flightRules, flightType) = parseField8(fields[1])

        var aircraftType: String?
        var equipment: String?
        var surveillance: String?
        parseField9(fields[2], aircraftType: &aircraftType, equipment: &equipment, surveillance: &surveillance)

        let field13Idx: Int
        if fields.count > 7 {
            parseEquipmentString(fields[3], equipment: &equipment, surveillance: &surveillance)
            field13Idx = 4
        } else {
            field13Idx = 3
        }

        var departure = ""
        var departureTimeUTC: (hour: Int, minute: Int)?
        parseField13(fields[field13Idx], icao: &departure, time: &departureTimeUTC)

        var speedStr: String?
        var speedKnots: Int?
        var levelStr: String?
        var altitudeFeet: Int?
        var rawRoute: String?

        let field15Idx = field13Idx + 1
        if field15Idx < fields.count {
            parseField15(fields[field15Idx], speed: &speedStr, speedKnots: &speedKnots,
                         level: &levelStr, altitudeFeet: &altitudeFeet, rawRoute: &rawRoute)
        }

        var destination = ""
        var eetMinutes: Int?
        var alternates: [String] = []

        let field16Idx = field15Idx + 1
        if field16Idx < fields.count {
            parseField16(fields[field16Idx], icao: &destination, eet: &eetMinutes, alternates: &alternates)
        }

        var otherInfo: [String: String] = [:]
        var dateOfFlight: Date?

        let field18Idx = field16Idx + 1
        if field18Idx < fields.count {
            let field18Text = fields[field18Idx...].joined(separator: " -")
            parseField18(field18Text, otherInfo: &otherInfo, dateOfFlight: &dateOfFlight)
        }

        // Step 4: Parse route tokens
        var waypointNames: [String] = []
        var waypointCoords: [RoutePoint] = []
        parseRouteTokens(rawRoute, resolver: resolver,
                         waypointNames: &waypointNames, waypointCoords: &waypointCoords)

        // Step 5: Resolve departure/destination/alternates coordinates
        var depCoords: [Double]?
        var destCoords: [Double]?
        var altCoords: [String: [Double]]?

        if let resolver = resolver {
            if let pt = resolver.resolve(departure) {
                depCoords = [pt.latitude, pt.longitude]
            }
            if let pt = resolver.resolve(destination) {
                destCoords = [pt.latitude, pt.longitude]
            }
            var ac: [String: [Double]] = [:]
            for alt in alternates {
                if let pt = resolver.resolve(alt) {
                    ac[alt] = [pt.latitude, pt.longitude]
                }
            }
            if !ac.isEmpty { altCoords = ac }
        }

        // Step 6: Compute times
        var depDateTime: Date?
        var arrDateTime: Date?

        if let dof = dateOfFlight, let depTime = departureTimeUTC {
            var cal = Calendar(identifier: .gregorian)
            cal.timeZone = TimeZone(identifier: "UTC")!
            var components = cal.dateComponents([.year, .month, .day], from: dof)
            components.hour = depTime.hour
            components.minute = depTime.minute
            components.timeZone = TimeZone(identifier: "UTC")
            depDateTime = cal.date(from: components)
        }

        if let dep = depDateTime, let eet = eetMinutes {
            arrDateTime = dep.addingTimeInterval(Double(eet) * 60)
        }

        let route = Route(
            departure: departure,
            destination: destination,
            alternates: alternates,
            waypoints: waypointNames,
            departureCoords: depCoords,
            destinationCoords: destCoords,
            alternateCoords: altCoords,
            waypointCoords: waypointCoords,
            aircraftType: aircraftType,
            departureTime: depDateTime,
            arrivalTime: arrDateTime
        )

        return ICAOFlightPlan(
            aircraftRegistration: registration,
            aircraftType: aircraftType,
            flightRules: flightRules,
            flightType: flightType,
            speed: speedStr,
            speedKnots: speedKnots,
            level: levelStr,
            altitudeFeet: altitudeFeet,
            equipment: equipment,
            surveillance: surveillance,
            dateOfFlight: dateOfFlight,
            departureTimeUTC: departureTimeUTC,
            eetMinutes: eetMinutes,
            rawRoute: rawRoute,
            otherInfo: otherInfo,
            rawText: rawText,
            route: route
        )
    }

    // MARK: - Field Splitting

    private static func splitFields(_ body: String) -> [String] {
        var text = body
        if text.hasPrefix("FPL") {
            text = String(text.dropFirst(3))
        }
        text = text.trimmingCharacters(in: CharacterSet(charactersIn: "- "))

        let parts = text.components(separatedBy: " -")
        var fields: [String] = []
        for (i, part) in parts.enumerated() {
            if i == 0 {
                let subparts = part.components(separatedBy: "-")
                fields.append(contentsOf: subparts.map { $0.trimmingCharacters(in: .whitespaces) })
            } else {
                let trimmed = part.trimmingCharacters(in: .whitespaces)
                if !trimmed.isEmpty {
                    fields.append(trimmed)
                }
            }
        }
        return fields
    }

    // MARK: - Field Parsers

    private static func parseField8(_ field: String) -> (rules: String?, type: String?) {
        let trimmed = field.trimmingCharacters(in: .whitespaces).uppercased()
        guard !trimmed.isEmpty else { return (nil, nil) }
        let rules = String(trimmed.prefix(1))
        let type = trimmed.count >= 2 ? String(trimmed.dropFirst(1)) : nil
        return (rules, type)
    }

    private static func parseField9(
        _ field: String,
        aircraftType: inout String?,
        equipment: inout String?,
        surveillance: inout String?
    ) {
        let trimmed = field.trimmingCharacters(in: .whitespaces).uppercased()

        // Check for embedded equipment: "S22T/L-SBDGORVY/LB2"
        if let dashIdx = trimmed.firstIndex(of: "-") {
            let typePart = String(trimmed[trimmed.startIndex..<dashIdx])
            let equipPart = String(trimmed[trimmed.index(after: dashIdx)...])

            if let slashIdx = typePart.firstIndex(of: "/") {
                aircraftType = String(typePart[typePart.startIndex..<slashIdx])
            } else {
                aircraftType = typePart
            }
            parseEquipmentString(equipPart, equipment: &equipment, surveillance: &surveillance)
        } else {
            if let slashIdx = trimmed.firstIndex(of: "/") {
                aircraftType = String(trimmed[trimmed.startIndex..<slashIdx])
            } else {
                aircraftType = trimmed
            }
        }
    }

    private static func parseEquipmentString(
        _ field: String,
        equipment: inout String?,
        surveillance: inout String?
    ) {
        let trimmed = field.trimmingCharacters(in: .whitespaces).uppercased()
        if let slashIdx = trimmed.firstIndex(of: "/") {
            equipment = String(trimmed[trimmed.startIndex..<slashIdx])
            surveillance = String(trimmed[trimmed.index(after: slashIdx)...])
        } else {
            equipment = trimmed
        }
    }

    private static func parseField13(
        _ field: String,
        icao: inout String,
        time: inout (hour: Int, minute: Int)?
    ) {
        let trimmed = field.trimmingCharacters(in: .whitespaces).uppercased()
        guard trimmed.count >= 4 else { return }
        icao = String(trimmed.prefix(4))

        guard trimmed.count >= 8 else { return }
        let timeStr = String(trimmed.dropFirst(4).prefix(4))
        if let hour = Int(timeStr.prefix(2)), let min = Int(timeStr.suffix(2)),
           (0...23).contains(hour), (0...59).contains(min) {
            time = (hour, min)
        }
    }

    private static func parseField15(
        _ field: String,
        speed: inout String?,
        speedKnots: inout Int?,
        level: inout String?,
        altitudeFeet: inout Int?,
        rawRoute: inout String?
    ) {
        var remaining = field.trimmingCharacters(in: .whitespaces).uppercased()
        let nsRange = NSRange(remaining.startIndex..., in: remaining)

        // Speed
        if let match = speedPattern.firstMatch(in: remaining, range: nsRange) {
            let fullRange = Range(match.range, in: remaining)!
            speed = String(remaining[fullRange])

            let prefixRange = Range(match.range(at: 1), in: remaining)!
            let digitsRange = Range(match.range(at: 2), in: remaining)!
            let prefix = String(remaining[prefixRange])
            let digits = Int(remaining[digitsRange])!

            if prefix == "N" {
                speedKnots = digits
            } else {
                speedKnots = Int(round(Double(digits) / 1.852))
            }
            remaining = String(remaining[fullRange.upperBound...]).trimmingCharacters(in: .whitespaces)
        }

        // Level
        let levelNSRange = NSRange(remaining.startIndex..., in: remaining)
        if let match = levelPattern.firstMatch(in: remaining, range: levelNSRange) {
            let fullRange = Range(match.range, in: remaining)!
            level = String(remaining[fullRange])
            altitudeFeet = parseAltitude(level!)
            remaining = String(remaining[fullRange.upperBound...]).trimmingCharacters(in: .whitespaces)
        }

        rawRoute = remaining.isEmpty ? nil : remaining
    }

    private static func parseField16(
        _ field: String,
        icao: inout String,
        eet: inout Int?,
        alternates: inout [String]
    ) {
        let trimmed = field.trimmingCharacters(in: .whitespaces).uppercased()
        guard trimmed.count >= 4 else { return }
        icao = String(trimmed.prefix(4))

        if trimmed.count >= 8 {
            let eetStr = String(trimmed.dropFirst(4).prefix(4))
            if let hour = Int(eetStr.prefix(2)), let min = Int(eetStr.suffix(2)),
               (0...99).contains(hour), (0...59).contains(min) {
                eet = hour * 60 + min
            }
        }

        // Alternates after first 8 chars
        if trimmed.count > 8 {
            let remainder = String(trimmed.dropFirst(8)).trimmingCharacters(in: .whitespaces)
            let tokens = remainder.split(separator: " ").map(String.init)
            alternates = tokens.filter { $0.count == 4 && $0.allSatisfy(\.isLetter) }
        }
    }

    private static func parseField18(
        _ field: String,
        otherInfo: inout [String: String],
        dateOfFlight: inout Date?
    ) {
        let trimmed = field.trimmingCharacters(in: .whitespaces)
        if trimmed == "0" || trimmed.isEmpty { return }

        // Find KEY/ positions
        let pattern = try! NSRegularExpression(pattern: #"\b([A-Z]{2,4})/"#)
        let nsRange = NSRange(trimmed.startIndex..., in: trimmed)
        let matches = pattern.matches(in: trimmed, range: nsRange)

        var positions: [(start: Int, key: String, valStart: Int)] = []
        for match in matches {
            let keyRange = Range(match.range(at: 1), in: trimmed)!
            let key = String(trimmed[keyRange]).uppercased()
            if field18Keys.contains(key) {
                let fullRange = Range(match.range, in: trimmed)!
                let startOffset = trimmed.distance(from: trimmed.startIndex, to: fullRange.lowerBound)
                let valOffset = trimmed.distance(from: trimmed.startIndex, to: fullRange.upperBound)
                positions.append((startOffset, key, valOffset))
            }
        }

        for (i, pos) in positions.enumerated() {
            let valStart = trimmed.index(trimmed.startIndex, offsetBy: pos.valStart)
            let valEnd: String.Index
            if i + 1 < positions.count {
                valEnd = trimmed.index(trimmed.startIndex, offsetBy: positions[i + 1].start)
            } else {
                valEnd = trimmed.endIndex
            }
            let value = trimmed[valStart..<valEnd].trimmingCharacters(in: .whitespaces)
            otherInfo[pos.key] = value
        }

        // Extract DOF → date
        if let dof = otherInfo["DOF"], dof.count >= 6 {
            let clean = String(dof.prefix(6))
            if let yy = Int(clean.prefix(2)),
               let mm = Int(clean.dropFirst(2).prefix(2)),
               let dd = Int(clean.suffix(2)) {
                var components = DateComponents()
                components.year = 2000 + yy
                components.month = mm
                components.day = dd
                components.timeZone = TimeZone(identifier: "UTC")
                dateOfFlight = Calendar(identifier: .gregorian).date(from: components)
            }
        }
    }

    // MARK: - Route Token Parsing

    private static func parseRouteTokens(
        _ rawRoute: String?,
        resolver: RoutePointResolver?,
        waypointNames: inout [String],
        waypointCoords: inout [RoutePoint]
    ) {
        guard let route = rawRoute else { return }

        for token in route.split(separator: " ").map(String.init) {
            let t = token.trimmingCharacters(in: .whitespaces).uppercased()
            if t.isEmpty { continue }

            // Skip filtered tokens
            if skipTokens.contains(t) { continue }

            // GPS coordinate
            if let coord = parseICAOCoordinate(t) {
                waypointNames.append(t)
                waypointCoords.append(RoutePoint(
                    name: t,
                    latitude: coord.latitude,
                    longitude: coord.longitude,
                    pointType: "gps"
                ))
                continue
            }

            // Airway — skip
            let tNSRange = NSRange(t.startIndex..., in: t)
            if airwayPattern.firstMatch(in: t, range: tNSRange) != nil {
                continue
            }

            // Waypoint or airport
            waypointNames.append(t)
            if let resolver = resolver, let point = resolver.resolve(t) {
                waypointCoords.append(point)
            }
        }
    }

    // MARK: - ICAO Coordinate Parsing

    /// Parse ICAO route coordinate: DDMM[NS]DDDMM[EW] or DDMMSS[NS]DDDMMSS[EW]
    static func parseICAOCoordinate(_ s: String) -> CLLocationCoordinate2D? {
        let nsRange = NSRange(s.startIndex..., in: s)

        // Try degrees+minutes (11 chars)
        if let m = icaoCoordDM.firstMatch(in: s, range: nsRange) {
            guard let latDeg = intGroup(m, 1, in: s),
                  let latMin = intGroup(m, 2, in: s),
                  let latHem = strGroup(m, 3, in: s),
                  let lonDeg = intGroup(m, 4, in: s),
                  let lonMin = intGroup(m, 5, in: s),
                  let lonHem = strGroup(m, 6, in: s) else { return nil }

            var lat = Double(latDeg) + Double(latMin) / 60.0
            var lon = Double(lonDeg) + Double(lonMin) / 60.0
            if latHem == "S" { lat = -lat }
            if lonHem == "W" { lon = -lon }
            return CLLocationCoordinate2D(latitude: lat, longitude: lon)
        }

        // Try degrees+minutes+seconds (15 chars)
        if let m = icaoCoordDMS.firstMatch(in: s, range: nsRange) {
            guard let latDeg = intGroup(m, 1, in: s),
                  let latMin = intGroup(m, 2, in: s),
                  let latSec = intGroup(m, 3, in: s),
                  let latHem = strGroup(m, 4, in: s),
                  let lonDeg = intGroup(m, 5, in: s),
                  let lonMin = intGroup(m, 6, in: s),
                  let lonSec = intGroup(m, 7, in: s),
                  let lonHem = strGroup(m, 8, in: s) else { return nil }

            var lat = Double(latDeg) + Double(latMin) / 60.0 + Double(latSec) / 3600.0
            var lon = Double(lonDeg) + Double(lonMin) / 60.0 + Double(lonSec) / 3600.0
            if latHem == "S" { lat = -lat }
            if lonHem == "W" { lon = -lon }
            return CLLocationCoordinate2D(latitude: lat, longitude: lon)
        }

        return nil
    }

    // MARK: - Altitude Parsing

    static func parseAltitude(_ level: String) -> Int? {
        if level == "VFR" || level == "IFR" { return nil }
        guard level.count >= 4 else { return nil }
        let prefix = level.prefix(1)
        guard let digits = Int(level.dropFirst()) else { return nil }

        switch prefix {
        case "F": return digits * 100
        case "A": return digits * 100
        case "S": return Int(round(Double(digits) * 10.0 * 3.28084))
        case "M": return Int(round(Double(digits) * 10.0 * 3.28084))
        default: return nil
        }
    }

    // MARK: - Regex Helpers

    private static func intGroup(_ match: NSTextCheckingResult, _ group: Int, in s: String) -> Int? {
        guard let range = Range(match.range(at: group), in: s) else { return nil }
        return Int(s[range])
    }

    private static func strGroup(_ match: NSTextCheckingResult, _ group: Int, in s: String) -> String? {
        guard let range = Range(match.range(at: group), in: s) else { return nil }
        return String(s[range])
    }
}
