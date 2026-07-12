import Foundation

/// Resolves how to spawn `fastfold serve` (dev-friendly; bundled Python later).
///
/// Resolution order:
/// 1. `SANDWALK_SERVE_BIN` — absolute path to an executable (args: serve --host --port)
/// 2. `fastfold` on PATH
/// 3. `<agentCliRoot>/.venv/bin/fastfold`
/// 4. `uv run --directory <agentCliRoot> fastfold serve …`
struct ServeRuntime {
    let executable: URL
    let argumentsPrefix: [String]
    let workingDirectory: URL?

    enum ResolutionError: Error, LocalizedError {
        case notFound

        var errorDescription: String? {
            "Could not find fastfold. Set SANDWALK_SERVE_BIN, install fastfold on PATH, or set SANDWALK_AGENT_CLI to the agent-cli checkout."
        }
    }

    static func resolve(config: AppConfig) throws -> ServeRuntime {
        let env = ProcessInfo.processInfo.environment
        let fm = FileManager.default

        if let override = env["SANDWALK_SERVE_BIN"], !override.isEmpty {
            let url = URL(fileURLWithPath: (override as NSString).expandingTildeInPath)
            if fm.isExecutableFile(atPath: url.path) {
                return ServeRuntime(executable: url, argumentsPrefix: [], workingDirectory: nil)
            }
        }

        // Prefer the agent-cli checkout (venv or uv) over a global `fastfold`
        // shim, which may be an older install that does not expose `serve`.
        if let root = config.agentCliRoot {
            let venvBin = root.appendingPathComponent(".venv/bin/fastfold")
            if fm.isExecutableFile(atPath: venvBin.path) {
                return ServeRuntime(
                    executable: venvBin,
                    argumentsPrefix: [],
                    workingDirectory: root
                )
            }
            if let uv = which("uv") {
                return ServeRuntime(
                    executable: URL(fileURLWithPath: uv),
                    argumentsPrefix: ["run", "--directory", root.path, "fastfold"],
                    workingDirectory: root
                )
            }
        }

        if let path = which("fastfold") {
            return ServeRuntime(
                executable: URL(fileURLWithPath: path),
                argumentsPrefix: [],
                workingDirectory: nil
            )
        }

        throw ResolutionError.notFound
    }

    func makeServeArguments(host: String, port: Int) -> [String] {
        argumentsPrefix + ["serve", "--host", host, "--port", String(port)]
    }

    func makeEnvironment() -> [String: String] {
        var env = ProcessInfo.processInfo.environment
        env["SANDWALK_SUPERVISED"] = "menubar"
        return env
    }

    private static func which(_ name: String) -> String? {
        let process = Process()
        process.executableURL = URL(fileURLWithPath: "/usr/bin/which")
        process.arguments = [name]
        let pipe = Pipe()
        process.standardOutput = pipe
        process.standardError = FileHandle.nullDevice
        do {
            try process.run()
            process.waitUntilExit()
        } catch {
            return nil
        }
        guard process.terminationStatus == 0 else { return nil }
        let data = pipe.fileHandleForReading.readDataToEndOfFile()
        let path = String(data: data, encoding: .utf8)?
            .trimmingCharacters(in: .whitespacesAndNewlines)
        guard let path, !path.isEmpty else { return nil }
        return path
    }
}
