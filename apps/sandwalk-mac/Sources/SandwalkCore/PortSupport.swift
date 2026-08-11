import Darwin
import Foundation

/// Port / health helpers shared by API and web supervisors.
enum PortSupport {
    static func listenerPid(port: Int) -> Int32? {
        let task = Process()
        task.executableURL = URL(fileURLWithPath: "/usr/sbin/lsof")
        task.arguments = ["-nP", "-iTCP:\(port)", "-sTCP:LISTEN", "-t"]
        let pipe = Pipe()
        task.standardOutput = pipe
        task.standardError = FileHandle.nullDevice
        do {
            try task.run()
            task.waitUntilExit()
        } catch {
            return nil
        }
        guard task.terminationStatus == 0 else { return nil }
        let data = pipe.fileHandleForReading.readDataToEndOfFile()
        let text = String(data: data, encoding: .utf8)?
            .trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
        let first = text.split(whereSeparator: \.isNewline).first.flatMap { Int32($0) }
        return first
    }

    static func freePort(_ port: Int) {
        freePort(port, graceSteps: 10)
    }

    /// Terminate whoever listens on `port`.
    ///
    /// `graceSteps` × 0.3s of SIGTERM before SIGKILL. Instant kill -9 while
    /// `sandwalk serve` is mid-WAL write is a common cause of agent-server.db
    /// corruption and the menubar restart loop that follows, so prefer a grace
    /// window — but keep it short on the app-termination path, where AppKit will
    /// force-kill us and leave the agent orphaned.
    static func freePort(_ port: Int, graceSteps: Int) {
        let steps = max(1, graceSteps)
        let task = Process()
        task.executableURL = URL(fileURLWithPath: "/bin/zsh")
        task.arguments = [
            "-c",
            """
            pids=$(lsof -tiTCP:\(port) -sTCP:LISTEN 2>/dev/null)
            if [ -z "$pids" ]; then exit 0; fi
            kill -TERM $pids 2>/dev/null
            for i in $(seq 1 \(steps)); do
              sleep 0.3
              pids=$(lsof -tiTCP:\(port) -sTCP:LISTEN 2>/dev/null)
              [ -z "$pids" ] && exit 0
            done
            pids=$(lsof -tiTCP:\(port) -sTCP:LISTEN 2>/dev/null)
            [ -n "$pids" ] && kill -9 $pids 2>/dev/null
            true
            """,
        ]
        try? task.run()
        task.waitUntilExit()
    }

    static func probeHTTPSync(url: URL, accept: @escaping (Int) -> Bool, timeout: TimeInterval = 1.5) -> Bool {
        // Prefer curl: URLSession health checks can fail under App Transport Security
        // / local-network quirks in the menubar app, which then freePort()-kills a
        // healthy listener and leaves Sandwalk "partially running".
        if let code = curlStatus(url: url, timeout: timeout) {
            return accept(code)
        }

        let sem = DispatchSemaphore(value: 0)
        var ok = false
        var request = URLRequest(url: url)
        request.timeoutInterval = timeout
        request.httpMethod = "GET"
        let task = URLSession.shared.dataTask(with: request) { _, response, _ in
            let code = (response as? HTTPURLResponse)?.statusCode ?? 0
            ok = accept(code)
            sem.signal()
        }
        task.resume()
        _ = sem.wait(timeout: .now() + timeout + 0.5)
        return ok
    }

    /// Public wrapper for async health loops (API / web supervisors).
    static func curlStatusPublic(url: URL, timeout: TimeInterval) -> Int? {
        curlStatus(url: url, timeout: timeout)
    }

    private static func curlStatus(url: URL, timeout: TimeInterval) -> Int? {
        let task = Process()
        task.executableURL = URL(fileURLWithPath: "/usr/bin/curl")
        task.arguments = [
            "-s",
            "-o", "/dev/null",
            "-w", "%{http_code}",
            "--max-time", String(max(1, Int(timeout.rounded(.up)))),
            url.absoluteString,
        ]
        let pipe = Pipe()
        task.standardOutput = pipe
        task.standardError = FileHandle.nullDevice
        do {
            try task.run()
            task.waitUntilExit()
        } catch {
            return nil
        }
        guard task.terminationStatus == 0 else { return nil }
        let data = pipe.fileHandleForReading.readDataToEndOfFile()
        let text = String(data: data, encoding: .utf8)?
            .trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
        return Int(text)
    }

    static func killProcessTree(pid: Int32) {
        let task = Process()
        task.executableURL = URL(fileURLWithPath: "/bin/kill")
        task.arguments = ["-TERM", "-\(pid)"]
        try? task.run()
        task.waitUntilExit()
        kill(pid, SIGTERM)
    }

    /// Signal a child and every process in its group.
    ///
    /// `sandwalk serve` runs uvicorn, which forks a worker into the same group.
    /// Signaling the parent alone can leave that worker alive holding port 8787
    /// and the exclusive SQLite lock, so the next start fails with "database is
    /// locked by another process". Falls back to the bare pid when the process is
    /// not its own group leader.
    static func signalProcessGroup(pid: Int32, signal sig: Int32) {
        guard pid > 0 else { return }
        let group = getpgid(pid)
        if group > 0, group == pid {
            // Negative pid targets the whole group.
            _ = kill(-group, sig)
        }
        _ = kill(pid, sig)
    }
}
