import AppKit
import Foundation

/// Detects a second copy of the menubar helper.
///
/// Two helpers each supervise their own `sandwalk serve`, and the second one
/// loses the exclusive SQLite lock — the agent then reports "database is locked
/// by another process" and the pair fight over port 8787. macOS does not prevent
/// this on its own: a helper orphaned to `launchd` (its parent app was killed, or
/// a terminate was cancelled) keeps running and is re-launched alongside.
enum SingleInstanceGuard {
    /// PID of another live helper instance, or nil when this process is alone.
    ///
    /// Prefers NSRunningApplication (same bundle id, cheap and exact) and falls
    /// back to scanning the process table, which also catches a helper started
    /// directly from `.build/` rather than from the installed bundle.
    static func otherRunningHelperPid() -> Int32? {
        let me = ProcessInfo.processInfo.processIdentifier
        if let bundleId = Bundle.main.bundleIdentifier {
            let peers = NSRunningApplication.runningApplications(withBundleIdentifier: bundleId)
                .map(\.processIdentifier)
                .filter { $0 != me && $0 > 0 }
            if let first = peers.first {
                return first
            }
        }
        return scanProcessTable(excluding: me)
    }

    /// Match on the helper's executable path so the Tauri client and unrelated
    /// "Sandwalk" processes are not mistaken for a second helper.
    private static func scanProcessTable(excluding me: Int32) -> Int32? {
        let task = Process()
        task.executableURL = URL(fileURLWithPath: "/bin/ps")
        task.arguments = ["-Axo", "pid=,comm="]
        let pipe = Pipe()
        task.standardOutput = pipe
        task.standardError = FileHandle.nullDevice
        do {
            try task.run()
        } catch {
            return nil
        }
        let data = pipe.fileHandleForReading.readDataToEndOfFile()
        task.waitUntilExit()
        guard let text = String(data: data, encoding: .utf8) else { return nil }

        let marker = "Sandwalk Server.app/Contents/MacOS/Sandwalk"
        for line in text.split(whereSeparator: \.isNewline) {
            let trimmed = line.trimmingCharacters(in: .whitespaces)
            guard let spaceIndex = trimmed.firstIndex(of: " ") else { continue }
            guard let pid = Int32(trimmed[trimmed.startIndex..<spaceIndex]) else { continue }
            if pid == me || pid <= 0 { continue }
            let command = trimmed[trimmed.index(after: spaceIndex)...]
            if command.contains(marker) {
                return pid
            }
        }
        return nil
    }
}
