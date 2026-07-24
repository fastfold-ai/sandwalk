import Foundation

/// Coordinates agent API + web dashboard processes for the menubar.
@MainActor
final class SandwalkSupervisor {
    enum OverallState: Equatable {
        case stopped
        case starting
        case running
        case partial(api: Bool, web: Bool)
        case stopping
        case failed(String)

        var label: String {
            switch self {
            case .stopped: return "Stopped"
            case .starting: return "Starting…"
            case .running: return "Running"
            case .partial(let api, let web):
                if api && !web { return "API up · Web starting/down" }
                if web && !api { return "Web up · API starting/down" }
                return "Partial"
            case .stopping: return "Stopping…"
            case .failed(let message): return "Failed — \(message)"
            }
        }

        var isLive: Bool {
            switch self {
            case .running, .starting, .partial, .stopping: return true
            default: return false
            }
        }
    }

    static let stateDidChangeNotification = Notification.Name("SandwalkSupervisorStateDidChange")
    static let configDidChangeNotification = Notification.Name("SandwalkSupervisorConfigDidChange")

    private(set) var config: AppConfig
    let api: ServerProcess
    let web: WebUIProcess

    private(set) var overall: OverallState = .stopped
    var partialRecoveryTask: Task<Void, Never>?
    var partialRecoveryAttempts = 0
    let maxPartialRecoveries = 5

    init(config: AppConfig) {
        self.config = config
        self.api = ServerProcess(config: config)
        self.web = WebUIProcess(config: config)

        NotificationCenter.default.addObserver(
            forName: ServerProcess.stateDidChangeNotification,
            object: api,
            queue: .main
        ) { [weak self] _ in
            Task { @MainActor in self?.recompute() }
        }
        NotificationCenter.default.addObserver(
            forName: WebUIProcess.stateDidChangeNotification,
            object: web,
            queue: .main
        ) { [weak self] _ in
            Task { @MainActor in self?.recompute() }
        }
    }

    func startAll() throws {
        overall = .starting
        partialRecoveryAttempts = 0
        notify()
        do {
            if config.usesBundledDashboard {
                // Stop any leftover Vite from a previous Development session.
                web.reapSync(timeout: 3)
                try prepareProductionDashboard()
            }
            _ = try api.start()
        } catch {
            overall = .failed(error.localizedDescription)
            notify()
            throw error
        }
        if config.usesBundledDashboard {
            // Dashboard is served by the API — no separate Vite process.
            recompute()
            return
        }
        do {
            try web.start()
        } catch {
            // API may already be up — report combined failure but keep API.
            overall = .failed("Web UI: \(error.localizedDescription)")
            notify()
            throw error
        }
        recompute()
    }

    private func prepareProductionDashboard() throws {
        guard let repoRoot = config.repoRoot else {
            throw DashboardBuilder.BuildError.missingRepo
        }
        try DashboardBuilder.ensureBuilt(
            repoRoot: repoRoot,
            force: false,
            logURL: config.webLogURL
        )
    }

    func stopAll() async {
        overall = .stopping
        notify()
        await web.stop()
        await api.stop()
        recompute()
    }

    /// Persist network / advanced settings and restart API + web when live.
    func applyNetworkConfig(_ next: AppConfig) async throws {
        var updated = next
        // Preserve discovery paths from the running supervisor.
        updated.agentCliRoot = config.agentCliRoot
        updated.repoRoot = config.repoRoot
        try updated.saveNetworkSettings()
        config = updated
        api.reconfigure(config: updated)
        web.reconfigure(config: updated)
        NotificationCenter.default.post(name: Self.configDidChangeNotification, object: self)

        let shouldRestart = overall.isLive
        if shouldRestart {
            await stopAll()
            try startAll()
        }
    }

