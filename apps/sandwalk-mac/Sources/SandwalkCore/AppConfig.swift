import Foundation

/// Shared config for the menubar supervisor (API + web UI).
struct AppConfig: Equatable, Sendable {
    var bindHost: String
    var port: Int
    var dashboardHost: String
    var dashboardPort: Int
    var autoStartOnLaunch: Bool
    /// How often the menubar probes `/v1/health` while the API is running.
    /// Cold-start still uses a short interval so Start stays responsive.
    var healthCheckIntervalSeconds: Int
    /// Monorepo `cli/` directory (Python package).
    var agentCliRoot: URL?
    /// Monorepo root (contains `apps/`, `cli/`, `package.json`).
    var repoRoot: URL?

    static let defaultHost = "127.0.0.1"
    static let defaultPort = 8787
    static let defaultDashboardHost = "127.0.0.1"
    static let defaultDashboardPort = 8969
    static let defaultHealthCheckIntervalSeconds = 60
    static let minHealthCheckIntervalSeconds = 5
    static let maxHealthCheckIntervalSeconds = 300

    static func clampHealthCheckInterval(_ seconds: Int) -> Int {
        min(
            max(seconds, minHealthCheckIntervalSeconds),
            maxHealthCheckIntervalSeconds
        )
    }

    var dashboardURL: URL {
        URL(string: "http://\(dashboardConnectableHost):\(dashboardPort)/")!
    }

    /// Settings / overview surface (`/dashboard`).
    var dashboardHomeURL: URL {
        dashboardURL.appendingPathComponent("dashboard")
    }

    /// Deep link into a dashboard page (e.g. `skills`, `integrations`, `mcp`).
    func dashboardPageURL(_ path: String) -> URL {
        let trimmed = path.trimmingCharacters(in: CharacterSet(charactersIn: "/"))
        guard !trimmed.isEmpty else { return dashboardHomeURL }
        return dashboardHomeURL.appendingPathComponent(trimmed)
    }

    var apiBaseURL: URL {
        URL(string: "http://\(connectableHost):\(port)")!
    }

    var sessionsAPIURL: URL {
        apiBaseURL.appendingPathComponent("v1/sessions")
    }

    func agentSessionURL(_ sessionId: String) -> URL {
        dashboardURL.appendingPathComponent("agents/\(sessionId)")
    }

    var agentsHomeURL: URL {
        dashboardURL.appendingPathComponent("agents/home")
    }

    var healthURL: URL {
        URL(string: "http://\(connectableHost):\(port)/v1/health")!
    }

    var webHealthURL: URL {
        dashboardURL
    }

    /// Host used in browser / HTTP client URLs when bound to all interfaces.
    var connectableHost: String {
        bindHost == "0.0.0.0" ? "127.0.0.1" : bindHost
    }

    var dashboardConnectableHost: String {
        dashboardHost == "0.0.0.0" ? "127.0.0.1" : dashboardHost
    }

    var apiExposesRemote: Bool { bindHost == "0.0.0.0" }
    var dashboardExposesRemote: Bool { dashboardHost == "0.0.0.0" }

    /// Load: env overrides → settings.json → defaults.
    static func load() -> AppConfig {
        let env = ProcessInfo.processInfo.environment
        let saved = ServerSettingsStore.load()

        let host =
            env["SANDWALK_HOST"]
            ?? saved.bindHost
            ?? defaultHost
        let port =
            Int(env["SANDWALK_PORT"] ?? "")
            ?? saved.port
            ?? defaultPort
        var dashHost =
            env["SANDWALK_DASHBOARD_HOST"]
            ?? saved.dashboardHost
            ?? defaultDashboardHost
        var dashPort =
            Int(env["SANDWALK_DASHBOARD_PORT"] ?? "")
            ?? saved.dashboardPort
            ?? defaultDashboardPort
        if let override = env["SANDWALK_DASHBOARD_URL"].flatMap(URL.init(string:)) {
            dashHost = override.host ?? dashHost
            dashPort = override.port ?? dashPort
        }
        let autoStart: Bool = {
            if let raw = env["SANDWALK_AUTO_START"] {
                return raw != "0"
            }
            return saved.autoStartOnLaunch ?? true
        }()
        let healthInterval: Int = {
            if let raw = env["SANDWALK_HEALTH_INTERVAL"], let value = Int(raw) {
                return clampHealthCheckInterval(value)
            }
            return clampHealthCheckInterval(
                saved.healthCheckIntervalSeconds ?? defaultHealthCheckIntervalSeconds
            )
        }()
        let repoRoot = env["SANDWALK_REPO_ROOT"].map {
            URL(fileURLWithPath: ($0 as NSString).expandingTildeInPath, isDirectory: true)
        } ?? discoverRepoRoot()
        let cliRoot = env["SANDWALK_AGENT_CLI"].map {
            URL(fileURLWithPath: ($0 as NSString).expandingTildeInPath, isDirectory: true)
        } ?? repoRoot?.appendingPathComponent("cli", isDirectory: true)
            ?? discoverAgentCliRoot()

        return AppConfig(
            bindHost: host,
            port: port,
            dashboardHost: dashHost,
            dashboardPort: dashPort,
            autoStartOnLaunch: autoStart,
            healthCheckIntervalSeconds: healthInterval,
            agentCliRoot: cliRoot,
            repoRoot: repoRoot
        )
    }

