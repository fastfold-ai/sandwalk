import Darwin
import Foundation
import XCTest
@testable import SandwalkCore

final class AppConfigTests: XCTestCase {
    private var savedSettings: Data?

    private let envKeys = [
        "SANDWALK_HOST",
        "SANDWALK_PORT",
        "SANDWALK_DASHBOARD_HOST",
        "SANDWALK_DASHBOARD_PORT",
        "SANDWALK_DASHBOARD_URL",
        "SANDWALK_DASHBOARD_MODE",
        "SANDWALK_AUTO_START",
        "SANDWALK_DB_AUTO_HEAL",
        "SANDWALK_REPO_ROOT",
        "SANDWALK_AGENT_CLI",
    ]

    override func setUp() {
        super.setUp()
        savedSettings = SettingsTestSupport.backupSettings()
        SettingsTestSupport.removeSettings()
        EnvTestSupport.unset(envKeys)
    }

    override func tearDown() {
        EnvTestSupport.unset(envKeys)
        SettingsTestSupport.restoreSettings(from: savedSettings)
        super.tearDown()
    }
    private func makeConfig(
        bindHost: String = "127.0.0.1",
        port: Int = 8787,
        dashboardHost: String = "127.0.0.1",
        dashboardPort: Int = 8969,
        healthCheckIntervalSeconds: Int = AppConfig.defaultHealthCheckIntervalSeconds,
        dashboardServeMode: DashboardServeMode = .development
    ) -> AppConfig {
        AppConfig(
            bindHost: bindHost,
            port: port,
            dashboardHost: dashboardHost,
            dashboardPort: dashboardPort,
            autoStartOnLaunch: true,
            healthCheckIntervalSeconds: healthCheckIntervalSeconds,
            dashboardServeMode: dashboardServeMode,
            dbAutoHeal: true,
            keepMenubarOnCmdQ: true,
            agentCliRoot: nil,
            repoRoot: nil
        )
    }

    func testConnectableHostMapsWildcardToLoopback() {
        let local = makeConfig(bindHost: "127.0.0.1")
        XCTAssertEqual(local.connectableHost, "127.0.0.1")
        XCTAssertFalse(local.apiExposesRemote)

        let remote = makeConfig(bindHost: "0.0.0.0", dashboardHost: "0.0.0.0")
        XCTAssertEqual(remote.connectableHost, "127.0.0.1")
        XCTAssertEqual(remote.dashboardConnectableHost, "127.0.0.1")
        XCTAssertTrue(remote.apiExposesRemote)
        XCTAssertTrue(remote.dashboardExposesRemote)
    }

    func testDashboardAndAPIURLs() {
        let config = makeConfig(port: 9001, dashboardPort: 9002)
        XCTAssertEqual(config.apiBaseURL.absoluteString, "http://127.0.0.1:9001")
        XCTAssertEqual(config.healthURL.absoluteString, "http://127.0.0.1:9001/v1/health")
        XCTAssertEqual(config.sessionsAPIURL.absoluteString, "http://127.0.0.1:9001/v1/sessions")
        XCTAssertEqual(config.dashboardURL.absoluteString, "http://127.0.0.1:9002/")
        XCTAssertEqual(config.dashboardHomeURL.absoluteString, "http://127.0.0.1:9002/dashboard")
        XCTAssertEqual(
            config.dashboardPageURL("skills").absoluteString,
            "http://127.0.0.1:9002/dashboard/skills"
        )
        XCTAssertEqual(
            config.dashboardPageURL("/integrations/").absoluteString,
            "http://127.0.0.1:9002/dashboard/integrations"
        )
        XCTAssertEqual(config.dashboardPageURL("").absoluteString, config.dashboardHomeURL.absoluteString)
        XCTAssertEqual(
            config.agentSessionURL("abc-123").absoluteString,
            "http://127.0.0.1:9002/agents/abc-123"
        )
        XCTAssertEqual(config.agentsHomeURL.absoluteString, "http://127.0.0.1:9002/agents/home")
    }

