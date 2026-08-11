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
        (
            "public / lan mode requires",
            "Remote access needs an API key — generate one under Security and enable auth, or turn off Allow remote connections"
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
        let base = "Exited with code \(code)"
        // SIGTERM / SIGKILL — often intentional or tooling; allow adopt/respawn.
        // Checked before the log scan: a signalled exit is not evidence of the
        // fatal condition some earlier line describes.
        if code == 15 || code == 9 || code == 143 || code == 137 {
            return Classification(isFatal: false, message: base)
        }

        if let hint = recentFatalHint(logURL: logURL) {
            return Classification(isFatal: true, message: hint)
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
        // Only consider the current run. A failed start writes its error and
        // exits, but that line stays in the log; scanning the whole tail made a
        // healthy server keep reporting the previous attempt's failure
        // ("database is locked") even though it was serving fine.
        let scoped = currentRunSlice(of: text)
        let lower = scoped.lowercased()
        for pattern in fatalLogPatterns {
            if lower.contains(pattern.match) {
                return pattern.message
            }
        }
        return nil
    }

    /// Log substrings that mark the start of a fresh `sandwalk serve` process.
    private static let runStartMarkers = [
        "started server process",
        "uvicorn running on",
    ]

    /// Trim everything before the last server startup line.
    ///
    /// Returns the input unchanged when no marker is present — a process that
    /// died before printing one has only its own output in the log.
    static func currentRunSlice(of text: String) -> String {
        let lower = text.lowercased()
        var cut: String.Index?
        for marker in runStartMarkers {
            if let range = lower.range(of: marker, options: .backwards) {
                if cut == nil || range.lowerBound > cut! {
                    cut = range.lowerBound
                }
            }
        }
        guard let cut else { return text }
        return String(text[cut...])
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
