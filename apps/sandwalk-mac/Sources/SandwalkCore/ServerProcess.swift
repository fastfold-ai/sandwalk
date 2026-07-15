import Darwin
import Foundation

/// Owns the `sandwalk serve` child process.
final class ServerProcess: @unchecked Sendable {
    enum State: Equatable, Sendable {
        case stopped
        case starting
        case running(pid: Int32)
        case stopping
        case failed(message: String)

        var label: String {
            switch self {
            case .stopped: return "Stopped"
            case .starting: return "Starting…"
            case .running: return "Running"
            case .stopping: return "Stopping…"
            case .failed(let message): return "Failed — \(message)"
            }
        }

        var isLive: Bool {
            switch self {
            case .running, .starting, .stopping: return true
            default: return false
            }
        }
    }

    enum StartResult: Sendable {
        case started
        case alreadyRunning
    }

    static let stateDidChangeNotification = Notification.Name("SandwalkServerStateDidChange")

    private(set) var config: AppConfig
    private(set) var state: State = .stopped

    var process: Process?
    /// Listener we did not spawn (orphan / external) but are supervising.
    var adoptedPid: Int32?
    var logHandle: FileHandle?
    var healthTask: Task<Void, Never>?
    var recoveryTask: Task<Void, Never>?
    var expectingExit = false
    var consecutiveFailures = 0
    var consecutiveRecoveries = 0
    /// True after at least one successful /v1/health while this child was live.
    var everHealthy = false
    /// When true, skip auto-respawn (fatal startup / user must Start manually).
    var suppressAutoRecovery = false
    /// Exits before first healthy probe during the current start attempt streak.
    var consecutiveStartupFailures = 0

    /// Fast probes while starting; configured interval once running.
    let startupHealthInterval: TimeInterval = 2
    let maxHealthFailures = 5
    let stopGraceSeconds: TimeInterval = 8
    let maxAutoRecoveries = 8
    /// Cap respawns that never reach healthy (avoids thrashing on bad config).
    let maxStartupRecoveries = 1

    init(config: AppConfig) {
        self.config = config
    }

    func reconfigure(config: AppConfig) {
        let intervalChanged =
            self.config.healthCheckIntervalSeconds != config.healthCheckIntervalSeconds
        self.config = config
        if intervalChanged, case .running = state {
            startHealthLoop()
        }
    }

    /// Restart the health loop after an interval change (running / starting only).
    func refreshHealthLoop() {
        switch state {
        case .running, .starting:
            startHealthLoop()
        default:
            break
        }
    }

    var healthSleepInterval: TimeInterval {
        switch state {
        case .starting:
            return startupHealthInterval
        default:
            return TimeInterval(
                AppConfig.clampHealthCheckInterval(config.healthCheckIntervalSeconds)
            )
        }
    }

    @discardableResult
    func start() throws -> StartResult {
        switch state {
        case .running, .starting:
            return .alreadyRunning
        case .stopping:
            throw StartError.busy
        case .stopped, .failed:
            break
        }
        suppressAutoRecovery = false
        consecutiveStartupFailures = 0
        if tryAdoptHealthyListener() {
            consecutiveRecoveries = 0
            everHealthy = true
            return .alreadyRunning
        }
        // Stale binder on the port would make a fresh spawn exit(1).
        if PortSupport.listenerPid(port: config.port) != nil {
            PortSupport.freePort(config.port)
        }
        try doStart()
        consecutiveRecoveries = 0
        return .started
    }

    func stop() async {
        expectingExit = true
        cancelRecovery()
        cancelHealthLoop()
        update(.stopping)

        if let proc = process, proc.isRunning {
            let pid = proc.processIdentifier
            kill(pid, SIGTERM)
            let deadline = Date().addingTimeInterval(stopGraceSeconds)
            while Date() < deadline {
                if !proc.isRunning { break }
                try? await Task.sleep(for: .milliseconds(150))
            }
            if proc.isRunning {
                kill(pid, SIGKILL)
            }
        } else if let pid = adoptedPid ?? PortSupport.listenerPid(port: config.port) {
            PortSupport.killProcessTree(pid: pid)
            PortSupport.freePort(config.port)
        }

        process = nil
        adoptedPid = nil
        closeLog()
        consecutiveRecoveries = 0
        consecutiveStartupFailures = 0
        suppressAutoRecovery = false
        everHealthy = false
        update(.stopped)
    }

    /// Synchronous stop for app termination / signal paths.
    func reapSync(timeout: TimeInterval = 5) {
        expectingExit = true
        cancelRecovery()
        cancelHealthLoop()
        if let proc = process, proc.isRunning {
            let pid = proc.processIdentifier
            kill(pid, SIGTERM)
            let deadline = Date().addingTimeInterval(timeout)
            while Date() < deadline {
                if kill(pid, 0) != 0 { break }
                usleep(100_000)
            }
            if kill(pid, 0) == 0 {
                kill(pid, SIGKILL)
            }
        } else if let pid = adoptedPid ?? PortSupport.listenerPid(port: config.port) {
            PortSupport.killProcessTree(pid: pid)
            PortSupport.freePort(config.port)
        }
        process = nil
        adoptedPid = nil
        closeLog()
        consecutiveRecoveries = 0
        consecutiveStartupFailures = 0
        suppressAutoRecovery = false
        everHealthy = false
        update(.stopped)
    }

    func update(_ next: State) {
        state = next
        NotificationCenter.default.post(name: Self.stateDidChangeNotification, object: self)
    }

    func ensureDir(_ url: URL) throws {
        try FileManager.default.createDirectory(at: url, withIntermediateDirectories: true)
    }

    func closeLog() {
        try? logHandle?.close()
        logHandle = nil
    }
}
