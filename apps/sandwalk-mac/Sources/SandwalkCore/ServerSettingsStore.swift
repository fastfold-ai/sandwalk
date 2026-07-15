import Foundation

/// Network slice of `settings.json` (alongside `auth`).
struct ServerNetworkSettings: Equatable, Sendable {
    var bindHost: String?
    var port: Int?
    var dashboardHost: String?
    var dashboardPort: Int?
    var autoStartOnLaunch: Bool?
    var healthCheckIntervalSeconds: Int?
    var dashboardServeMode: DashboardServeMode?
    /// When true, agent server auto-quarantines/recovers a corrupt SQLite DB.
    var dbAutoHeal: Bool?
    /// When true, ⌘Q closes windows only (menu bar stays up).
    var keepMenubarOnCmdQ: Bool?
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
        let modeRaw = (server["dashboard_serve_mode"] as? String)?.lowercased()
        let mode: DashboardServeMode? = {
            switch modeRaw {
            case "development", "dev": return .development
            case "production", "prod": return .production
            default: return nil
            }
        }()
        return ServerNetworkSettings(
            bindHost: server["host"] as? String,
            port: server["port"] as? Int,
            dashboardHost: server["dashboard_host"] as? String,
            dashboardPort: server["dashboard_port"] as? Int,
            autoStartOnLaunch: server["auto_start"] as? Bool,
            healthCheckIntervalSeconds: server["health_check_interval_seconds"] as? Int,
            dashboardServeMode: mode,
            dbAutoHeal: server["db_auto_heal"] as? Bool,
            keepMenubarOnCmdQ: server["keep_menubar_on_cmdq"] as? Bool
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
            "dashboard_serve_mode": (
                settings.dashboardServeMode ?? AppConfig.defaultDashboardServeMode
            ).rawValue,
            "db_auto_heal": settings.dbAutoHeal ?? AppConfig.defaultDbAutoHeal,
            "keep_menubar_on_cmdq": settings.keepMenubarOnCmdQ ?? AppConfig.defaultKeepMenubarOnCmdQ,
        ]
        let data = try JSONSerialization.data(withJSONObject: root, options: [.prettyPrinted, .sortedKeys])
        try data.write(to: url, options: .atomic)
    }
}
