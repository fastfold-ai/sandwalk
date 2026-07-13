import Foundation

/// GUI apps launched from Finder/Dock inherit a minimal PATH (no Homebrew,
/// no pnpm). Augment before resolving CLI tools — same idea as oMLX.
enum PathSupport {
    static var augmentedPATH: String {
        var parts = (ProcessInfo.processInfo.environment["PATH"] ?? "")
            .split(separator: ":")
            .map(String.init)

        let home = NSHomeDirectory()
        let extras = [
            "/opt/homebrew/bin",
            "/opt/homebrew/sbin",
            "/usr/local/bin",
            "\(home)/Library/pnpm/bin",
            "\(home)/.local/share/pnpm",
            "\(home)/.local/bin",
            "\(home)/.bun/bin",
            "\(home)/.npm-global/bin",
            "\(home)/.nvm/current/bin",
            "\(home)/.volta/bin",
            "\(home)/.cargo/bin",
            "\(home)/.omlx/bin",
        ]
        for path in extras.reversed() where !parts.contains(path) {
            parts.insert(path, at: 0)
        }
        return parts.joined(separator: ":")
    }

    /// Environment for child processes — parent env + augmented PATH.
    static func processEnvironment(
        merging extra: [String: String] = [:]
    ) -> [String: String] {
        var env = ProcessInfo.processInfo.environment
        env["PATH"] = augmentedPATH
        for (key, value) in extra {
            env[key] = value
        }
        return env
    }

    /// Resolve an executable on the augmented PATH (absolute paths first).
    static func which(_ name: String) -> String? {
        let fm = FileManager.default
        if name.hasPrefix("/"), fm.isExecutableFile(atPath: name) {
            return name
        }

        // Fast path: known install locations before spawning `which`.
        let home = NSHomeDirectory()
        let candidates = [
            "/opt/homebrew/bin/\(name)",
            "/usr/local/bin/\(name)",
            "\(home)/Library/pnpm/bin/\(name)",
            "\(home)/.local/share/pnpm/\(name)",
            "\(home)/.local/bin/\(name)",
            "\(home)/.bun/bin/\(name)",
            "\(home)/.volta/bin/\(name)",
        ]
        for path in candidates where fm.isExecutableFile(atPath: path) {
            return path
        }

        let process = Process()
        process.executableURL = URL(fileURLWithPath: "/usr/bin/which")
        process.arguments = [name]
        process.environment = processEnvironment()
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
        guard let path, !path.isEmpty, fm.isExecutableFile(atPath: path) else {
            return nil
        }
        return path
    }
}
