import Darwin
import Foundation

extension ServerProcess {
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

    /// If something healthy is already on our port, supervise it instead of spawning.
    @discardableResult
    func tryAdoptHealthyListener() -> Bool {
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

    func doStart() throws {
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
        everHealthy = false
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

    func handleProcessExit(code: Int32) {
        let wasExpecting = expectingExit
        expectingExit = false
        process = nil
        closeLog()
        cancelHealthLoop()
        if wasExpecting {
            update(.stopped)
            return
        }

        if !everHealthy {
            consecutiveStartupFailures += 1
        }

        let classification = ServerStartupDiagnostics.classifyExit(
            code: code,
            everHealthy: everHealthy,
            consecutiveStartupFailures: consecutiveStartupFailures,
            logURL: config.serverLogURL
        )
        update(.failed(message: classification.message))

        let startupExhausted =
            !everHealthy && consecutiveStartupFailures > maxStartupRecoveries
        if classification.isFatal || suppressAutoRecovery || startupExhausted {
            suppressAutoRecovery = true
            cancelRecovery()
            NSLog(
                "Sandwalk: API fatal/startup exit — not auto-restarting (%@)",
                classification.message
            )
            return
        }

        // External kill / crash — recover by adopting a replacement listener
        // or respawning. Staying in .failed leaves the menubar "partially
        // running" whenever tools restart the API out-of-band.
        scheduleRecovery(reason: "process-exit")
    }
}
