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

    /// A failed attempt leaves its error in the log. Once a later process starts
    /// successfully, that stale line must not keep the menubar in an error state
    /// while the server is actually serving.
    func testIgnoresFatalErrorFromBeforeTheCurrentRun() throws {
        let dir = FileManager.default.temporaryDirectory
            .appendingPathComponent("sandwalk-diag-\(UUID().uuidString)", isDirectory: true)
        try FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        defer { try? FileManager.default.removeItem(at: dir) }

        let log = dir.appendingPathComponent("server.log")
        let body = """
        Error: Another Sandwalk server already has this database open (held by pid 21528): /Users/x/.sandwalk/agent-server.db
        INFO:     Started server process [21528]
        INFO:     Application startup complete.
        INFO:     Uvicorn running on http://127.0.0.1:8787
        INFO:     127.0.0.1:55442 - "GET /api/health HTTP/1.1" 200 OK
        """
        try body.write(to: log, atomically: true, encoding: .utf8)

        XCTAssertNil(ServerStartupDiagnostics.recentFatalHint(logURL: log))
    }

    func testStillDetectsFatalErrorAfterTheLastStartup() throws {
        let dir = FileManager.default.temporaryDirectory
            .appendingPathComponent("sandwalk-diag-\(UUID().uuidString)", isDirectory: true)
        try FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        defer { try? FileManager.default.removeItem(at: dir) }

        let log = dir.appendingPathComponent("server.log")
        let body = """
        INFO:     Started server process [111]
        INFO:     Uvicorn running on http://127.0.0.1:8787
        Error: Another Sandwalk server already has this database open (held by pid 222): /Users/x/.sandwalk/agent-server.db
        """
        try body.write(to: log, atomically: true, encoding: .utf8)

        let hint = ServerStartupDiagnostics.recentFatalHint(logURL: log)
        XCTAssertNotNil(hint)
        XCTAssertTrue(hint?.localizedCaseInsensitiveContains("locked") == true)
    }

    func testSignalledExitIsNotFatalDespiteStaleLogError() throws {
        let dir = FileManager.default.temporaryDirectory
            .appendingPathComponent("sandwalk-diag-\(UUID().uuidString)", isDirectory: true)
        try FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        defer { try? FileManager.default.removeItem(at: dir) }

        let log = dir.appendingPathComponent("server.log")
        try """
        Error: Another Sandwalk server already has this database open (held by pid 1): /tmp/x.db
        """.write(to: log, atomically: true, encoding: .utf8)

        // Quit / Restart sends SIGTERM; that is intentional, not a fatal fault.
        for code in [Int32(15), 9, 143, 137] {
            let classified = ServerStartupDiagnostics.classifyExit(
                code: code,
                everHealthy: true,
                consecutiveStartupFailures: 0,
                logURL: log
            )
            XCTAssertFalse(classified.isFatal, "code \(code) should allow restart")
        }
    }

    func testCurrentRunSliceKeepsTextWithoutAMarker() {
        let text = "Error: something bad\nmore context\n"
        XCTAssertEqual(ServerStartupDiagnostics.currentRunSlice(of: text), text)
    }

    func testCurrentRunSliceUsesTheLastStartup() {
        let text = """
        Started server process [1]
        Error: first run failed
        Started server process [2]
        healthy
        """
        let slice = ServerStartupDiagnostics.currentRunSlice(of: text)
        XCTAssertTrue(slice.contains("[2]"))
        XCTAssertFalse(slice.contains("first run failed"))
    }

    /// Toggling Network → Allow remote connections without an API key makes
    /// `sandwalk serve` exit(2). The menubar used to show a bare "Exited with
    /// code 2 — stopped auto-restart" with no hint about the cause.
    func testExplainsRemoteBindWithoutApiKey() throws {
        let dir = FileManager.default.temporaryDirectory
            .appendingPathComponent("sandwalk-diag-\(UUID().uuidString)", isDirectory: true)
        try FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        defer { try? FileManager.default.removeItem(at: dir) }

        let log = dir.appendingPathComponent("server.log")
        // Verbatim CLI output.
        let body = """
        Server configuration error: Public / LAN mode requires --api-key, \
        FASTFOLD_SERVER_API_KEY, or `sandwalk auth enable` with a configured key \
        (`sandwalk auth generate` then `sandwalk auth enable`).
        """
        try body.write(to: log, atomically: true, encoding: .utf8)

        let classified = ServerStartupDiagnostics.classifyExit(
            code: 2,
            everHealthy: false,
            consecutiveStartupFailures: 1,
            logURL: log
        )
        XCTAssertTrue(classified.isFatal, "respawning cannot fix a missing key")
        XCTAssertTrue(classified.message.localizedCaseInsensitiveContains("API key"))
        XCTAssertTrue(
            classified.message.localizedCaseInsensitiveContains("remote"),
            "message should point at the Allow remote toggle"
        )
    }
}
