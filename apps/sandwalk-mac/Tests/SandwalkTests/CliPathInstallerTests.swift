import Foundation
import XCTest
@testable import SandwalkCore

final class CliPathInstallerTests: XCTestCase {
    private var tempHome: URL!
    private var fakePython: URL!

    override func setUpWithError() throws {
        let root = FileManager.default.temporaryDirectory
            .appendingPathComponent("sandwalk-cli-path-\(UUID().uuidString)", isDirectory: true)
        try FileManager.default.createDirectory(at: root, withIntermediateDirectories: true)
        tempHome = root

        let bin = root.appendingPathComponent("runtime/bin", isDirectory: true)
        try FileManager.default.createDirectory(at: bin, withIntermediateDirectories: true)
        fakePython = bin.appendingPathComponent("python3.12")
        try "#!/bin/bash\necho fake\n".write(to: fakePython, atomically: true, encoding: .utf8)
        try FileManager.default.setAttributes(
            [.posixPermissions: 0o755],
            ofItemAtPath: fakePython.path
        )
    }

    override func tearDownWithError() throws {
        if let tempHome {
            try? FileManager.default.removeItem(at: tempHome)
        }
        tempHome = nil
        fakePython = nil
    }

    func testInstallsManagedShim() {
        let outcome = CliPathInstaller.ensureInstalled(
            pythonURL: fakePython,
            homeDirectory: tempHome
        )
        guard case let .installed(path) = outcome else {
            return XCTFail("expected installed, got \(outcome)")
        }

        let shim = URL(fileURLWithPath: path)
        XCTAssertTrue(FileManager.default.isExecutableFile(atPath: shim.path))
        XCTAssertTrue(CliPathInstaller.isManagedShim(at: shim))

        let body = try! String(contentsOf: shim, encoding: .utf8)
        XCTAssertTrue(body.contains(fakePython.path))
        XCTAssertTrue(body.contains("-m cli"))
    }

    func testUpdatesManagedShimWhenPythonMoves() throws {
        _ = CliPathInstaller.ensureInstalled(
            pythonURL: fakePython,
            homeDirectory: tempHome
        )

        let moved = tempHome.appendingPathComponent("runtime/bin/python3.12-new")
        try FileManager.default.copyItem(at: fakePython, to: moved)
        try FileManager.default.setAttributes(
            [.posixPermissions: 0o755],
            ofItemAtPath: moved.path
        )

        let outcome = CliPathInstaller.ensureInstalled(
            pythonURL: moved,
            homeDirectory: tempHome
        )
        guard case let .updated(path) = outcome else {
            return XCTFail("expected updated, got \(outcome)")
        }
        let body = try String(contentsOf: URL(fileURLWithPath: path), encoding: .utf8)
        XCTAssertTrue(body.contains(moved.path))
    }

    func testLeavesForeignInstallAlone() throws {
        let bin = tempHome.appendingPathComponent(".local/bin", isDirectory: true)
        try FileManager.default.createDirectory(at: bin, withIntermediateDirectories: true)
        let foreign = bin.appendingPathComponent("sandwalk")
        try "#!/bin/bash\necho uv-tool\n".write(to: foreign, atomically: true, encoding: .utf8)
        try FileManager.default.setAttributes(
            [.posixPermissions: 0o755],
            ofItemAtPath: foreign.path
        )

        let outcome = CliPathInstaller.ensureInstalled(
            pythonURL: fakePython,
            homeDirectory: tempHome
        )
        guard case let .skippedForeignInstall(path) = outcome else {
            return XCTFail("expected skippedForeignInstall, got \(outcome)")
        }
        XCTAssertEqual(path, foreign.path)
        let body = try String(contentsOf: foreign, encoding: .utf8)
        XCTAssertEqual(body, "#!/bin/bash\necho uv-tool\n")
    }

    func testForceReplacesForeignInstall() throws {
        let bin = tempHome.appendingPathComponent(".local/bin", isDirectory: true)
        try FileManager.default.createDirectory(at: bin, withIntermediateDirectories: true)
        let foreign = bin.appendingPathComponent("sandwalk")
        try "#!/bin/bash\necho uv-tool\n".write(to: foreign, atomically: true, encoding: .utf8)
        try FileManager.default.setAttributes(
            [.posixPermissions: 0o755],
            ofItemAtPath: foreign.path
        )

        let outcome = CliPathInstaller.ensureInstalled(
            pythonURL: fakePython,
            homeDirectory: tempHome,
            force: true
        )
        guard case let .updated(path) = outcome else {
            return XCTFail("expected updated, got \(outcome)")
        }
        XCTAssertTrue(CliPathInstaller.isManagedShim(at: URL(fileURLWithPath: path)))
    }

    func testStatusReportsMissingAndReady() {
        let missing = CliPathInstaller.status(
            pythonURL: fakePython,
            homeDirectory: tempHome
        )
        XCTAssertEqual(missing["state"] as? String, "missing")

        _ = CliPathInstaller.ensureInstalled(
            pythonURL: fakePython,
            homeDirectory: tempHome
        )
        let ready = CliPathInstaller.status(
            pythonURL: fakePython,
            homeDirectory: tempHome
        )
        XCTAssertEqual(ready["state"] as? String, "ready")
        XCTAssertEqual(ready["managed"] as? Bool, true)
    }

    func testUnchangedWhenShimAlreadyCorrect() {
        _ = CliPathInstaller.ensureInstalled(
            pythonURL: fakePython,
            homeDirectory: tempHome
        )
        let second = CliPathInstaller.ensureInstalled(
            pythonURL: fakePython,
            homeDirectory: tempHome
        )
        guard case .unchanged = second else {
            return XCTFail("expected unchanged, got \(second)")
        }
    }

    func testAddsZprofilePATHBlockOnce() throws {
        XCTAssertTrue(CliPathInstaller.ensureLocalBinOnPATH(homeDirectory: tempHome))
        let zprofile = tempHome.appendingPathComponent(".zprofile")
        let first = try String(contentsOf: zprofile, encoding: .utf8)
        XCTAssertTrue(first.contains(CliPathInstaller.pathBlockMarker))
        XCTAssertTrue(first.contains("$HOME/.local/bin"))

        XCTAssertFalse(CliPathInstaller.ensureLocalBinOnPATH(homeDirectory: tempHome))
        let second = try String(contentsOf: zprofile, encoding: .utf8)
        XCTAssertEqual(first, second)
    }

    func testSkipsZprofileWhenLocalBinAlreadyReferenced() throws {
        let zshrc = tempHome.appendingPathComponent(".zshrc")
        try "export PATH=\"$HOME/.local/bin:$PATH\"\n".write(
            to: zshrc,
            atomically: true,
            encoding: .utf8
        )
        XCTAssertFalse(CliPathInstaller.ensureLocalBinOnPATH(homeDirectory: tempHome))
        XCTAssertFalse(
            FileManager.default.fileExists(
                atPath: tempHome.appendingPathComponent(".zprofile").path
            )
        )
    }
}
