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
        let identifierFormat: String?
        let type: String?
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
            case identifierFormat = "identifier_format"
            case type
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
            // Handle both 2-group (number, year) and 3-group (series, number, year) patterns
            let series: String?
            let numberStr: String
            let yearStr: String

            if match.numberOfRanges >= 4,
               let seriesRange = Range(match.range(at: 1), in: text),
               let numRange = Range(match.range(at: 2), in: text),
               let yrRange = Range(match.range(at: 3), in: text) {
                // 3 capture groups: series, number, year (e.g., AIC pattern)
                series = String(text[seriesRange])
                numberStr = String(text[numRange])
                yearStr = String(text[yrRange])
            } else if match.numberOfRanges >= 3,
                      let numRange = Range(match.range(at: 1), in: text),
                      let yrRange = Range(match.range(at: 2), in: text) {
                // 2 capture groups: number, year (e.g., SUP pattern)
                series = nil
                numberStr = String(text[numRange])
                yearStr = String(text[yrRange])
            } else {
                continue
            }

            // Normalize year to 4 digits
            let year = normalizeYear(yearStr)

            // Pad number with leading zeros
            let numberPadding = provider.numberPadding ?? 3
            let paddedNumber = String(repeating: "0", count: max(0, numberPadding - numberStr.count)) + numberStr

            // Build identifier using format string or default
            let identifier: String
            if let format = provider.identifierFormat {
                identifier = format
                    .replacingOccurrences(of: "{series}", with: series ?? "")
                    .replacingOccurrences(of: "{number}", with: paddedNumber)
                    .replacingOccurrences(of: "{year}", with: year)
            } else {
                identifier = "SUP \(paddedNumber)/\(year)"
            }

            // Generate URLs
            let searchURL = provider.searchUrl.flatMap { URL(string: $0) }
            let documentURLs = generateDocumentURLs(
                templates: provider.documentUrlTemplates,
                year: year,
                number: paddedNumber,
                series: series
            )

            let ref = DocumentReference(
                type: provider.type ?? "aip_supplement",
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
        number: String,
        series: String? = nil
    ) -> [URL] {
        var urls: [URL] = []

        for template in templates {
            var urlString = template
                .replacingOccurrences(of: "{year}", with: year)
                .replacingOccurrences(of: "{number}", with: number)

            if let series = series {
                urlString = urlString.replacingOccurrences(of: "{series}", with: series)
            }

            if let url = URL(string: urlString) {
                urls.append(url)
            }
        }

        return urls
    }
}
