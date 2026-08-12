import Foundation

/// Installs a user-PATH `sandwalk` shim when the helper ships a bundled agent runtime.
///
/// - Writes `~/.local/bin/sandwalk` (same location as the curl / uv install).
/// - Only creates or updates shims marked `# Managed by Sandwalk.app`.
/// - Never overwrites a foreign install (uv tool, pipx, manual).
/// - Refreshes the shim on every launch so app moves/updates keep working.
/// - Ensures `~/.local/bin` is on PATH via a small block in `~/.zprofile` when needed.
enum CliPathInstaller {
    static let managedMarker = "# Managed by Sandwalk.app"
    static let pathBlockMarker = "# Added by Sandwalk.app"

    enum Outcome: Equatable {
        case skippedNoBundledRuntime
        case skippedForeignInstall(path: String)
        case installed(path: String)
        case updated(path: String)
        case unchanged(path: String)
        case failed(String)
    }

    @discardableResult
    static func ensureInstalled(bundle: Bundle = .main, force: Bool = false) -> Outcome {
        guard let python = ServeRuntime.bundledPythonURL(bundle: bundle) else {
            return .skippedNoBundledRuntime
        }
        return ensureInstalled(
            pythonURL: python,
            homeDirectory: URL(fileURLWithPath: NSHomeDirectory(), isDirectory: true),
            force: force
        )
    }

    /// Snapshot for Settings / control plane (does not write).
    static func status(bundle: Bundle = .main) -> [String: Any] {
        status(
            pythonURL: ServeRuntime.bundledPythonURL(bundle: bundle),
            homeDirectory: URL(fileURLWithPath: NSHomeDirectory(), isDirectory: true)
        )
    }

    static func status(pythonURL: URL?, homeDirectory: URL) -> [String: Any] {
        let fm = FileManager.default
        let shim = homeDirectory
            .appendingPathComponent(".local/bin", isDirectory: true)
            .appendingPathComponent("sandwalk")
        let exists = fm.isExecutableFile(atPath: shim.path)
        let managed = exists && isManagedShim(at: shim)
        let foreign = exists && !managed
        let pathReady = localBinReferencedInProfiles(homeDirectory: homeDirectory)
        let bundled = pythonURL.map { fm.isExecutableFile(atPath: $0.path) } ?? false

        let state: String = {
            if !bundled { return "unavailable" }
            if !exists { return "missing" }
            if foreign { return "foreign" }
            return "ready"
        }()

        let message: String = {
            switch state {
            case "unavailable":
                return "This build has no bundled agent runtime (dev-only)."
            case "missing":
                return "CLI command not installed. Use Install to add sandwalk to ~/.local/bin."
            case "foreign":
                return "A separate CLI install owns sandwalk (curl/uv/pipx). Reinstall replaces it with the app’s CLI."
            default:
                return pathReady
                    ? "Terminal: sandwalk — uses the app’s bundled CLI."
                    : "Installed at ~/.local/bin/sandwalk. Open a new terminal (PATH may need ~/.local/bin)."
            }
        }()

        var payload: [String: Any] = [
            "state": state,
            "command": "sandwalk",
            "shim_path": shim.path,
            "shim_exists": exists,
            "managed": managed,
            "foreign": foreign,
            "bundled_runtime": bundled,
            "path_ready": pathReady,
            "message": message,
        ]
        if let pythonURL, bundled {
            payload["python_path"] = pythonURL.path
            if let version = probeVersion(pythonURL: pythonURL) {
                payload["version"] = version
            }
        }
        return payload
    }

    /// Testable entry — no Bundle dependency.
    @discardableResult
    static func ensureInstalled(
        pythonURL: URL,
        homeDirectory: URL,
        force: Bool = false
    ) -> Outcome {
        let fm = FileManager.default
        guard fm.isExecutableFile(atPath: pythonURL.path) else {
            return .failed("bundled python is not executable: \(pythonURL.path)")
        }

        let binDir = homeDirectory.appendingPathComponent(".local/bin", isDirectory: true)
        let shim = binDir.appendingPathComponent("sandwalk")

        do {
            try fm.createDirectory(at: binDir, withIntermediateDirectories: true)
        } catch {
            return .failed("could not create \(binDir.path): \(error.localizedDescription)")
        }

        let script = makeShimScript(pythonURL: pythonURL)
        if fm.fileExists(atPath: shim.path) {
            if !isManagedShim(at: shim), !force {
                return .skippedForeignInstall(path: shim.path)
            }
            if (try? String(contentsOf: shim, encoding: .utf8)) == script {
                ensureLocalBinOnPATH(homeDirectory: homeDirectory)
                return .unchanged(path: shim.path)
            }
            do {
                try script.write(to: shim, atomically: true, encoding: .utf8)
                try fm.setAttributes(
                    [.posixPermissions: 0o755],
                    ofItemAtPath: shim.path
                )
                ensureLocalBinOnPATH(homeDirectory: homeDirectory)
                return .updated(path: shim.path)
            } catch {
                return .failed("could not update \(shim.path): \(error.localizedDescription)")
            }
        }

        do {
            try script.write(to: shim, atomically: true, encoding: .utf8)
            try fm.setAttributes(
                [.posixPermissions: 0o755],
                ofItemAtPath: shim.path
            )
            ensureLocalBinOnPATH(homeDirectory: homeDirectory)
            return .installed(path: shim.path)
        } catch {
            return .failed("could not write \(shim.path): \(error.localizedDescription)")
        }
    }

