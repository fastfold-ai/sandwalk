import XCTest
@testable import SandwalkCore

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
