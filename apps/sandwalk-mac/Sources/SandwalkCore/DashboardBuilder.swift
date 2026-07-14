import Foundation

/// Builds `apps/local-web/dist` for production dashboard serving.
enum DashboardBuilder {
    enum BuildError: Error, LocalizedError {
        case missingRepo
        case missingPnpm
        case failed(String)

        var errorDescription: String? {
            switch self {
            case .missingRepo:
                return "Sandwalk repo root not found (need package.json + cli/)."
            case .missingPnpm:
                return "pnpm not found. Install pnpm or ensure it is on PATH."
            case .failed(let message):
                return message
            }
        }
    }

    static func distURL(repoRoot: URL) -> URL {
        repoRoot.appendingPathComponent("apps/local-web/dist", isDirectory: true)
    }

    static func indexURL(repoRoot: URL) -> URL {
        distURL(repoRoot: repoRoot).appendingPathComponent("index.html")
    }

    static func isBuilt(repoRoot: URL) -> Bool {
        FileManager.default.fileExists(atPath: indexURL(repoRoot: repoRoot).path)
    }

    /// Run `pnpm --filter @sandwalk/agent-local-web build` when dist is missing
    /// (or always when `force` is true).
    static func ensureBuilt(repoRoot: URL, force: Bool = false, logURL: URL? = nil) throws {
        if !force, isBuilt(repoRoot: repoRoot) {
            return
        }
        guard let pnpm = PathSupport.which("pnpm") else {
            throw BuildError.missingPnpm
        }

        let proc = Process()
        proc.executableURL = URL(fileURLWithPath: pnpm)
        proc.arguments = [
            "--dir", repoRoot.path,
            "--filter", "@sandwalk/agent-local-web",
            "build",
        ]
        proc.currentDirectoryURL = repoRoot
        proc.environment = PathSupport.processEnvironment(merging: [
            "SANDWALK_SUPERVISED": "menubar",
        ])

        var logHandle: FileHandle?
        if let logURL {
            try FileManager.default.createDirectory(
                at: logURL.deletingLastPathComponent(),
                withIntermediateDirectories: true
            )
            if !FileManager.default.fileExists(atPath: logURL.path) {
                FileManager.default.createFile(atPath: logURL.path, contents: nil)
            }
            let handle = try FileHandle(forWritingTo: logURL)
            try handle.seekToEnd()
            let banner = Data(
                "\n--- dashboard build \(ISO8601DateFormatter().string(from: Date())) ---\n".utf8
            )
            try handle.write(contentsOf: banner)
            proc.standardOutput = handle
            proc.standardError = handle
            logHandle = handle
        } else {
            proc.standardOutput = FileHandle.nullDevice
            proc.standardError = FileHandle.nullDevice
        }

        defer { try? logHandle?.close() }

        do {
            try proc.run()
        } catch {
            throw BuildError.failed(error.localizedDescription)
        }
        proc.waitUntilExit()

        guard proc.terminationStatus == 0, isBuilt(repoRoot: repoRoot) else {
            throw BuildError.failed(
                "Dashboard build failed (exit \(proc.terminationStatus)). Check logs/web.log."
            )
        }
    }
}
