import Foundation

/// Resolves how to spawn `sandwalk serve` (dev-friendly; bundled Python later).
///
/// Resolution order:
/// 1. `SANDWALK_SERVE_BIN` — absolute path to an executable (args: serve --host --port)
/// 2. `<agentCliRoot>/.venv/bin/sandwalk` (or legacy `fastfold`)
/// 3. `uv run --directory <agentCliRoot> sandwalk serve …`
/// 4. `sandwalk` / `fastfold` on PATH
struct ServeRuntime {
    let executable: URL
    let argumentsPrefix: [String]
    let workingDirectory: URL?

    enum ResolutionError: Error, LocalizedError {
        case notFound

        var errorDescription: String? {
            "Could not find sandwalk. Set SANDWALK_SERVE_BIN, install the CLI, or set SANDWALK_AGENT_CLI to the monorepo cli/ directory."
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

        // Prefer the monorepo cli checkout (venv or uv) over a global shim.
        if let root = config.agentCliRoot {
            for name in ["sandwalk", "fastfold"] {
                let venvBin = root.appendingPathComponent(".venv/bin/\(name)")
                if fm.isExecutableFile(atPath: venvBin.path) {
                    return ServeRuntime(
                        executable: venvBin,
                        argumentsPrefix: [],
                        workingDirectory: root
                    )
                }
            }
            if let uv = which("uv") {
                return ServeRuntime(
                    executable: URL(fileURLWithPath: uv),
                    argumentsPrefix: ["run", "--directory", root.path, "sandwalk"],
                    workingDirectory: root
                )
            }
        }

        if let path = which("sandwalk") ?? which("fastfold") {
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
        // Pin to Application Support so CLI `sandwalk auth` and serve share one
        // file. Ignore stale shell overrides (e.g. /tmp from local tests).
        env["SANDWALK_SETTINGS_PATH"] = AuthSettingsStore.settingsFileURL().path
        env.removeValue(forKey: "SANDWALK_HOME")
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
