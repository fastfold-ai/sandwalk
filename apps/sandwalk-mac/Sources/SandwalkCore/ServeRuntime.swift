import Foundation

/// Resolves how to spawn `sandwalk serve`.
///
/// Resolution order:
/// 1. `SANDWALK_SERVE_BIN` — absolute path to an executable (args: serve --host --port)
/// 2. Bundled `Contents/Resources/agent-runtime` CPython (`python -m cli`)
/// 3. `<agentCliRoot>/.venv/bin/sandwalk` (or legacy `fastfold`)
/// 4. `uv run --directory <agentCliRoot> sandwalk serve …`
/// 5. `sandwalk` / `fastfold` on PATH
struct ServeRuntime {
    let executable: URL
    let argumentsPrefix: [String]
    let workingDirectory: URL?
    /// Bin directory of the resolved venv/install, when known. GUI-launched
    /// processes don't get an activated venv on PATH just because we're
    /// running its interpreter directly — without this, pip-installed
    /// console scripts (e.g. Modal's `modal` CLI) resolve via `import` but
    /// not via `shutil.which`, even though the exact same venv installed
    /// them right next to the running interpreter.
    let venvBinDirectory: URL?

    enum ResolutionError: Error, LocalizedError {
        case notFound

        var errorDescription: String? {
            "Could not find sandwalk. Set SANDWALK_SERVE_BIN, install the CLI, or set SANDWALK_AGENT_CLI to the monorepo cli/ directory."
        }
    }

    /// Packaged helper ships CPython under Resources/agent-runtime.
    static func bundledPythonURL(bundle: Bundle = .main) -> URL? {
        guard let resources = bundle.resourceURL else { return nil }
        let bin = resources.appendingPathComponent("agent-runtime/bin", isDirectory: true)
        let fm = FileManager.default
        for name in ["python3.12", "python3.11", "python3", "python"] {
            let url = bin.appendingPathComponent(name)
            if fm.isExecutableFile(atPath: url.path) {
                return url
            }
        }
        return nil
    }

    static func resolve(config: AppConfig) throws -> ServeRuntime {
        let env = ProcessInfo.processInfo.environment
        let fm = FileManager.default

        if let override = env["SANDWALK_SERVE_BIN"], !override.isEmpty {
            let url = URL(fileURLWithPath: (override as NSString).expandingTildeInPath)
            if fm.isExecutableFile(atPath: url.path) {
                return ServeRuntime(
                    executable: url,
                    argumentsPrefix: [],
                    workingDirectory: nil,
                    venvBinDirectory: url.deletingLastPathComponent()
                )
            }
        }

        if let python = bundledPythonURL() {
            return ServeRuntime(
                executable: python,
                argumentsPrefix: ["-m", "cli"],
                workingDirectory: nil,
                venvBinDirectory: python.deletingLastPathComponent()
            )
        }

        // Prefer the monorepo cli checkout (venv or uv) over a global shim.
        if let root = config.agentCliRoot {
            for name in ["sandwalk", "fastfold"] {
                let venvBin = root.appendingPathComponent(".venv/bin/\(name)")
                if fm.isExecutableFile(atPath: venvBin.path) {
                    return ServeRuntime(
                        executable: venvBin,
                        argumentsPrefix: [],
                        workingDirectory: root,
                        venvBinDirectory: venvBin.deletingLastPathComponent()
                    )
                }
            }
            if let uv = PathSupport.which("uv") {
                // `uv run` resolves/activates its own venv PATH for the
                // subprocess it spawns, so no extra venvBinDirectory needed.
                return ServeRuntime(
                    executable: URL(fileURLWithPath: uv),
                    argumentsPrefix: ["run", "--directory", root.path, "sandwalk"],
                    workingDirectory: root,
                    venvBinDirectory: nil
                )
            }
        }

        if let path = PathSupport.which("sandwalk") ?? PathSupport.which("fastfold") {
            let url = URL(fileURLWithPath: path)
            return ServeRuntime(
                executable: url,
                argumentsPrefix: [],
                workingDirectory: nil,
                venvBinDirectory: url.deletingLastPathComponent()
            )
        }

        throw ResolutionError.notFound
    }

    func makeServeArguments(host: String, port: Int) -> [String] {
        var args = argumentsPrefix + ["serve", "--host", host, "--port", String(port)]
        // Match CLI: non-loopback bind (Network → Allow Remote Connections).
        let loopback = host == "127.0.0.1" || host == "localhost" || host == "::1"
        if !loopback {
            args.append("--public")
        }
        return args
    }

    func makeEnvironment(config: AppConfig) -> [String: String] {
        var env = PathSupport.processEnvironment(merging: [
            "SANDWALK_SUPERVISED": "menubar",
            "SANDWALK_SETTINGS_PATH": AuthSettingsStore.settingsFileURL().path,
            "SANDWALK_DB_AUTO_HEAL": config.dbAutoHeal ? "1" : "0",
            // Where the dashboard actually lives — bundled on the API port in
            // production, or the separate Vite dev server otherwise. Lets the
            // Slack App Home builder link to the right place (e.g. "Open
            // Sandwalk", session links) instead of assuming the API port.
            "SANDWALK_DASHBOARD_BASE_URL": config.dashboardURL.absoluteString,
            // The bundled runtime is inside a signed bundle. Bytecode written
            // next to the sources would break the code-signature seal, so
            // send it to Caches instead.
            "PYTHONPYCACHEPREFIX": FileManager.default
                .urls(for: .cachesDirectory, in: .userDomainMask)[0]
                .appendingPathComponent("Sandwalk/pycache", isDirectory: true)
                .path,
        ])
        if let venvBinDirectory {
            let venvBin = venvBinDirectory.path
            let current = env["PATH"] ?? ""
            if !current.split(separator: ":").map(String.init).contains(venvBin) {
                env["PATH"] = "\(venvBin):\(current)"
            }
        }
        // Pin to Application Support; ignore stale shell overrides (e.g. /tmp).
        env.removeValue(forKey: "SANDWALK_HOME")
        if config.usesBundledDashboard, let dist = config.uiDistURL {
            env["SANDWALK_UI_DIST"] = dist.path
        } else {
            env.removeValue(forKey: "SANDWALK_UI_DIST")
            env.removeValue(forKey: "FASTFOLD_UI_DIST")
        }
        return env
    }
}
