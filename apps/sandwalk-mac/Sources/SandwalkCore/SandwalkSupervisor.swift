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
    private var partialRecoveryTask: Task<Void, Never>?
    private var partialRecoveryAttempts = 0
    private let maxPartialRecoveries = 5

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
            _ = try api.start()
        } catch {
            overall = .failed(error.localizedDescription)
            notify()
            throw error
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

    func stopAll() async {
        overall = .stopping
        notify()
        await web.stop()
        await api.stop()
        recompute()
    }

    /// Persist network settings and restart API + web with the new binds.
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
        // Let TIME_WAIT / child reaping finish so the next bind can succeed.
        try await Task.sleep(for: .milliseconds(700))
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

    private func recompute() {
        let apiLive: Bool = {
            switch api.state {
            case .running: return true
            default: return false
            }
        }()
        let webLive: Bool = {
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
            if case .starting = web.state { return true }
            return false
        }()
        let apiStopping = {
            if case .stopping = api.state { return true }
            return false
        }()
        let webStopping = {
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
        } else if case .failed(let message) = web.state {
            overall = .failed(message)
        } else {
            overall = .stopped
        }
        notify()
        recoverPartialAPIIfNeeded()
    }

    /// Web-up / API-down is the common "tools killed sandwalk serve" failure mode.
    /// Kick API start (adopt-or-respawn) so the menubar doesn't stay orange forever.
    private func recoverPartialAPIIfNeeded() {
        guard case .partial(let apiUp, let webUp) = overall, !apiUp, webUp else {
            partialRecoveryTask?.cancel()
            partialRecoveryTask = nil
            if case .running = overall {
                partialRecoveryAttempts = 0
            }
            return
        }
        guard partialRecoveryTask == nil else { return }
        guard partialRecoveryAttempts < maxPartialRecoveries else {
            NSLog(
                "Sandwalk: giving up partial API recovery after %d attempts — check server.log",
                maxPartialRecoveries
            )
            return
        }
        partialRecoveryTask = Task { @MainActor [weak self] in
            guard let self else { return }
            defer { self.partialRecoveryTask = nil }
            let attempt = self.partialRecoveryAttempts + 1
            let delayMs = 700 * attempt
            try? await Task.sleep(for: .milliseconds(delayMs))
            guard !Task.isCancelled else { return }
            guard case .partial(let stillApi, let stillWeb) = self.overall, !stillApi, stillWeb else {
                return
            }
            self.partialRecoveryAttempts = attempt
            do {
                _ = try self.api.start()
                NSLog("Sandwalk: recovered API from partial state (attempt %d)", attempt)
            } catch {
                NSLog(
                    "Sandwalk: partial API recovery failed (attempt %d) — %@",
                    attempt,
                    error.localizedDescription
                )
            }
            self.recompute()
        }
    }

    private func notify() {
        NotificationCenter.default.post(name: Self.stateDidChangeNotification, object: self)
    }
}
