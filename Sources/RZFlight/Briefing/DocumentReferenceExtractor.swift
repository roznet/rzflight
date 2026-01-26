//
//  DocumentReferenceExtractor.swift
//  RZFlight
//
//  Extract document references from NOTAM text.
//  Configuration loaded from document_references.json.
//

import Foundation

/// Extract document references from NOTAM text using configurable providers.
///
/// Providers are defined in document_references.json and specify:
/// - Trigger patterns to detect when the provider applies
/// - Reference patterns to extract document identifiers (e.g., SUP numbers)
/// - URL templates to generate direct document links
///
/// Example:
/// ```swift
/// let refs = DocumentReferenceExtractor.extract(from: notamText)
/// for ref in refs {
///     print("\(ref.identifier): \(ref.documentURLs)")
/// }
/// ```
public enum DocumentReferenceExtractor {

    // MARK: - Configuration Types

    private struct Config: Codable {
        let providers: [Provider]
    }

    private struct Provider: Codable {
        let id: String
        let name: String
        let countryCode: String?
        let triggerPatterns: [String]
        let referencePattern: String
        let searchUrl: String?
        let documentUrlTemplates: [String]
        let yearFormat: String?
        let numberPadding: Int?

        enum CodingKeys: String, CodingKey {
            case id
            case name
            case countryCode = "country_code"
            case triggerPatterns = "trigger_patterns"
            case referencePattern = "reference_pattern"
            case searchUrl = "search_url"
            case documentUrlTemplates = "document_url_templates"
            case yearFormat = "year_format"
            case numberPadding = "number_padding"
        }
    }

    // MARK: - Singleton Data

    private static var providers: [Provider] = {
        loadConfig()
    }()

    // MARK: - Public Interface

    /// Extract document references from text.
    ///
    /// - Parameter text: NOTAM text to search
    /// - Returns: List of DocumentReference objects found in text
    public static func extract(from text: String) -> [DocumentReference] {
        guard !text.isEmpty else { return [] }

        let textUpper = text.uppercased()
        var references: [DocumentReference] = []
        var seenIdentifiers = Set<String>()

        for provider in providers {
            // Check if any trigger pattern matches
            guard matchesTrigger(text: textUpper, provider: provider) else {
                continue
            }

            // Extract references using this provider
            let providerRefs = extractWithProvider(text: textUpper, provider: provider)

            // Deduplicate
            for ref in providerRefs {
                let key = "\(ref.provider):\(ref.identifier)"
                if !seenIdentifiers.contains(key) {
                    seenIdentifiers.insert(key)
                    references.append(ref)
                }
            }
        }

        return references
    }

    // MARK: - Private Methods

    private static func loadConfig() -> [Provider] {
        guard let url = Bundle.module.url(forResource: "document_references", withExtension: "json") else {
            print("Warning: document_references.json not found in bundle")
            return []
        }

        do {
            let data = try Data(contentsOf: url)
            let config = try JSONDecoder().decode(Config.self, from: data)
            return config.providers
        } catch {
            print("Warning: Failed to load document_references.json: \(error)")
            return []
        }
    }

    private static func matchesTrigger(text: String, provider: Provider) -> Bool {
        for pattern in provider.triggerPatterns {
            if text.contains(pattern.uppercased()) {
                return true
            }
        }
        return false
    }

    private static func extractWithProvider(text: String, provider: Provider) -> [DocumentReference] {
        var references: [DocumentReference] = []

        guard let regex = try? NSRegularExpression(
            pattern: provider.referencePattern,
            options: [.caseInsensitive]
        ) else {
            return references
        }

        let range = NSRange(text.startIndex..., in: text)
        let matches = regex.matches(in: text, range: range)

        for match in matches {
            guard match.numberOfRanges >= 3,
                  let numberRange = Range(match.range(at: 1), in: text),
                  let yearRange = Range(match.range(at: 2), in: text) else {
                continue
            }

            let numberStr = String(text[numberRange])
            let yearStr = String(text[yearRange])

            // Normalize year to 4 digits
            let year = normalizeYear(yearStr)

            // Pad number with leading zeros
            let numberPadding = provider.numberPadding ?? 3
            let paddedNumber = String(repeating: "0", count: max(0, numberPadding - numberStr.count)) + numberStr

            // Build identifier
            let identifier = "SUP \(paddedNumber)/\(year)"

            // Generate URLs
            let searchURL = provider.searchUrl.flatMap { URL(string: $0) }
            let documentURLs = generateDocumentURLs(
                templates: provider.documentUrlTemplates,
                year: year,
                number: paddedNumber
            )

            let ref = DocumentReference(
                type: "aip_supplement",
                identifier: identifier,
                provider: provider.id,
                providerName: provider.name,
                searchURL: searchURL,
                documentURLs: documentURLs
            )
            references.append(ref)
        }

        return references
    }

    private static func normalizeYear(_ yearStr: String) -> String {
        if yearStr.count == 2 {
            // Assume 20xx for 2-digit years
            if let yearInt = Int(yearStr), yearInt > 50 {
                return "19\(yearStr)"
            } else {
                return "20\(yearStr)"
            }
        }
        return yearStr
    }

    private static func generateDocumentURLs(
        templates: [String],
        year: String,
        number: String
    ) -> [URL] {
        var urls: [URL] = []

        for template in templates {
            let urlString = template
                .replacingOccurrences(of: "{year}", with: year)
                .replacingOccurrences(of: "{number}", with: number)

            if let url = URL(string: urlString) {
                urls.append(url)
            }
        }

        return urls
    }
}
