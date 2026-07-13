import Foundation
import XCTest
@testable import SandwalkCore

final class PathSupportTests: XCTestCase {
    func testAugmentedPATHContainsHomebrewPaths() {
        let path = PathSupport.augmentedPATH
        let parts = Set(path.split(separator: ":").map(String.init))

        XCTAssertTrue(parts.contains("/opt/homebrew/bin"))
        XCTAssertTrue(parts.contains("/opt/homebrew/sbin"))
        XCTAssertTrue(parts.contains("/usr/local/bin"))

        let home = NSHomeDirectory()
        XCTAssertTrue(parts.contains("\(home)/.local/bin"))
        XCTAssertTrue(parts.contains("\(home)/.cargo/bin"))
    }

    func testProcessEnvironmentMergesExtrasAndAugmentsPATH() {
        let env = PathSupport.processEnvironment(merging: [
            "SANDWALK_TEST_KEY": "hello",
        ])

        XCTAssertEqual(env["SANDWALK_TEST_KEY"], "hello")
        XCTAssertEqual(env["PATH"], PathSupport.augmentedPATH)
        XCTAssertTrue(env["PATH"]?.contains("/opt/homebrew/bin") == true)
    }

    func testProcessEnvironmentExtraPATHOverridesAugmented() {
        // `merging` applies after PATH augmentation, so callers can override.
        let env = PathSupport.processEnvironment(merging: [
            "PATH": "/custom/bin",
        ])
        XCTAssertEqual(env["PATH"], "/custom/bin")
    }

    func testWhichResolvesAbsoluteExecutablePaths() {
        XCTAssertEqual(PathSupport.which("/bin/zsh"), "/bin/zsh")
        XCTAssertEqual(PathSupport.which("/usr/bin/true"), "/usr/bin/true")
    }

    func testWhichReturnsNilForMissingAbsolutePath() {
        XCTAssertNil(PathSupport.which("/this/path/does/not/exist-\(UUID().uuidString)"))
    }

    func testWhichReturnsNilForNonExecutableFile() throws {
        let file = FileManager.default.temporaryDirectory
            .appendingPathComponent("sandwalk-path-support-\(UUID().uuidString).txt")
        try "not executable".write(to: file, atomically: true, encoding: .utf8)
        defer { try? FileManager.default.removeItem(at: file) }
        XCTAssertNil(PathSupport.which(file.path))
    }

    func testWhichResolvesKnownSystemExecutable() {
        XCTAssertEqual(PathSupport.which("zsh"), "/bin/zsh")
    }
}
