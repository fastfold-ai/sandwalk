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

    private var process: Process?
    /// Listener we did not spawn (orphan / external) but are supervising.
    private var adoptedPid: Int32?
    private var logHandle: FileHandle?
    private var healthTask: Task<Void, Never>?
    private var recoveryTask: Task<Void, Never>?
    private var expectingExit = false
    private var consecutiveFailures = 0
    private var consecutiveRecoveries = 0

    /// Fast probes while starting; configured interval once running.
    private let startupHealthInterval: TimeInterval = 2
    private let maxHealthFailures = 5
    private let stopGraceSeconds: TimeInterval = 8
    private let maxAutoRecoveries = 8

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

    private var healthSleepInterval: TimeInterval {
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
        if tryAdoptHealthyListener() {
            consecutiveRecoveries = 0
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
        update(.stopped)
    }

    /// If something healthy is already on our port, supervise it instead of spawning.
    @discardableResult
    private func tryAdoptHealthyListener() -> Bool {
        let healthy = PortSupport.probeHTTPSync(url: config.healthURL) { $0 == 200 }
        guard healthy else { return false }
        let pid = PortSupport.listenerPid(port: config.port) ?? 0
        adoptedPid = pid == 0 ? nil : pid
        process = nil
        consecutiveFailures = 0
        expectingExit = false
        update(.running(pid: pid))
        startHealthLoop()
        return true
    }

    enum StartError: Error, LocalizedError {
        case busy
        case spawnFailed(String)

        var errorDescription: String? {
            switch self {
            case .busy: return "Server is busy stopping."
            case .spawnFailed(let message): return message
            }
        }
    }

    // MARK: - Spawn

    private func doStart() throws {
        let runtime = try ServeRuntime.resolve(config: config)
        try ensureDir(config.supportDirectory.appendingPathComponent("logs", isDirectory: true))

        let logURL = config.serverLogURL
        if !FileManager.default.fileExists(atPath: logURL.path) {
            FileManager.default.createFile(atPath: logURL.path, contents: nil)
        }
        let handle = try FileHandle(forWritingTo: logURL)
        try handle.seekToEnd()
        logHandle = handle

        let proc = Process()
        proc.executableURL = runtime.executable
        proc.arguments = runtime.makeServeArguments(host: config.bindHost, port: config.port)
        proc.environment = runtime.makeEnvironment(config: config)
        proc.currentDirectoryURL = runtime.workingDirectory
        proc.standardOutput = handle
        proc.standardError = handle
        proc.terminationHandler = { [weak self] term in
            DispatchQueue.main.async {
                self?.handleProcessExit(code: term.terminationStatus)
            }
        }

        consecutiveFailures = 0
        expectingExit = false
        update(.starting)
        do {
            try proc.run()
        } catch {
            closeLog()
            update(.failed(message: error.localizedDescription))
            throw StartError.spawnFailed(error.localizedDescription)
        }
        process = proc
        startHealthLoop()
    }

    private func handleProcessExit(code: Int32) {
        let wasExpecting = expectingExit
        expectingExit = false
        process = nil
        closeLog()
        cancelHealthLoop()
        if wasExpecting {
            update(.stopped)
        } else {
            // External kill / crash — recover by adopting a replacement listener
            // or respawning. Staying in .failed leaves the menubar "partially
            // running" whenever tools restart the API out-of-band.
            update(.failed(message: "Exited with code \(code)"))
            scheduleRecovery(reason: "process-exit")
        }
    }

    // MARK: - Health

    private func startHealthLoop() {
        cancelHealthLoop()
        healthTask = Task { @MainActor [weak self] in
            while !Task.isCancelled {
                guard let self else { return }
                await self.tickHealth()
                try? await Task.sleep(for: .seconds(self.healthSleepInterval))
            }
        }
    }

    private func cancelHealthLoop() {
        healthTask?.cancel()
        healthTask = nil
    }

    private func cancelRecovery() {
        recoveryTask?.cancel()
        recoveryTask = nil
    }

    /// After an unexpected API death, adopt a healthy listener on our port or respawn.
    private func scheduleRecovery(reason: String) {
        cancelRecovery()
        recoveryTask = Task { @MainActor [weak self] in
            guard let self else { return }
            // Brief pause so a replacement `sandwalk serve` can bind first.
            try? await Task.sleep(for: .milliseconds(900))
            guard !Task.isCancelled else { return }
            switch self.state {
            case .failed, .stopped:
                break
            default:
                return
            }
            if self.tryAdoptHealthyListener() {
                self.consecutiveRecoveries = 0
                NSLog("Sandwalk: API recovered by adopting listener (%@)", reason)
                return
            }
            if self.consecutiveRecoveries >= self.maxAutoRecoveries {
                NSLog("Sandwalk: API recovery gave up after %d attempts (%@)", self.maxAutoRecoveries, reason)
                return
            }
            self.consecutiveRecoveries += 1
            do {
                try self.doStart()
                NSLog("Sandwalk: API respawned after %@ (attempt %d)", reason, self.consecutiveRecoveries)
            } catch {
                NSLog("Sandwalk: API respawn failed (%@): %@", reason, error.localizedDescription)
                // Try again with backoff.
                try? await Task.sleep(for: .seconds(2))
                guard !Task.isCancelled else { return }
                self.scheduleRecovery(reason: "retry")
            }
        }
    }

    @MainActor
    private func tickHealth() async {
        switch state {
        case .starting, .running:
            break
        default:
            return
        }

        let ok = await probeHealth()
        if ok {
            consecutiveFailures = 0
            consecutiveRecoveries = 0
            let pid = process?.processIdentifier ?? adoptedPid
                ?? PortSupport.listenerPid(port: config.port) ?? 0
            if case .starting = state {
                update(.running(pid: pid))
            } else if case .running = state, process == nil, adoptedPid == nil, pid != 0 {
                adoptedPid = pid
                update(.running(pid: pid))
            } else if case .running = state, let adopted = adoptedPid, adopted != 0 {
                // Child was replaced out-of-band — track the live listener.
                if let live = PortSupport.listenerPid(port: config.port), live != adopted {
                    adoptedPid = live
                    update(.running(pid: live))
                }
            }
        } else {
            consecutiveFailures += 1
            if process == nil, adoptedPid != nil || PortSupport.listenerPid(port: config.port) == nil {
                // Adopted listener disappeared.
                if consecutiveFailures >= maxHealthFailures {
                    adoptedPid = nil
                    update(.failed(message: "API stopped responding on \(config.healthURL.absoluteString)"))
                    cancelHealthLoop()
                    scheduleRecovery(reason: "health-lost")
                }
                return
            }
            // Supervised child still listed as running but health is down —
            // if the PID is gone, recover instead of waiting forever.
            if let proc = process, !proc.isRunning {
                process = nil
                update(.failed(message: "API process ended while unhealthy"))
                cancelHealthLoop()
                scheduleRecovery(reason: "stale-child")
                return
            }
            if case .starting = state, consecutiveFailures >= maxHealthFailures {
                // Keep waiting a bit longer during cold start — uv can be slow.
                if consecutiveFailures >= maxHealthFailures * 3 {
                    update(.failed(message: "Health check timed out on \(config.healthURL.absoluteString)"))
                    expectingExit = true
                    process?.terminate()
                    scheduleRecovery(reason: "start-timeout")
                }
            }
        }
    }

    private func probeHealth() async -> Bool {
        if let code = await Task.detached(priority: .utility, operation: {
            PortSupport.curlStatusPublic(url: self.config.healthURL, timeout: 2)
        }).value {
            return code == 200
        }
        var request = URLRequest(url: config.healthURL)
        request.timeoutInterval = 2
        request.httpMethod = "GET"
        do {
            let (_, response) = try await URLSession.shared.data(for: request)
            return (response as? HTTPURLResponse)?.statusCode == 200
        } catch {
            return false
        }
    }

    // MARK: - Helpers

    private func update(_ next: State) {
        state = next
        NotificationCenter.default.post(name: Self.stateDidChangeNotification, object: self)
    }

    private func ensureDir(_ url: URL) throws {
        try FileManager.default.createDirectory(at: url, withIntermediateDirectories: true)
    }

    private func closeLog() {
        try? logHandle?.close()
        logHandle = nil
    }
}
