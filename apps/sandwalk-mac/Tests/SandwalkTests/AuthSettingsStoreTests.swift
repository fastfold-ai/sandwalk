import Foundation
import XCTest
@testable import SandwalkCore

final class AuthSettingsStoreTests: XCTestCase {
    private var savedSettings: Data?

    override func setUp() {
        super.setUp()
        savedSettings = SettingsTestSupport.backupSettings()
        SettingsTestSupport.removeSettings()
    }

    override func tearDown() {
        SettingsTestSupport.restoreSettings(from: savedSettings)
        super.tearDown()
    }
    func testEmptyAuthSettings() {
        let empty = SandwalkAuthSettings.empty
        XCTAssertEqual(empty.apiKey, "")
        XCTAssertFalse(empty.authEnabled)
        XCTAssertEqual(empty.secretKey, "")
        XCTAssertFalse(empty.apiKeyConfigured)
    }

    func testAPIKeyConfiguredTrimsWhitespace() {
        let blank = SandwalkAuthSettings(apiKey: "   ", authEnabled: true, secretKey: "x")
        XCTAssertFalse(blank.apiKeyConfigured)

        let set = SandwalkAuthSettings(apiKey: "sk-sandwalk-abc", authEnabled: true, secretKey: "x")
        XCTAssertTrue(set.apiKeyConfigured)
    }

    func testGenerateAPIKeyFormat() {
        let key = AuthSettingsStore.generateAPIKey()
        XCTAssertTrue(key.hasPrefix("sk-sandwalk-"))
        let suffix = String(key.dropFirst("sk-sandwalk-".count))
        XCTAssertEqual(suffix.count, 24)
        XCTAssertTrue(suffix.allSatisfy { $0.isLetter || $0.isNumber })
    }

    func testSettingsFileURLPointsAtApplicationSupport() {
        let url = AuthSettingsStore.settingsFileURL()
        XCTAssertTrue(url.path.contains("Application Support/Sandwalk/settings.json"))
        XCTAssertEqual(url, ServerSettingsStore.settingsFileURL())
    }

    func testLoadReturnsEmptyWhenMissingFile() {
        XCTAssertEqual(AuthSettingsStore.load(), .empty)
    }

    func testLoadParsesAuthSection() throws {
        try SettingsTestSupport.writeSettingsJSON([
            "auth": [
                "api_key": "sk-sandwalk-abc",
                "auth_enabled": true,
                "secret_key": "top-secret",
            ],
        ])

        let loaded = AuthSettingsStore.load()
        XCTAssertEqual(loaded.apiKey, "sk-sandwalk-abc")
        XCTAssertTrue(loaded.authEnabled)
        XCTAssertEqual(loaded.secretKey, "top-secret")
        XCTAssertTrue(loaded.apiKeyConfigured)
    }

    func testSaveRoundTripPreservesProvidedSecret() throws {
        let settings = SandwalkAuthSettings(
            apiKey: "sk-sandwalk-roundtrip",
            authEnabled: true,
            secretKey: "provided-secret"
        )
        try AuthSettingsStore.save(settings)

        let loaded = AuthSettingsStore.load()
        XCTAssertEqual(loaded, settings)
    }

    func testSaveGeneratesSecretWhenEmpty() throws {
        let settings = SandwalkAuthSettings(apiKey: "sk-sandwalk-gen", authEnabled: false, secretKey: "")
        try AuthSettingsStore.save(settings)

        let loaded = AuthSettingsStore.load()
        XCTAssertEqual(loaded.apiKey, "sk-sandwalk-gen")
        XCTAssertFalse(loaded.authEnabled)
        XCTAssertFalse(loaded.secretKey.isEmpty)
        XCTAssertFalse(loaded.secretKey.contains("+"))
        XCTAssertFalse(loaded.secretKey.contains("/"))
        XCTAssertFalse(loaded.secretKey.contains("="))
    }

    func testSavePreservesExistingServerSection() throws {
        try SettingsTestSupport.writeSettingsJSON([
            "server": [
                "host": "127.0.0.1",
                "port": 8787,
                "dashboard_host": "127.0.0.1",
                "dashboard_port": 8969,
                "auto_start": true,
            ],
        ])

        try AuthSettingsStore.save(
            SandwalkAuthSettings(apiKey: "sk-sandwalk-merge", authEnabled: true, secretKey: "secret")
        )

        let network = ServerSettingsStore.load()
        XCTAssertEqual(network.port, 8787)
        XCTAssertEqual(network.dashboardPort, 8969)

        let auth = AuthSettingsStore.load()
        XCTAssertEqual(auth.apiKey, "sk-sandwalk-merge")
    }
}