    func testProductionDashboardUsesAPIPort() {
        let config = makeConfig(port: 9001, dashboardPort: 9002, dashboardServeMode: .production)
        XCTAssertTrue(config.usesBundledDashboard)
        XCTAssertEqual(config.dashboardURL.absoluteString, "http://127.0.0.1:9001/")
        XCTAssertEqual(config.dashboardHomeURL.absoluteString, "http://127.0.0.1:9001/dashboard")
        XCTAssertEqual(config.webHealthURL.absoluteString, "http://127.0.0.1:9001/")
    }

    func testSupportLogPathsLiveUnderApplicationSupport() {
        let config = makeConfig()
        XCTAssertTrue(config.supportDirectory.path.contains("Application Support/Sandwalk"))
        XCTAssertTrue(config.serverLogURL.path.hasSuffix("logs/server.log"))
        XCTAssertTrue(config.webLogURL.path.hasSuffix("logs/web.log"))
    }

    func testDefaults() {
        XCTAssertEqual(AppConfig.defaultHost, "127.0.0.1")
        XCTAssertEqual(AppConfig.defaultPort, 8787)
        XCTAssertEqual(AppConfig.defaultDashboardHost, "127.0.0.1")
        XCTAssertEqual(AppConfig.defaultDashboardPort, 8969)
        XCTAssertEqual(AppConfig.defaultHealthCheckIntervalSeconds, 60)
        XCTAssertEqual(AppConfig.defaultDashboardServeMode, .production)
    }

    func testClampHealthCheckInterval() {
        XCTAssertEqual(AppConfig.clampHealthCheckInterval(1), 5)
        XCTAssertEqual(AppConfig.clampHealthCheckInterval(60), 60)
        XCTAssertEqual(AppConfig.clampHealthCheckInterval(999), 300)
    }

    func testWebHealthURLMatchesDashboardURL() {
        let config = makeConfig(dashboardPort: 8969)
        XCTAssertEqual(config.webHealthURL, config.dashboardURL)
    }

    func testLoadUsesDefaultsWhenNoSettingsOrEnv() {
        let config = AppConfig.load()
        XCTAssertEqual(config.bindHost, AppConfig.defaultHost)
        XCTAssertEqual(config.port, AppConfig.defaultPort)
        XCTAssertEqual(config.dashboardHost, AppConfig.defaultDashboardHost)
        XCTAssertEqual(config.dashboardPort, AppConfig.defaultDashboardPort)
        XCTAssertTrue(config.autoStartOnLaunch)
        XCTAssertEqual(config.dashboardServeMode, .production)
        XCTAssertTrue(config.usesBundledDashboard)
    }

    func testLoadReadsNetworkSettingsFromFile() throws {
        try SettingsTestSupport.writeSettingsJSON([
            "server": [
                "host": "10.0.0.2",
                "port": 7777,
                "dashboard_host": "10.0.0.3",
                "dashboard_port": 8888,
                "auto_start": false,
                "dashboard_serve_mode": "development",
            ],
        ])

        let config = AppConfig.load()
        XCTAssertEqual(config.bindHost, "10.0.0.2")
        XCTAssertEqual(config.port, 7777)
        XCTAssertEqual(config.dashboardHost, "10.0.0.3")
        XCTAssertEqual(config.dashboardPort, 8888)
        XCTAssertFalse(config.autoStartOnLaunch)
        XCTAssertEqual(config.dashboardServeMode, .development)
    }

    func testLoadEnvironmentOverridesSettingsFile() throws {
        try SettingsTestSupport.writeSettingsJSON([
            "server": ["host": "10.0.0.2", "port": 7777, "dashboard_serve_mode": "production"],
        ])
        setenv("SANDWALK_HOST", "0.0.0.0", 1)
        setenv("SANDWALK_PORT", "9001", 1)
        setenv("SANDWALK_DASHBOARD_HOST", "0.0.0.0", 1)
        setenv("SANDWALK_DASHBOARD_PORT", "9002", 1)
        setenv("SANDWALK_DASHBOARD_MODE", "development", 1)
        setenv("SANDWALK_AUTO_START", "0", 1)

        let config = AppConfig.load()
        XCTAssertEqual(config.bindHost, "0.0.0.0")
        XCTAssertEqual(config.port, 9001)
        XCTAssertEqual(config.dashboardHost, "0.0.0.0")
        XCTAssertEqual(config.dashboardPort, 9002)
        XCTAssertFalse(config.autoStartOnLaunch)
        XCTAssertEqual(config.dashboardServeMode, .development)
    }

