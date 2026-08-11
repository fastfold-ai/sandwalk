import XCTest

@testable import SandwalkCore

/// A second helper instance is what produced "database is locked by another
/// process": each helper supervises its own `sandwalk serve`, and the loser
/// cannot take the exclusive SQLite lock.
final class SingleInstanceGuardTests: XCTestCase {
    func testDoesNotReportSelfAsAnotherInstance() {
        // This test process is not a helper bundle, so the guard must stay quiet
        // rather than matching our own pid and refusing to launch.
        let other = SingleInstanceGuard.otherRunningHelperPid()
        XCTAssertNotEqual(other, ProcessInfo.processInfo.processIdentifier)
    }

    func testReportsNoPeerOrAPositivePid() {
        // Whatever the machine state, the result must be either nil or a usable
        // pid — never 0 or negative, which `kill` would interpret as a group.
        if let pid = SingleInstanceGuard.otherRunningHelperPid() {
            XCTAssertGreaterThan(pid, 0)
        }
    }
}

final class ProcessGroupSignalTests: XCTestCase {
    /// `sandwalk serve` runs uvicorn, which forks a worker; signaling only the
    /// parent used to leave that worker holding port 8787 and the database lock.
    func testSignalProcessGroupTerminatesChildProcess() throws {
        let task = Process()
        task.executableURL = URL(fileURLWithPath: "/bin/sh")
        // setsid-like: the child leads its own group, mirroring the agent spawn.
        task.arguments = ["-c", "sleep 30"]
        try task.run()
        let pid = task.processIdentifier
        XCTAssertGreaterThan(pid, 0)

        PortSupport.signalProcessGroup(pid: pid, signal: SIGTERM)

        let deadline = Date().addingTimeInterval(5)
        while Date() < deadline, task.isRunning {
            usleep(50_000)
        }
        XCTAssertFalse(task.isRunning, "signalProcessGroup should reap the child")
    }

    func testSignalProcessGroupIgnoresInvalidPid() {
        // Must never send to pid 0 / negatives: that would signal our own group
        // (or every process) instead of the intended child.
        PortSupport.signalProcessGroup(pid: 0, signal: SIGTERM)
        PortSupport.signalProcessGroup(pid: -1, signal: SIGTERM)
    }
}
