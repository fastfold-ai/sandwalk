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

    let config: AppConfig
    let api: ServerProcess
    let web: WebUIProcess

    private(set) var overall: OverallState = .stopped

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
    }

    private func notify() {
        NotificationCenter.default.post(name: Self.stateDidChangeNotification, object: self)
    }
}
