import Foundation
import FMDB
@testable import RZFlight

final class TestSupport {
    static let shared = TestSupport()
    let db: FMDatabase?
    let known: KnownAirports?

    private init() {
        let thisSourceFile = URL(fileURLWithPath: #file)
        let rootDirectory = thisSourceFile
            .deletingLastPathComponent()
            .deletingLastPathComponent()
            .deletingLastPathComponent()
        let resourceURL = rootDirectory
            .appendingPathComponent("euro_aip/example")
            .appendingPathComponent("airports.db")
        if FileManager.default.fileExists(atPath: resourceURL.path) {
            let database = FMDatabase(url: resourceURL)
            database.open()
            self.db = database
            self.known = KnownAirports(db: database)
        } else {
            self.db = nil
            self.known = nil
        }
    }
}


