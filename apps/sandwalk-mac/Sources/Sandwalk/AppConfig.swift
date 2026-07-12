import Foundation

/// Shared config for the menubar supervisor (v1: simple defaults + env overrides).
struct AppConfig: Equatable, Sendable {
    var bindHost: String
    var port: Int
    var dashboardURL: URL
    var autoStartOnLaunch: Bool
    /// Directory of `fastfold-agent-cli` when using `uv run` / venv spawn.
    var agentCliRoot: URL?

    static let defaultHost = "127.0.0.1"
    static let defaultPort = 8787
    static let defaultDashboard = URL(string: "http://127.0.0.1:8969")!

    var healthURL: URL {
        URL(string: "http://\(connectableHost):\(port)/v1/health")!
    }

    var connectableHost: String {
        bindHost == "0.0.0.0" ? "127.0.0.1" : bindHost
    }

    static func load() -> AppConfig {
        let env = ProcessInfo.processInfo.environment
        let host = env["SANDWALK_HOST"] ?? defaultHost
        let port = Int(env["SANDWALK_PORT"] ?? "") ?? defaultPort
        let dashboard =
            env["SANDWALK_DASHBOARD_URL"].flatMap(URL.init(string:))
            ?? defaultDashboard
        let autoStart = (env["SANDWALK_AUTO_START"] ?? "1") != "0"
        let cliRoot = env["SANDWALK_AGENT_CLI"].map {
            URL(fileURLWithPath: ($0 as NSString).expandingTildeInPath, isDirectory: true)
        } ?? discoverAgentCliRoot()

        return AppConfig(
            bindHost: host,
            port: port,
            dashboardURL: dashboard,
            autoStartOnLaunch: autoStart,
            agentCliRoot: cliRoot
        )
    }

    /// Prefer monorepo `cli/`, then sibling checkouts / ~/Projects.
    private static func discoverAgentCliRoot() -> URL? {
        let fm = FileManager.default
        // apps/sandwalk-mac/Sources/Sandwalk/AppConfig.swift → repo root → cli/
        let fromSources = URL(fileURLWithPath: #filePath)
            .deletingLastPathComponent() // Sandwalk/
            .deletingLastPathComponent() // Sources/
            .deletingLastPathComponent() // sandwalk-mac/
            .deletingLastPathComponent() // apps/
        let candidates: [URL] = [
            fromSources.appendingPathComponent("cli", isDirectory: true),
            fromSources
                .deletingLastPathComponent() // parent of monorepo
                .appendingPathComponent("fastfold-agent-cli", isDirectory: true),
            URL(fileURLWithPath: NSHomeDirectory())
                .appendingPathComponent("Projects/fastfold-agent-cli", isDirectory: true),
            URL(fileURLWithPath: NSHomeDirectory())
                .appendingPathComponent("Projects/sandwalk/cli", isDirectory: true),
        ]
        for url in candidates {
            let marker = url.appendingPathComponent("pyproject.toml")
            if fm.fileExists(atPath: marker.path) {
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
}