    /// Rebuild the production dashboard assets (does not restart unless live + production).
    func rebuildProductionDashboard() async throws {
        guard let repoRoot = config.repoRoot else {
            throw DashboardBuilder.BuildError.missingRepo
        }
        try DashboardBuilder.ensureBuilt(
            repoRoot: repoRoot,
            force: true,
            logURL: config.webLogURL
        )
        if config.usesBundledDashboard, overall.isLive {
            await stopAll()
            try startAll()
        }
    }

    /// Persist launch / menu-bar preferences without restarting API/web.
    func applyGeneralPreferences(_ next: AppConfig) throws {
        var updated = config
        updated.autoStartOnLaunch = next.autoStartOnLaunch
        updated.keepMenubarOnCmdQ = next.keepMenubarOnCmdQ
        // Preserve discovery paths from the running supervisor.
        updated.agentCliRoot = config.agentCliRoot
        updated.repoRoot = config.repoRoot
        try updated.saveNetworkSettings()
        config = updated
        NotificationCenter.default.post(name: Self.configDidChangeNotification, object: self)
    }

    /// Persist health-check interval without restarting API/web.
    func applyHealthCheckInterval(_ seconds: Int) throws {
        var updated = config
        updated.healthCheckIntervalSeconds = AppConfig.clampHealthCheckInterval(seconds)
        try updated.saveNetworkSettings()
        config = updated
        api.reconfigure(config: updated)
        web.reconfigure(config: updated)
        api.refreshHealthLoop()
        web.refreshHealthLoop()
        NotificationCenter.default.post(name: Self.configDidChangeNotification, object: self)
    }

    func restartAll() async throws {
        await stopAll()
        // Let TIME_WAIT / child reaping / SQLite flock drain so the next serve
        // can open agent-server.db (menubar Restart used to race this).
        try await Task.sleep(for: .milliseconds(2_000))
        try startAll()
        // Vite may adopt quickly while the API cold-starts — retry API once if
        // we land in "web up · API down".
        for _ in 0..<20 {
            try await Task.sleep(for: .milliseconds(250))
            recompute()
            if case .running = overall { return }
            if case .partial(let api, let web) = overall, api, web { return }
            if case .partial(let apiUp, let webUp) = overall, !apiUp, webUp {
                do {
                    _ = try self.api.start()
                } catch {
                    // Keep polling; start may race with a dying orphan.
                }
            }
        }
        recompute()
        if case .partial(let apiUp, _) = overall, !apiUp {
            throw ServerProcess.StartError.spawnFailed(
                "API did not become healthy on \(config.healthURL.absoluteString). Check Logs → server.log."
            )
        }
    }

    func reapSync() {
        web.reapSync(timeout: 5)
        api.reapSync(timeout: 5)
        recompute()
    }

    func recompute() {
        let apiLive: Bool = {
            switch api.state {
            case .running: return true
            default: return false
            }
        }()
        let webLive: Bool = {
            if config.usesBundledDashboard {
                // Production UI is hosted by the API process.
                return apiLive
            }
            switch web.state {
            case .running: return true
            default: return false
            }
        }()
        let apiStarting = {
            if case .starting = api.state { return true }
            return false
        }()
        let webStarting = {
            if config.usesBundledDashboard { return false }
            if case .starting = web.state { return true }
            return false
        }()
        let apiStopping = {
            if case .stopping = api.state { return true }
            return false
        }()
        let webStopping = {
            if config.usesBundledDashboard { return false }
            if case .stopping = web.state { return true }
            return false
        }()

        if apiStopping || webStopping {
            overall = .stopping
        } else if apiStarting || webStarting {
            overall = .starting
        } else if apiLive && webLive {
            overall = .running
        } else if apiLive || webLive {
            overall = .partial(api: apiLive, web: webLive)
        } else if case .failed(let message) = api.state {
            overall = .failed(message)
        } else if !config.usesBundledDashboard, case .failed(let message) = web.state {
            overall = .failed(message)
        } else {
            overall = .stopped
        }
        notify()
        recoverPartialAPIIfNeeded()
    }

    func notify() {
        NotificationCenter.default.post(name: Self.stateDidChangeNotification, object: self)
    }
}
