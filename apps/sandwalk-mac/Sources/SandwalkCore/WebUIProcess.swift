import Darwin
import Foundation

/// Owns the Vite / pnpm web dashboard child process.
final class WebUIProcess: @unchecked Sendable {
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

    static let stateDidChangeNotification = Notification.Name("SandwalkWebUIStateDidChange")

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
    private let maxHealthFailures = 45 // Vite cold start can be slow
    private let stopGraceSeconds: TimeInterval = 8

    init(config: AppConfig) {
        self.config = config
    }

    func reconfigure(config: AppConfig) {
        self.config = config
    }

    func start() throws {
        switch state {
        case .running, .starting:
            return
        case .stopping:
            throw StartError.busy
        case .stopped, .failed:
            break
        }
        if tryAdoptHealthyListener() {
            return
        }
        if PortSupport.listenerPid(port: config.dashboardPort) != nil {
            PortSupport.freePort(config.dashboardPort)
        }
        try doStart()
    }

    func stop() async {
        expectingExit = true
        cancelHealthLoop()
        update(.stopping)

        if let proc = process, proc.isRunning {
            let pid = proc.processIdentifier
            PortSupport.killProcessTree(pid: pid)
            let deadline = Date().addingTimeInterval(stopGraceSeconds)
            while Date() < deadline {
                if !proc.isRunning { break }
                try? await Task.sleep(for: .milliseconds(150))
            }
            if proc.isRunning {
                kill(pid, SIGKILL)
            }
        } else if let pid = adoptedPid ?? PortSupport.listenerPid(port: config.dashboardPort) {
            PortSupport.killProcessTree(pid: pid)
        }
        PortSupport.freePort(config.dashboardPort)
        process = nil
        adoptedPid = nil
        closeLog()
        update(.stopped)
    }

    func reapSync(timeout: TimeInterval = 5) {
        expectingExit = true
        cancelHealthLoop()
        if let proc = process, proc.isRunning {
            let pid = proc.processIdentifier
            PortSupport.killProcessTree(pid: pid)
            let deadline = Date().addingTimeInterval(timeout)
            while Date() < deadline {
                if kill(pid, 0) != 0 { break }
                usleep(100_000)
            }
            if kill(pid, 0) == 0 {
                kill(pid, SIGKILL)
            }
        } else if let pid = adoptedPid ?? PortSupport.listenerPid(port: config.dashboardPort) {
            PortSupport.killProcessTree(pid: pid)
        }
        PortSupport.freePort(config.dashboardPort)
        process = nil
        adoptedPid = nil
        closeLog()
        update(.stopped)
    }

    @discardableResult
    private func tryAdoptHealthyListener() -> Bool {
        let healthy = PortSupport.probeHTTPSync(url: config.webHealthURL) { (200..<500).contains($0) }
        guard healthy else { return false }
        let pid = PortSupport.listenerPid(port: config.dashboardPort) ?? 0
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
        case missingRepo
        case missingPnpm
        case spawnFailed(String)

        var errorDescription: String? {
            switch self {
            case .busy: return "Web UI is busy stopping."
            case .missingRepo: return "Sandwalk repo root not found (need package.json + cli/)."
            case .missingPnpm: return "pnpm not found. Install pnpm or ensure it is on PATH (Homebrew / ~/Library/pnpm/bin)."
            case .spawnFailed(let message): return message
            }
        }
    }

    private func doStart() throws {
        guard let repoRoot = config.repoRoot else {
            throw StartError.missingRepo
        }
        guard let pnpm = PathSupport.which("pnpm") else {
            throw StartError.missingPnpm
        }

        try ensureDir(config.supportDirectory.appendingPathComponent("logs", isDirectory: true))
        let logURL = config.webLogURL
        if !FileManager.default.fileExists(atPath: logURL.path) {
            FileManager.default.createFile(atPath: logURL.path, contents: nil)
        }
        let handle = try FileHandle(forWritingTo: logURL)
        try handle.seekToEnd()
        logHandle = handle

        let proc = Process()
        proc.executableURL = URL(fileURLWithPath: pnpm)
        proc.arguments = [
            "--dir", repoRoot.path,
            "--filter", "@sandwalk/agent-local-web",
            "exec", "vite",
            "--host", config.dashboardHost,
            "--port", String(config.dashboardPort),
        ]
        proc.currentDirectoryURL = repoRoot
        proc.environment = PathSupport.processEnvironment(merging: [
            "SANDWALK_SUPERVISED": "menubar",
        ])
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
            update(.failed(message: "Web UI exited with code \(code)"))
        }
    }

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
                ?? PortSupport.listenerPid(port: config.dashboardPort) ?? 0
            if case .starting = state {
                update(.running(pid: pid))
            } else if case .running = state, process == nil, adoptedPid == nil, pid != 0 {
                adoptedPid = pid
                update(.running(pid: pid))
            }
        } else if process == nil, adoptedPid != nil || PortSupport.listenerPid(port: config.dashboardPort) == nil {
            consecutiveFailures += 1
            if consecutiveFailures >= 5 {
                adoptedPid = nil
                update(.failed(message: "Web UI stopped responding on \(config.webHealthURL.absoluteString)"))
                cancelHealthLoop()
            }
        } else if case .starting = state {
            consecutiveFailures += 1
            if consecutiveFailures >= maxHealthFailures {
                update(.failed(message: "Web UI health timed out on \(config.webHealthURL.absoluteString)"))
                expectingExit = true
                if let pid = process?.processIdentifier {
                    PortSupport.killProcessTree(pid: pid)
                }
            }
        }
    }

    private func probeHealth() async -> Bool {
        var request = URLRequest(url: config.webHealthURL)
        request.timeoutInterval = 2
        request.httpMethod = "GET"
        do {
            let (_, response) = try await URLSession.shared.data(for: request)
            let code = (response as? HTTPURLResponse)?.statusCode ?? 0
            return (200..<500).contains(code)
        } catch {
            return false
        }
    }

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