    /// Persist network bind settings (does not touch auth keys).
    func saveNetworkSettings() throws {
        try ServerSettingsStore.save(
            ServerNetworkSettings(
                bindHost: bindHost,
                port: port,
                dashboardHost: dashboardHost,
                dashboardPort: dashboardPort,
                autoStartOnLaunch: autoStartOnLaunch,
                healthCheckIntervalSeconds: healthCheckIntervalSeconds
            )
        )
    }

    private static func discoverRepoRoot() -> URL? {
        let fm = FileManager.default
        let fromSources = URL(fileURLWithPath: #filePath)
            .deletingLastPathComponent() // Sandwalk/
            .deletingLastPathComponent() // Sources/
            .deletingLastPathComponent() // sandwalk-mac/
            .deletingLastPathComponent() // apps/
        let candidates: [URL] = [
            fromSources,
            URL(fileURLWithPath: NSHomeDirectory())
                .appendingPathComponent("Projects/sandwalk", isDirectory: true),
        ]
        for url in candidates {
            let marker = url.appendingPathComponent("package.json")
            let cli = url.appendingPathComponent("cli/pyproject.toml")
            if fm.fileExists(atPath: marker.path), fm.fileExists(atPath: cli.path) {
                return url
            }
        }
        return nil
    }

    private static func discoverAgentCliRoot() -> URL? {
        let fm = FileManager.default
        if let root = discoverRepoRoot() {
            let cli = root.appendingPathComponent("cli", isDirectory: true)
            if fm.fileExists(atPath: cli.appendingPathComponent("pyproject.toml").path) {
                return cli
            }
        }
        let candidates: [URL] = [
            URL(fileURLWithPath: NSHomeDirectory())
                .appendingPathComponent("Projects/sandwalk/cli", isDirectory: true),
            URL(fileURLWithPath: NSHomeDirectory())
                .appendingPathComponent("Projects/fastfold-agent-cli", isDirectory: true),
        ]
        for url in candidates {
            if fm.fileExists(atPath: url.appendingPathComponent("pyproject.toml").path) {
                return url
            }
        }
        return nil
    }

    var supportDirectory: URL {
        let base = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask).first
            ?? URL(fileURLWithPath: NSHomeDirectory()).appendingPathComponent("Library/Application Support")
        return base.appendingPathComponent("Sandwalk", isDirectory: true)
    }

    var serverLogURL: URL {
        supportDirectory.appendingPathComponent("logs/server.log")
    }

    var webLogURL: URL {
        supportDirectory.appendingPathComponent("logs/web.log")
    }
}

/// Network slice of `settings.json` (alongside `auth`).
struct ServerNetworkSettings: Equatable, Sendable {
    var bindHost: String?
    var port: Int?
    var dashboardHost: String?
    var dashboardPort: Int?
    var autoStartOnLaunch: Bool?
    var healthCheckIntervalSeconds: Int?
}

enum ServerSettingsStore {
    static func settingsFileURL() -> URL {
        AuthSettingsStore.settingsFileURL()
    }

    static func load() -> ServerNetworkSettings {
        let url = settingsFileURL()
        guard
            let data = try? Data(contentsOf: url),
            let root = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
            let server = root["server"] as? [String: Any]
        else {
            return ServerNetworkSettings()
        }
        return ServerNetworkSettings(
            bindHost: server["host"] as? String,
            port: server["port"] as? Int,
            dashboardHost: server["dashboard_host"] as? String,
            dashboardPort: server["dashboard_port"] as? Int,
            autoStartOnLaunch: server["auto_start"] as? Bool,
            healthCheckIntervalSeconds: server["health_check_interval_seconds"] as? Int
        )
    }

    static func save(_ settings: ServerNetworkSettings) throws {
        let url = settingsFileURL()
        try FileManager.default.createDirectory(
            at: url.deletingLastPathComponent(),
            withIntermediateDirectories: true
        )
        var root: [String: Any] = [:]
        if let data = try? Data(contentsOf: url),
           let existing = try? JSONSerialization.jsonObject(with: data) as? [String: Any]
        {
            root = existing
        }
        root["server"] = [
            "host": settings.bindHost ?? AppConfig.defaultHost,
            "port": settings.port ?? AppConfig.defaultPort,
            "dashboard_host": settings.dashboardHost ?? AppConfig.defaultDashboardHost,
            "dashboard_port": settings.dashboardPort ?? AppConfig.defaultDashboardPort,
            "auto_start": settings.autoStartOnLaunch ?? true,
            "health_check_interval_seconds": AppConfig.clampHealthCheckInterval(
                settings.healthCheckIntervalSeconds ?? AppConfig.defaultHealthCheckIntervalSeconds
            ),
        ]
        let data = try JSONSerialization.data(withJSONObject: root, options: [.prettyPrinted, .sortedKeys])
        try data.write(to: url, options: .atomic)
    }
}
