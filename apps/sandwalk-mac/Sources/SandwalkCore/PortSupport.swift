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
        let task = Process()
        task.executableURL = URL(fileURLWithPath: "/bin/zsh")
        task.arguments = [
            "-c",
            "pids=$(lsof -tiTCP:\(port) -sTCP:LISTEN 2>/dev/null); [ -n \"$pids\" ] && kill $pids 2>/dev/null; sleep 0.2; pids=$(lsof -tiTCP:\(port) -sTCP:LISTEN 2>/dev/null); [ -n \"$pids\" ] && kill -9 $pids 2>/dev/null; true",
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
}
