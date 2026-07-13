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

    static func killProcessTree(pid: Int32) {
        let task = Process()
        task.executableURL = URL(fileURLWithPath: "/bin/kill")
        task.arguments = ["-TERM", "-\(pid)"]
        try? task.run()
        task.waitUntilExit()
        kill(pid, SIGTERM)
    }
}
