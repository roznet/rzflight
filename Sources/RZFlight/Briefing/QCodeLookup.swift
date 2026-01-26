//
//  QCodeLookup.swift
//  RZFlight
//
//  Lookup service for ICAO Q-code meanings.
//  Loads from q_codes.json and provides human-readable descriptions.
//

import Foundation

/// Service for looking up ICAO Q-code meanings.
///
/// Q-codes follow the format: Q + Subject(2) + Condition(2)
/// Example: QMRLC = Q + MR (Runway) + LC (Closed)
///
/// Usage:
/// ```swift
/// if let info = QCodeLookup.shared.lookup("QMRLC") {
///     print(info.displayText)  // "Runway: Closed"
/// }
/// ```
public enum QCodeLookup {

    // MARK: - Types

    private struct QCodeData: Codable {
        let subjects: [String: SubjectInfo]
        let conditions: [String: ConditionInfo]
    }

    private struct SubjectInfo: Codable {
        let meaning: String
        let phrase: String
        let cat: String
    }

    private struct ConditionInfo: Codable {
        let meaning: String
        let phrase: String
        let cat: String
    }

    // MARK: - Singleton Data

    /// Loaded Q-code data (subjects and conditions)
    private static var qCodeData: QCodeData? = {
        loadQCodeData()
    }()

    // MARK: - Public Interface

    /// Look up a Q-code and return parsed information.
    ///
    /// - Parameter qCode: Q-code string (e.g., "QMRLC" or "MRLC")
    /// - Returns: QCodeInfo with subject, condition, and display text, or nil if invalid
    public static func lookup(_ qCode: String?) -> QCodeInfo? {
        guard let qCode = qCode, !qCode.isEmpty else { return nil }
        guard let data = qCodeData else { return nil }

        // Normalize: remove Q prefix if present
        var code = qCode.uppercased()
        if code.hasPrefix("Q") {
            code = String(code.dropFirst())
        }

        // Need at least 2 chars for subject, ideally 4 for subject + condition
        guard code.count >= 2 else { return nil }

        let subjectCode = String(code.prefix(2))
        let conditionCode = code.count >= 4 ? String(code.dropFirst(2).prefix(2)) : nil

        // Look up subject
        guard let subject = data.subjects[subjectCode] else {
            // Unknown subject - return basic info
            return createBasicInfo(
                qCode: qCode.uppercased(),
                subjectCode: subjectCode,
                conditionCode: conditionCode
            )
        }

        // Look up condition
        let condition = conditionCode.flatMap { data.conditions[$0] }

        return createQCodeInfo(
            qCode: qCode.uppercased(),
            subjectCode: subjectCode,
            subject: subject,
            conditionCode: conditionCode,
            condition: condition
        )
    }

    /// Check if a Q-code represents a checklist NOTAM (QKKKK).
    public static func isChecklist(_ qCode: String?) -> Bool {
        guard let code = qCode?.uppercased() else { return false }
        return code == "QKKKK" || code == "KKKK"
    }

    /// Check if a Q-code indicates plain language follows (XX condition).
    public static func isPlainLanguage(_ qCode: String?) -> Bool {
        guard let code = qCode?.uppercased() else { return false }
        let normalized = code.hasPrefix("Q") ? String(code.dropFirst()) : code
        return normalized.count >= 4 && normalized.suffix(2) == "XX"
    }

    // MARK: - Private Methods

    private static func loadQCodeData() -> QCodeData? {
        guard let url = Bundle.module.url(forResource: "q_codes", withExtension: "json") else {
            print("Warning: q_codes.json not found in bundle")
            return nil
        }

        do {
            let data = try Data(contentsOf: url)
            return try JSONDecoder().decode(QCodeData.self, from: data)
        } catch {
            print("Warning: Failed to load q_codes.json: \(error)")
            return nil
        }
    }

    private static func createQCodeInfo(
        qCode: String,
        subjectCode: String,
        subject: SubjectInfo,
        conditionCode: String?,
        condition: ConditionInfo?
    ) -> QCodeInfo {
        let displayText: String
        let shortText: String

        if let condition = condition {
            displayText = "\(subject.meaning): \(condition.meaning)"
            shortText = "\(subject.phrase.uppercased()) \(condition.phrase.uppercased())"
        } else {
            displayText = subject.meaning
            shortText = subject.phrase.uppercased()
        }

        return QCodeInfo(
            qCode: qCode,
            subjectCode: subjectCode,
            subjectMeaning: subject.meaning,
            subjectPhrase: subject.phrase,
            subjectCategory: subject.cat,
            conditionCode: conditionCode ?? "",
            conditionMeaning: condition?.meaning ?? "",
            conditionPhrase: condition?.phrase ?? "",
            conditionCategory: condition?.cat ?? "",
            displayText: displayText,
            shortText: shortText,
            isChecklist: isChecklist(qCode),
            isPlainLanguage: isPlainLanguage(qCode)
        )
    }

    private static func createBasicInfo(
        qCode: String,
        subjectCode: String,
        conditionCode: String?
    ) -> QCodeInfo {
        QCodeInfo(
            qCode: qCode,
            subjectCode: subjectCode,
            subjectMeaning: "Unknown",
            subjectPhrase: subjectCode.lowercased(),
            subjectCategory: "Other",
            conditionCode: conditionCode ?? "",
            conditionMeaning: "",
            conditionPhrase: conditionCode?.lowercased() ?? "",
            conditionCategory: "",
            displayText: qCode,
            shortText: qCode,
            isChecklist: isChecklist(qCode),
            isPlainLanguage: isPlainLanguage(qCode)
        )
    }
}
