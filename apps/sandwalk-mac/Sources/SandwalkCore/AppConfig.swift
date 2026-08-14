import Foundation

/// How the menubar serves the web dashboard.
enum DashboardServeMode: String, Equatable, Sendable, CaseIterable {
    /// Built Vite assets served by FastAPI on the API port (default).
    case production
    /// Separate Vite dev server with HMR on the dashboard port.
    case development

    var title: String {
        switch self {
        case .production: return "Production"
        case .development: return "Development"
        }
    }

    var detail: String {
        switch self {
        case .production:
            return "Serve the built dashboard from the API (one process, no Vite)."
        case .development:
            return "Run the Vite dev server with hot reload on the dashboard port."
        }
    }
}

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
    /// Production (API-hosted UI) vs Development (Vite).
    var dashboardServeMode: DashboardServeMode
    /// Quarantine + recover corrupt `agent-server.db` on serve start (default on).
    var dbAutoHeal: Bool
    /// When true, ⌘Q closes windows only; menu bar + agent keep running.
    var keepMenubarOnCmdQ: Bool
    /// Monorepo `cli/` directory (Python package).
    var agentCliRoot: URL?
    /// Monorepo root (contains `apps/`, `cli/`, `package.json`).
    var repoRoot: URL?

    static let defaultHost = "127.0.0.1"
    static let defaultPort = 8787
    static let defaultDashboardHost = "127.0.0.1"
    static let defaultDashboardPort = 8969
    static let defaultHealthCheckIntervalSeconds = 60
    static let defaultDashboardServeMode: DashboardServeMode = .production
    static let defaultDbAutoHeal = true
    static let defaultKeepMenubarOnCmdQ = true
    static let minHealthCheckIntervalSeconds = 5
    static let maxHealthCheckIntervalSeconds = 300

    static func clampHealthCheckInterval(_ seconds: Int) -> Int {
        min(
            max(seconds, minHealthCheckIntervalSeconds),
            maxHealthCheckIntervalSeconds
        )
    }

    var usesBundledDashboard: Bool {
        dashboardServeMode == .production
    }

    /// Packaged helper ships Vite output under Resources/ui-dist.
    static func bundledUiDistURL(bundle: Bundle = .main) -> URL? {
        guard let resources = bundle.resourceURL else { return nil }
        let bundled = resources.appendingPathComponent("ui-dist", isDirectory: true)
        let index = bundled.appendingPathComponent("index.html")
        guard FileManager.default.fileExists(atPath: index.path) else { return nil }
        return bundled
    }

    var uiDistURL: URL? {
        if let bundled = Self.bundledUiDistURL() {
            return bundled
        }
        guard let repoRoot else { return nil }
        return DashboardBuilder.distURL(repoRoot: repoRoot)
    }

    var dashboardURL: URL {
        if usesBundledDashboard {
            return URL(string: "http://\(connectableHost):\(port)/")!
        }
        return URL(string: "http://\(dashboardConnectableHost):\(dashboardPort)/")!
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
        dashboardURL.appendingPathComponent("agents/new")
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
        var serveMode: DashboardServeMode = {
            if let raw = env["SANDWALK_DASHBOARD_MODE"]?.lowercased() {
                if raw == "development" || raw == "dev" { return .development }
                if raw == "production" || raw == "prod" { return .production }
            }
            return saved.dashboardServeMode ?? defaultDashboardServeMode
        }()
        let dbAutoHeal: Bool = {
            if let raw = env["SANDWALK_DB_AUTO_HEAL"]?.lowercased() {
                return !["0", "false", "no", "off"].contains(raw)
            }
            return saved.dbAutoHeal ?? defaultDbAutoHeal
        }()
        let keepMenubarOnCmdQ: Bool = {
            if let raw = env["SANDWALK_KEEP_MENUBAR_ON_CMDQ"]?.lowercased() {
                return !["0", "false", "no", "off"].contains(raw)
            }
            return saved.keepMenubarOnCmdQ ?? defaultKeepMenubarOnCmdQ
        }()
        let repoRoot = env["SANDWALK_REPO_ROOT"].map {
            URL(fileURLWithPath: ($0 as NSString).expandingTildeInPath, isDirectory: true)
        } ?? discoverRepoRoot()
        let cliRoot = env["SANDWALK_AGENT_CLI"].map {
            URL(fileURLWithPath: ($0 as NSString).expandingTildeInPath, isDirectory: true)
        } ?? repoRoot?.appendingPathComponent("cli", isDirectory: true)
            ?? discoverAgentCliRoot()

        // Self-contained DMG: agent-runtime + ui-dist mean Production. Ignore a
        // leftover Development setting from a prior checkout (no Vite on :8969).
        // Explicit SANDWALK_DASHBOARD_MODE still wins (handled above).
        if env["SANDWALK_DASHBOARD_MODE"] == nil,
           ServeRuntime.bundledPythonURL() != nil,
           Self.bundledUiDistURL() != nil
        {
            serveMode = .production
        }

        return AppConfig(
            bindHost: host,
            port: port,
            dashboardHost: dashHost,
            dashboardPort: dashPort,
            autoStartOnLaunch: autoStart,
            healthCheckIntervalSeconds: healthInterval,
            dashboardServeMode: serveMode,
            dbAutoHeal: dbAutoHeal,
            keepMenubarOnCmdQ: keepMenubarOnCmdQ,
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
                healthCheckIntervalSeconds: healthCheckIntervalSeconds,
                dashboardServeMode: dashboardServeMode,
                dbAutoHeal: dbAutoHeal,
                keepMenubarOnCmdQ: keepMenubarOnCmdQ
            )
        )
    }

    private static func discoverRepoRoot() -> URL? {
        let fm = FileManager.default
        let fromSources = URL(fileURLWithPath: #filePath)
            .deletingLastPathComponent() // SandwalkCore/
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
