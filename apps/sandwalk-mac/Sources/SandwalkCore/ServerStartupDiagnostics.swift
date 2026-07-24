import Foundation

/// Classifies agent-server exits so the menubar does not restart-loop on
/// permanent startup failures (corrupt DB, missing deps, etc.).
enum ServerStartupDiagnostics {
    /// Log substrings (lowercased) that mean respawning will not help.
    static let fatalLogPatterns: [(match: String, message: String)] = [
        (
            "database disk image is malformed",
            "Agent database is corrupt — auto-heal failed; see Logs / ~/.sandwalk"
        ),
        (
            "agent store database is corrupt",
            "Agent database is corrupt — auto-heal failed; see Logs / ~/.sandwalk"
        ),
        (
            "refusing to auto-repair",
            "Agent database is corrupt — auto-heal failed; see Logs / ~/.sandwalk"
        ),
        (
            "another sandwalk server already has this database open",
            "Agent database is locked by another Sandwalk process — Quit Sandwalk, stop leftover serve processes, then Start again"
        ),
        (
            "modulenotfounderror",
            "Python dependency missing — reinstall the agent CLI (see Logs)"
        ),
        (
            "no module named",
            "Python dependency missing — reinstall the agent CLI (see Logs)"
        ),
    ]

    struct Classification: Equatable {
        var isFatal: Bool
        var message: String
    }

    /// Decide whether auto-recovery should run after an unexpected exit.
    static func classifyExit(
        code: Int32,
        everHealthy: Bool,
        consecutiveStartupFailures: Int,
        logURL: URL
    ) -> Classification {
        if let hint = recentFatalHint(logURL: logURL) {
            return Classification(isFatal: true, message: hint)
        }

        let base = "Exited with code \(code)"
        // SIGTERM / SIGKILL — often intentional or tooling; allow adopt/respawn.
        if code == 15 || code == 9 || code == 143 || code == 137 {
            return Classification(isFatal: false, message: base)
        }

        // Never reached /v1/health more than once: same failure will loop forever.
        if !everHealthy, code != 0, consecutiveStartupFailures >= 2 {
            return Classification(
                isFatal: true,
                message: "\(base) — stopped auto-restart after repeated startup failure (see Logs)"
            )
        }

        return Classification(isFatal: false, message: base)
    }

    static func recentFatalHint(logURL: URL) -> String? {
        guard let text = readTail(of: logURL, maxBytes: 24_576) else { return nil }
        let lower = text.lowercased()
        for pattern in fatalLogPatterns {
            if lower.contains(pattern.match) {
                return pattern.message
            }
        }
        return nil
    }

    static func readTail(of url: URL, maxBytes: Int) -> String? {
        guard FileManager.default.fileExists(atPath: url.path) else { return nil }
        guard let handle = try? FileHandle(forReadingFrom: url) else { return nil }
        defer { try? handle.close() }
        let size: UInt64
        do {
            size = try handle.seekToEnd()
        } catch {
            return nil
        }
        let start = size > UInt64(maxBytes) ? size - UInt64(maxBytes) : 0
        do {
            try handle.seek(toOffset: start)
            guard let data = try handle.readToEnd(), !data.isEmpty else { return nil }
            return String(decoding: data, as: UTF8.self)
        } catch {
            return nil
        }
    }
}