    func testLoadDashboardURLFromEnvironment() {
        setenv("SANDWALK_DASHBOARD_URL", "http://192.168.1.10:7654/", 1)

        let config = AppConfig.load()
        XCTAssertEqual(config.dashboardHost, "192.168.1.10")
        XCTAssertEqual(config.dashboardPort, 7654)
    }

    func testLoadRepoAndAgentCliFromEnvironment() throws {
        let tmp = FileManager.default.temporaryDirectory
            .appendingPathComponent("sandwalk-appconfig-\(UUID().uuidString)", isDirectory: true)
        let cli = tmp.appendingPathComponent("cli", isDirectory: true)
        try FileManager.default.createDirectory(at: cli, withIntermediateDirectories: true)
        try Data("{}".utf8).write(to: tmp.appendingPathComponent("package.json"))
        try Data("[project]\n".utf8).write(to: cli.appendingPathComponent("pyproject.toml"))
        defer { try? FileManager.default.removeItem(at: tmp) }

        setenv("SANDWALK_REPO_ROOT", tmp.path, 1)
        setenv("SANDWALK_AGENT_CLI", cli.path, 1)

        let config = AppConfig.load()
        XCTAssertEqual(config.repoRoot?.standardizedFileURL, tmp.standardizedFileURL)
        XCTAssertEqual(config.agentCliRoot?.standardizedFileURL, cli.standardizedFileURL)
    }

    func testSaveNetworkSettingsPersistsAndPreservesAuth() throws {
        try SettingsTestSupport.writeSettingsJSON([
            "auth": [
                "api_key": "sk-sandwalk-test",
                "auth_enabled": true,
                "secret_key": "secret",
            ],
        ])

        var config = makeConfig(bindHost: "0.0.0.0", port: 9100, dashboardHost: "127.0.0.1", dashboardPort: 9200)
        config.autoStartOnLaunch = false
        config.dashboardServeMode = .production
        try config.saveNetworkSettings()

        let network = ServerSettingsStore.load()
        XCTAssertEqual(network.bindHost, "0.0.0.0")
        XCTAssertEqual(network.port, 9100)
        XCTAssertEqual(network.dashboardHost, "127.0.0.1")
        XCTAssertEqual(network.dashboardPort, 9200)
        XCTAssertEqual(network.autoStartOnLaunch, false)
        XCTAssertEqual(network.dashboardServeMode, .production)
        XCTAssertEqual(
            network.healthCheckIntervalSeconds,
            AppConfig.defaultHealthCheckIntervalSeconds
        )

        let auth = AuthSettingsStore.load()
        XCTAssertEqual(auth.apiKey, "sk-sandwalk-test")
        XCTAssertTrue(auth.authEnabled)
        XCTAssertEqual(auth.secretKey, "secret")
    }

    func testServerSettingsStoreSaveUsesDefaultsForMissingFields() throws {
        try ServerSettingsStore.save(ServerNetworkSettings())

        let loaded = ServerSettingsStore.load()
        XCTAssertEqual(loaded.bindHost, AppConfig.defaultHost)
        XCTAssertEqual(loaded.port, AppConfig.defaultPort)
        XCTAssertEqual(loaded.dashboardHost, AppConfig.defaultDashboardHost)
        XCTAssertEqual(loaded.dashboardPort, AppConfig.defaultDashboardPort)
        XCTAssertEqual(loaded.autoStartOnLaunch, true)
        XCTAssertEqual(
            loaded.healthCheckIntervalSeconds,
            AppConfig.defaultHealthCheckIntervalSeconds
        )
        XCTAssertEqual(loaded.dashboardServeMode, .production)
    }

    func testServerSettingsStoreLoadReturnsEmptyWhenMissingFile() {
        let loaded = ServerSettingsStore.load()
        XCTAssertEqual(loaded, ServerNetworkSettings())
    }
}
