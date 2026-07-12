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
    private var expectingExit = false
    private var consecutiveFailures = 0

    private let healthInterval: TimeInterval = 2
    private let maxHealthFailures = 5
    private let stopGraceSeconds: TimeInterval = 8

    init(config: AppConfig) {
        self.config = config
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
            return .alreadyRunning
        }
        // Stale binder on the port would make a fresh spawn exit(1).
        if PortSupport.listenerPid(port: config.port) != nil {
            PortSupport.freePort(config.port)
        }
        try doStart()
        return .started
    }

    func stop() async {
        expectingExit = true
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
        update(.stopped)
    }

    /// Synchronous stop for app termination / signal paths.
    func reapSync(timeout: TimeInterval = 5) {
        expectingExit = true
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
        proc.environment = runtime.makeEnvironment()
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
            update(.failed(message: "Exited with code \(code)"))
        }
    }

    // MARK: - Health

    private func startHealthLoop() {
        cancelHealthLoop()
        healthTask = Task { @MainActor [weak self] in
            while !Task.isCancelled {
                guard let self else { return }
                await self.tickHealth()
                try? await Task.sleep(for: .seconds(self.healthInterval))
            }
        }
    }

    private func cancelHealthLoop() {
        healthTask?.cancel()
        healthTask = nil
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
            let pid = process?.processIdentifier ?? adoptedPid
                ?? PortSupport.listenerPid(port: config.port) ?? 0
            if case .starting = state {
                update(.running(pid: pid))
            } else if case .running = state, process == nil, adoptedPid == nil, pid != 0 {
                adoptedPid = pid
                update(.running(pid: pid))
            }
        } else {
            consecutiveFailures += 1
            if process == nil, adoptedPid != nil || PortSupport.listenerPid(port: config.port) == nil {
                // Adopted listener disappeared.
                if consecutiveFailures >= maxHealthFailures {
                    adoptedPid = nil
                    update(.failed(message: "API stopped responding on \(config.healthURL.absoluteString)"))
                    cancelHealthLoop()
                }
                return
            }
            if case .starting = state, consecutiveFailures >= maxHealthFailures {
                // Keep waiting a bit longer during cold start — uv can be slow.
                if consecutiveFailures >= maxHealthFailures * 3 {
                    update(.failed(message: "Health check timed out on \(config.healthURL.absoluteString)"))
                    expectingExit = true
                    process?.terminate()
                }
            }
        }
    }

    private func probeHealth() async -> Bool {
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
