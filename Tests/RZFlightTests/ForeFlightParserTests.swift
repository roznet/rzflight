import Testing
import Foundation
@testable import RZFlight

@Suite("ForeFlightParser Tests")
struct ForeFlightParserTests {

    @Test("Parse sample briefing and count NOTAMs")
    func testParseSampleBriefing() throws {
        let parser = ForeFlightParser()

        // Try to find sample briefing
        let samplePath = "tmp/sample_briefing.pdf"
        let url = URL(fileURLWithPath: samplePath)

        guard FileManager.default.fileExists(atPath: url.path) else {
            Issue.record("Sample briefing not found at \(samplePath)")
            return
        }

        let briefing = try parser.parse(url: url)

        print("Route: \(briefing.route?.departure ?? "?") -> \(briefing.route?.destination ?? "?")")
        print("Total NOTAMs: \(briefing.notams.count)")

        // Show first 5 NOTAMs
        print("\nFirst 5 NOTAMs:")
        for notam in briefing.notams.prefix(5) {
            print("  \(notam.id): \(notam.location) - \(notam.qCode ?? "no qcode")")
        }

        // We expect at least 100 NOTAMs based on Python parser result (231)
        #expect(briefing.notams.count > 100, "Expected at least 100 NOTAMs, got \(briefing.notams.count)")
    }

    @Test("Parse briefing with non-standard sections")
    func testParseBriefingWithNonStandardSections() throws {
        let parser = ForeFlightParser()

        let samplePath = "tmp/sample-briefing-3.pdf"
        let url = URL(fileURLWithPath: samplePath)

        guard FileManager.default.fileExists(atPath: url.path) else {
            Issue.record("Sample briefing not found at \(samplePath)")
            return
        }

        let briefing = try parser.parse(url: url)

        print("Route: \(briefing.route?.departure ?? "?") -> \(briefing.route?.destination ?? "?")")
        print("Total NOTAMs: \(briefing.notams.count)")

        // This briefing has no standard sections - parser should fall back to full text
        // Python parser finds 134, we expect similar
        #expect(briefing.notams.count > 100, "Expected at least 100 NOTAMs, got \(briefing.notams.count)")
    }

    @Test("Parse NOTAM text directly")
    func testParseNotamText() {
        let notamText = """
        E5272/24 NOTAMN
        Q) LFFF/QPDLT/I/NBO/A/000/999/4906N00202E005
        A) LFPT B) 2410270000 C) PERM
        E) POGO ROUTEING TIME RESTRICTIONS BTN LFPT AND LFPN
        """

        guard let notam = NotamParser.parse(notamText, source: "test") else {
            Issue.record("Failed to parse NOTAM")
            return
        }

        #expect(notam.id == "E5272/24")
        #expect(notam.location == "LFPT")
        #expect(notam.qCode == "QPDLT")
        #expect(notam.fir == "LFFF")
    }
}
