import XCTest
@testable import SandwalkCore

final class ServerStartupDiagnosticsTests: XCTestCase {
    func testDetectsCorruptDatabaseInLogTail() throws {
        let dir = FileManager.default.temporaryDirectory
            .appendingPathComponent("sandwalk-diag-\(UUID().uuidString)", isDirectory: true)
        try FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        defer { try? FileManager.default.removeItem(at: dir) }

        let log = dir.appendingPathComponent("server.log")
        let body = """
        INFO: starting
        Error: Agent store database is corrupt (database disk image is malformed): /tmp/x.db. Refusing to auto-repair so settings are not silently rewritten.
        """
        try body.write(to: log, atomically: true, encoding: .utf8)

        let hint = ServerStartupDiagnostics.recentFatalHint(logURL: log)
        XCTAssertNotNil(hint)
        XCTAssertTrue(hint?.localizedCaseInsensitiveContains("corrupt") == true)

        let classified = ServerStartupDiagnostics.classifyExit(
            code: 1,
            everHealthy: false,
            consecutiveStartupFailures: 1,
            logURL: log
        )
        XCTAssertTrue(classified.isFatal)
        XCTAssertTrue(classified.message.localizedCaseInsensitiveContains("corrupt"))
    }

    func testAllowsTransientExitAfterHealthyRun() throws {
        let dir = FileManager.default.temporaryDirectory
            .appendingPathComponent("sandwalk-diag-\(UUID().uuidString)", isDirectory: true)
        try FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        defer { try? FileManager.default.removeItem(at: dir) }

        let log = dir.appendingPathComponent("server.log")
        try "INFO: running fine\n".write(to: log, atomically: true, encoding: .utf8)

        let classified = ServerStartupDiagnostics.classifyExit(
            code: 1,
            everHealthy: true,
            consecutiveStartupFailures: 0,
            logURL: log
        )
        XCTAssertFalse(classified.isFatal)
    }

    func testDetectsDatabaseLockInLogTail() throws {
        let dir = FileManager.default.temporaryDirectory
            .appendingPathComponent("sandwalk-diag-\(UUID().uuidString)", isDirectory: true)
        try FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        defer { try? FileManager.default.removeItem(at: dir) }

        let log = dir.appendingPathComponent("server.log")
        let body = """
        Error: Another Sandwalk server already has this database open (held by pid 55228): /Users/x/.sandwalk/agent-server.db
        """
        try body.write(to: log, atomically: true, encoding: .utf8)

        let classified = ServerStartupDiagnostics.classifyExit(
            code: 1,
            everHealthy: false,
            consecutiveStartupFailures: 1,
            logURL: log
        )
        XCTAssertTrue(classified.isFatal)
        XCTAssertTrue(classified.message.localizedCaseInsensitiveContains("locked"))
    }

    func testStopsAfterRepeatedStartupFailuresWithoutHealthy() throws {
        let dir = FileManager.default.temporaryDirectory
            .appendingPathComponent("sandwalk-diag-\(UUID().uuidString)", isDirectory: true)
        try FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        defer { try? FileManager.default.removeItem(at: dir) }

        let log = dir.appendingPathComponent("server.log")
        try "INFO: boom\n".write(to: log, atomically: true, encoding: .utf8)

        let first = ServerStartupDiagnostics.classifyExit(
            code: 1,
            everHealthy: false,
            consecutiveStartupFailures: 1,
            logURL: log
        )
        XCTAssertFalse(first.isFatal)

        let second = ServerStartupDiagnostics.classifyExit(
            code: 1,
            everHealthy: false,
            consecutiveStartupFailures: 2,
            logURL: log
        )
        XCTAssertTrue(second.isFatal)
        XCTAssertTrue(second.message.contains("repeated startup failure"))
    }
}
