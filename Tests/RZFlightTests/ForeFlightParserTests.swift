import Testing
import Foundation
@testable import RZFlight

@Suite("ForeFlightParser Tests")
struct ForeFlightParserTests {

    @Test("Parse sample briefings from tmp directory")
    func testParseSampleBriefings() throws {
        let parser = ForeFlightParser()
        let fm = FileManager.default

        // Find all sample-briefing*.pdf files in tmp/
        let tmpURL = URL(fileURLWithPath: "tmp")
        guard fm.fileExists(atPath: tmpURL.path),
              let contents = try? fm.contentsOfDirectory(at: tmpURL, includingPropertiesForKeys: nil) else {
            print("Skipping: tmp/ directory not found or empty")
            return
        }

        let pdfFiles = contents.filter { $0.pathExtension == "pdf" &&
            ($0.lastPathComponent.hasPrefix("sample") || $0.lastPathComponent.contains("briefing")) }

        guard !pdfFiles.isEmpty else {
            print("Skipping: No sample briefing PDFs found in tmp/")
            return
        }

        print("Found \(pdfFiles.count) sample briefing(s)")

        for url in pdfFiles {
            print("\n--- Parsing: \(url.lastPathComponent) ---")

            let briefing = try parser.parse(url: url)

            print("Route: \(briefing.route?.departure ?? "?") -> \(briefing.route?.destination ?? "?")")
            print("Total NOTAMs: \(briefing.notams.count)")

            // Show first 3 NOTAMs with Q-code info
            print("First 3 NOTAMs:")
            for notam in briefing.notams.prefix(3) {
                let qInfo = notam.qCodeInfo?.displayText ?? notam.qCode ?? "no qcode"
                print("  \(notam.id): \(notam.location) - \(qInfo)")
            }

            // We expect at least 50 NOTAMs from any real briefing
            #expect(briefing.notams.count > 50, "Expected at least 50 NOTAMs from \(url.lastPathComponent), got \(briefing.notams.count)")
        }
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

    @Test("Q-code lookup returns human-readable meanings")
    func testQCodeLookup() {
        // Test runway closed
        let runwayClosed = QCodeLookup.lookup("QMRLC")
        #expect(runwayClosed != nil)
        #expect(runwayClosed?.subjectCode == "MR")
        #expect(runwayClosed?.subjectMeaning == "Runway")
        #expect(runwayClosed?.conditionCode == "LC")
        #expect(runwayClosed?.conditionMeaning == "Closed")
        #expect(runwayClosed?.displayText == "Runway: Closed")

        // Test obstacle work in progress
        let obstacleWip = QCodeLookup.lookup("QOBHW")
        #expect(obstacleWip != nil)
        #expect(obstacleWip?.subjectMeaning == "Obstacle")
        #expect(obstacleWip?.conditionMeaning == "Work in progress")

        // Test aerodrome closed
        let adClosed = QCodeLookup.lookup("QFALC")
        #expect(adClosed != nil)
        #expect(adClosed?.displayText == "Aerodrome: Closed")

        // Test VOR unserviceable
        let vorUs = QCodeLookup.lookup("QNVAS")
        #expect(vorUs != nil)
        #expect(vorUs?.subjectMeaning == "VOR")
        #expect(vorUs?.conditionMeaning == "Unserviceable")

        // Test parachute jumping will take place
        let pje = QCodeLookup.lookup("QWPLW")
        #expect(pje != nil)
        #expect(pje?.subjectMeaning == "Parachute jumping/Hang gliding")
        #expect(pje?.conditionMeaning == "Will take place")
    }

    @Test("NOTAM parser includes Q-code info")
    func testNotamParserIncludesQCodeInfo() {
        let notamText = """
        A1234/24 NOTAMN
        Q) LFFF/QMRLC/IV/NBO/A/000/999/4901N00225E005
        A) LFPG B) 2401150800 C) 2401152000
        E) RWY 09L/27R CLSD DUE TO MAINTENANCE
        """

        guard let notam = NotamParser.parse(notamText, source: "test") else {
            Issue.record("Failed to parse NOTAM")
            return
        }

        #expect(notam.qCode == "QMRLC")
        #expect(notam.qCodeInfo != nil)
        #expect(notam.qCodeInfo?.displayText == "Runway: Closed")
        #expect(notam.qCodeInfo?.shortText == "RWY CLSD")
    }
}
