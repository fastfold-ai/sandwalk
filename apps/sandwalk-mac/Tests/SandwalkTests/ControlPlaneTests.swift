import XCTest
@testable import SandwalkCore

/// `ControlPlane` is `@MainActor`, so these statics must be reached from the main
/// actor — without this the suite fails to compile under Swift 6 concurrency.
@MainActor
final class ControlPlaneTests: XCTestCase {
    func testControlFileURLIsUnderApplicationSupport() {
        let url = ControlPlane.controlFileURL()
        XCTAssertTrue(url.path.contains("Application Support/Sandwalk/control.json"))
    }

    func testLogsDirectoryIsUnderApplicationSupport() {
        let url = ControlPlane.logsDirectory()
        XCTAssertTrue(url.path.hasSuffix("Sandwalk/logs") || url.path.contains("Sandwalk/logs"))
    }
}