    static func outcomePayload(_ outcome: Outcome) -> [String: Any] {
        var base = status()
        switch outcome {
        case .skippedNoBundledRuntime:
            base["outcome"] = "skipped_no_bundled_runtime"
        case .skippedForeignInstall(let path):
            base["outcome"] = "skipped_foreign"
            base["outcome_path"] = path
        case .installed(let path):
            base["outcome"] = "installed"
            base["outcome_path"] = path
        case .updated(let path):
            base["outcome"] = "updated"
            base["outcome_path"] = path
        case .unchanged(let path):
            base["outcome"] = "unchanged"
            base["outcome_path"] = path
        case .failed(let message):
            base["outcome"] = "failed"
            base["error"] = message
        }
        return base
    }

    static func makeShimScript(pythonURL: URL) -> String {
        let python = shellEscape(pythonURL.path)
        return """
        #!/bin/bash
        \(managedMarker)
        # Rewritten when Sandwalk Server launches so app moves/updates keep working.
        set -euo pipefail
        exec \(python) -m cli "$@"

        """
    }

    static func isManagedShim(at url: URL) -> Bool {
        guard let text = try? String(contentsOf: url, encoding: .utf8) else {
            return false
        }
        return text.contains(managedMarker)
    }

    /// Append a PATH export to ~/.zprofile when ~/.local/bin is not already
    /// referenced in common shell profiles. Idempotent via pathBlockMarker.
    @discardableResult
    static func ensureLocalBinOnPATH(homeDirectory: URL) -> Bool {
        if localBinReferencedInProfiles(homeDirectory: homeDirectory) {
            return false
        }

        let zprofile = homeDirectory.appendingPathComponent(".zprofile")
        if let text = try? String(contentsOf: zprofile, encoding: .utf8),
           text.contains(pathBlockMarker)
        {
            return false
        }

        let block = """

        \(pathBlockMarker)
        export PATH="$HOME/.local/bin:$PATH"

        """
        let existing = (try? String(contentsOf: zprofile, encoding: .utf8)) ?? ""
        do {
            try (existing + block).write(to: zprofile, atomically: true, encoding: .utf8)
            return true
        } catch {
            NSLog("Sandwalk: could not update \(zprofile.path) for PATH — \(error.localizedDescription)")
            return false
        }
    }

    static func localBinReferencedInProfiles(homeDirectory: URL) -> Bool {
        let profiles = [
            homeDirectory.appendingPathComponent(".zprofile"),
            homeDirectory.appendingPathComponent(".zshrc"),
            homeDirectory.appendingPathComponent(".bash_profile"),
            homeDirectory.appendingPathComponent(".bashrc"),
            homeDirectory.appendingPathComponent(".profile"),
        ]
        let needle = ".local/bin"
        for profile in profiles {
            if let text = try? String(contentsOf: profile, encoding: .utf8),
               text.contains(needle)
            {
                return true
            }
        }
        return false
    }

    private static func probeVersion(pythonURL: URL) -> String? {
        let process = Process()
        process.executableURL = pythonURL
        process.arguments = ["-m", "cli", "--version"]
        let pipe = Pipe()
        process.standardOutput = pipe
        process.standardError = FileHandle.nullDevice
        do {
            try process.run()
        } catch {
            return nil
        }
        let deadline = Date().addingTimeInterval(5)
        while process.isRunning, Date() < deadline {
            Thread.sleep(forTimeInterval: 0.05)
        }
        if process.isRunning {
            process.terminate()
            return nil
        }
        guard process.terminationStatus == 0 else { return nil }
        let data = pipe.fileHandleForReading.readDataToEndOfFile()
        let text = String(data: data, encoding: .utf8)?
            .trimmingCharacters(in: .whitespacesAndNewlines)
        guard let text, !text.isEmpty else { return nil }
        return text
    }

    private static func shellEscape(_ path: String) -> String {
        "'" + path.replacingOccurrences(of: "'", with: "'\\''") + "'"
    }
}
