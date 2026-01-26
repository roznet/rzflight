//
//  DocumentReference.swift
//  RZFlight
//
//  Document reference model for AIP supplements and other linked documents.
//  Extracted from NOTAM text when references to external documents are detected.
//

import Foundation

/// Reference to an external document found in NOTAM text.
///
/// Examples:
/// - AIP Supplement: "SUP 059/2025" from UK NATS
/// - AIP Supplement: "SUP 009/26" from France SIA
public struct DocumentReference: Codable, Sendable, Hashable {
    /// Document type (e.g., "aip_supplement")
    public let type: String

    /// Original reference string (e.g., "SUP 059/2025")
    public let identifier: String

    /// Provider ID that matched (e.g., "uk_nats", "france_sia")
    public let provider: String

    /// Human-readable provider name
    public let providerName: String

    /// URL to search/browse page for this document type
    public let searchURL: URL?

    /// Direct URLs to the document(s)
    public let documentURLs: [URL]

    enum CodingKeys: String, CodingKey {
        case type
        case identifier
        case provider
        case providerName = "provider_name"
        case searchURL = "search_url"
        case documentURLs = "document_urls"
    }

    public init(
        type: String,
        identifier: String,
        provider: String,
        providerName: String,
        searchURL: URL? = nil,
        documentURLs: [URL] = []
    ) {
        self.type = type
        self.identifier = identifier
        self.provider = provider
        self.providerName = providerName
        self.searchURL = searchURL
        self.documentURLs = documentURLs
    }

    public init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        type = try container.decode(String.self, forKey: .type)
        identifier = try container.decode(String.self, forKey: .identifier)
        provider = try container.decode(String.self, forKey: .provider)
        providerName = try container.decodeIfPresent(String.self, forKey: .providerName) ?? ""

        // Handle URL decoding from string
        if let searchURLString = try container.decodeIfPresent(String.self, forKey: .searchURL) {
            searchURL = URL(string: searchURLString)
        } else {
            searchURL = nil
        }

        // Handle document URLs
        let urlStrings = try container.decodeIfPresent([String].self, forKey: .documentURLs) ?? []
        documentURLs = urlStrings.compactMap { URL(string: $0) }
    }

    public func encode(to encoder: Encoder) throws {
        var container = encoder.container(keyedBy: CodingKeys.self)
        try container.encode(type, forKey: .type)
        try container.encode(identifier, forKey: .identifier)
        try container.encode(provider, forKey: .provider)
        try container.encode(providerName, forKey: .providerName)
        try container.encodeIfPresent(searchURL?.absoluteString, forKey: .searchURL)
        try container.encode(documentURLs.map { $0.absoluteString }, forKey: .documentURLs)
    }
}
