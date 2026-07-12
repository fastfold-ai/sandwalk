import Foundation

/// Shared config for the menubar supervisor (API + web UI).
struct AppConfig: Equatable, Sendable {
    var bindHost: String
    var port: Int
    var dashboardHost: String
    var dashboardPort: Int
    var autoStartOnLaunch: Bool
    /// Monorepo `cli/` directory (Python package).
    var agentCliRoot: URL?
    /// Monorepo root (contains `apps/`, `cli/`, `package.json`).
    var repoRoot: URL?

    static let defaultHost = "127.0.0.1"
    static let defaultPort = 8787
    static let defaultDashboardHost = "127.0.0.1"
    static let defaultDashboardPort = 8969

    var dashboardURL: URL {
        URL(string: "http://\(dashboardHost):\(dashboardPort)/")!
    }

    /// Settings / overview surface (`/dashboard`).
    var dashboardHomeURL: URL {
        dashboardURL.appendingPathComponent("dashboard")
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

    var connectableHost: String {
        bindHost == "0.0.0.0" ? "127.0.0.1" : bindHost
    }

    static func load() -> AppConfig {
        let env = ProcessInfo.processInfo.environment
        let host = env["SANDWALK_HOST"] ?? defaultHost
        let port = Int(env["SANDWALK_PORT"] ?? "") ?? defaultPort
        var dashHost = env["SANDWALK_DASHBOARD_HOST"] ?? defaultDashboardHost
        var dashPort = Int(env["SANDWALK_DASHBOARD_PORT"] ?? "") ?? defaultDashboardPort
        if let override = env["SANDWALK_DASHBOARD_URL"].flatMap(URL.init(string:)) {
            dashHost = override.host ?? dashHost
            dashPort = override.port ?? dashPort
        }
        let autoStart = (env["SANDWALK_AUTO_START"] ?? "1") != "0"
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
            agentCliRoot: cliRoot,
            repoRoot: repoRoot
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
