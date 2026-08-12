import Foundation
import Network
import Security

/// Local loopback control plane for the Tauri desktop UI (and other local clients).
/// Writes `~/Library/Application Support/Sandwalk/control.json` with host/port/token.
@MainActor
final class ControlPlane {
    static let preferredPort: UInt16 = 18_787

    private var listener: NWListener?
    private var token: String = ""
    private var port: UInt16 = preferredPort

    var controlURL: URL {
        URL(string: "http://127.0.0.1:\(port)")!
    }

    func start() {
        token = Self.makeToken()
        port = Self.preferredPort
        startListening(on: port)
    }

    func stop() {
        listener?.cancel()
        listener = nil
        try? FileManager.default.removeItem(at: Self.controlFileURL())
    }

    // MARK: - Paths

    static func supportDirectory() -> URL {
        let base = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask).first
            ?? URL(fileURLWithPath: NSHomeDirectory()).appendingPathComponent("Library/Application Support")
        return base.appendingPathComponent("Sandwalk", isDirectory: true)
    }

    static func controlFileURL() -> URL {
        supportDirectory().appendingPathComponent("control.json")
    }

    static func logsDirectory() -> URL {
        supportDirectory().appendingPathComponent("logs", isDirectory: true)
    }

    // MARK: - Listen

    private func startListening(on desired: UInt16) {
        let params = NWParameters.tcp
        params.allowLocalEndpointReuse = true
        do {
            let listener = try NWListener(using: params, on: NWEndpoint.Port(rawValue: desired)!)
            self.listener = listener
            listener.stateUpdateHandler = { [weak self] state in
                Task { @MainActor in
                    guard let self else { return }
                    switch state {
                    case .ready:
                        if let p = listener.port?.rawValue {
                            self.port = p
                        }
                        self.writeControlFile()
                        NSLog("Sandwalk: control plane listening on 127.0.0.1:\(self.port)")
                    case .failed(let error):
                        NSLog("Sandwalk: control plane failed — \(error.localizedDescription)")
                        if desired == Self.preferredPort {
                            // Fall back to an ephemeral port.
                            listener.cancel()
                            self.startListeningEphemeral()
                        }
                    default:
                        break
                    }
                }
            }
            listener.newConnectionHandler = { [weak self] connection in
                Task { @MainActor in
                    self?.accept(connection)
                }
            }
            listener.start(queue: .main)
        } catch {
            NSLog("Sandwalk: control plane bind failed — \(error.localizedDescription)")
            if desired == Self.preferredPort {
                startListeningEphemeral()
            }
        }
    }

    private func startListeningEphemeral() {
        let params = NWParameters.tcp
        params.allowLocalEndpointReuse = true
        do {
            let listener = try NWListener(using: params, on: .any)
            self.listener = listener
            listener.stateUpdateHandler = { [weak self] state in
                Task { @MainActor in
                    guard let self else { return }
                    if case .ready = state, let p = listener.port?.rawValue {
                        self.port = p
                        self.writeControlFile()
                        NSLog("Sandwalk: control plane listening on 127.0.0.1:\(self.port)")
                    }
                }
            }
            listener.newConnectionHandler = { [weak self] connection in
                Task { @MainActor in
                    self?.accept(connection)
                }
            }
            listener.start(queue: .main)
        } catch {
            NSLog("Sandwalk: control plane ephemeral bind failed — \(error.localizedDescription)")
        }
    }

    private func writeControlFile() {
        let dir = Self.supportDirectory()
        try? FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        let config = SandwalkRuntime.config
        let payload: [String: Any] = [
            "pid": ProcessInfo.processInfo.processIdentifier,
            "host": "127.0.0.1",
            "port": Int(port),
            "token": token,
            "api_base": config.apiBaseURL.absoluteString,
            "dashboard_url": config.dashboardURL.absoluteString,
            "dashboard_home_url": config.dashboardHomeURL.absoluteString,
        ]
        guard let data = try? JSONSerialization.data(withJSONObject: payload, options: [.prettyPrinted, .sortedKeys])
        else { return }
        let url = Self.controlFileURL()
        try? data.write(to: url, options: .atomic)
        try? FileManager.default.setAttributes(
            [.posixPermissions: 0o600],
            ofItemAtPath: url.path
        )
    }

    private static func makeToken() -> String {
        var bytes = [UInt8](repeating: 0, count: 32)
        _ = SecRandomCopyBytes(kSecRandomDefault, bytes.count, &bytes)
        return Data(bytes).base64EncodedString()
            .replacingOccurrences(of: "+", with: "-")
            .replacingOccurrences(of: "/", with: "_")
            .replacingOccurrences(of: "=", with: "")
    }

    // MARK: - HTTP (minimal)

    private func accept(_ connection: NWConnection) {
        connection.start(queue: .main)
        receive(on: connection, buffer: Data())
    }

    private func receive(on connection: NWConnection, buffer: Data) {
        connection.receive(minimumIncompleteLength: 1, maximumLength: 64 * 1024) { [weak self] data, _, isComplete, error in
            Task { @MainActor in
                guard let self else { return }
                if let error {
                    NSLog("Sandwalk: control connection error — \(error.localizedDescription)")
                    connection.cancel()
                    return
                }
                var next = buffer
                if let data { next.append(data) }
                if let range = next.range(of: Data("\r\n\r\n".utf8)) {
                    let headerData = next.subdata(in: next.startIndex..<range.lowerBound)
                    let bodyStart = range.upperBound
                    let headers = String(data: headerData, encoding: .utf8) ?? ""
                    let contentLength = Self.parseContentLength(headers)
                    let body = next.subdata(in: bodyStart..<next.endIndex)
                    if body.count < contentLength {
                        self.receive(on: connection, buffer: next)
                        return
                    }
                    let requestBody = body.prefix(contentLength)
                    self.handleRequest(headers: headers, body: Data(requestBody), connection: connection)
                    return
                }
                if isComplete {
                    connection.cancel()
                    return
                }
                self.receive(on: connection, buffer: next)
            }
        }
    }

    private static func parseContentLength(_ headers: String) -> Int {
        for line in headers.split(separator: "\r\n") {
            let parts = line.split(separator: ":", maxSplits: 1).map {
                $0.trimmingCharacters(in: .whitespaces)
            }
            if parts.count == 2, parts[0].lowercased() == "content-length" {
                return Int(parts[1]) ?? 0
            }
        }
        return 0
    }

    private func handleRequest(headers: String, body: Data, connection: NWConnection) {
        let lines = headers.split(separator: "\r\n", omittingEmptySubsequences: false)
        guard let requestLine = lines.first else {
            respond(connection, status: 400, json: ["error": "bad request"])
            return
        }
        let parts = requestLine.split(separator: " ")
        guard parts.count >= 2 else {
            respond(connection, status: 400, json: ["error": "bad request"])
            return
        }
        let method = String(parts[0]).uppercased()
        let pathQuery = String(parts[1])
        let path = pathQuery.split(separator: "?", maxSplits: 1).first.map(String.init) ?? pathQuery
        let query = pathQuery.split(separator: "?", maxSplits: 1).count > 1
            ? String(pathQuery.split(separator: "?", maxSplits: 1)[1])
            : ""

        guard authorized(headers: headers) else {
            respond(connection, status: 401, json: ["error": "unauthorized"])
            return
        }

        Task { @MainActor in
            let result = await self.dispatch(method: method, path: path, query: query, body: body)
            self.respond(connection, status: result.status, json: result.json)
        }
    }

    private func authorized(headers: String) -> Bool {
        for line in headers.split(separator: "\r\n") {
            let parts = line.split(separator: ":", maxSplits: 1).map {
                $0.trimmingCharacters(in: .whitespaces)
            }
            guard parts.count == 2, parts[0].lowercased() == "authorization" else { continue }
            let value = parts[1]
            if value.hasPrefix("Bearer ") {
                return String(value.dropFirst("Bearer ".count)) == token
            }
            if value == token { return true }
        }
        // Also accept `X-Sandwalk-Token`
        for line in headers.split(separator: "\r\n") {
            let parts = line.split(separator: ":", maxSplits: 1).map {
                $0.trimmingCharacters(in: .whitespaces)
            }
            if parts.count == 2, parts[0].lowercased() == "x-sandwalk-token" {
                return parts[1] == token
            }
        }
        return false
    }

    private struct DispatchResult {
        var status: Int
        var json: [String: Any]
    }

    private func dispatch(method: String, path: String, query: String, body: Data) async -> DispatchResult {
        switch (method, path) {
        case ("GET", "/v1/control/status"):
            return .init(status: 200, json: statusPayload())
        case ("POST", "/v1/control/start"):
            do {
                try SandwalkRuntime.supervisor?.startAll()
                return .init(status: 200, json: statusPayload())
            } catch {
                return .init(status: 500, json: ["error": error.localizedDescription])
            }
        case ("POST", "/v1/control/stop"):
            await SandwalkRuntime.supervisor?.stopAll()
            return .init(status: 200, json: statusPayload())
        case ("POST", "/v1/control/restart"):
            do {
                try await SandwalkRuntime.supervisor?.restartAll()
                writeControlFile()
                return .init(status: 200, json: statusPayload())
            } catch {
                return .init(status: 500, json: ["error": error.localizedDescription])
            }
        case ("GET", "/v1/control/settings"):
            return .init(status: 200, json: settingsPayload())
        case ("PUT", "/v1/control/settings"), ("PATCH", "/v1/control/settings"):
            return await applySettings(body: body)
        case ("GET", "/v1/control/auth"):
            return .init(status: 200, json: authPayload())
        case ("PUT", "/v1/control/auth"), ("PATCH", "/v1/control/auth"):
            return await applyAuth(body: body)
        case ("GET", "/v1/control/desktop"):
            return .init(status: 200, json: desktopPayload())
        case ("PUT", "/v1/control/desktop"), ("PATCH", "/v1/control/desktop"):
            return applyDesktop(body: body)
        case ("GET", "/v1/control/logs"):
            return logsPayload(query: query)
        case ("POST", "/v1/control/rebuild-dashboard"):
            do {
                try await SandwalkRuntime.supervisor?.rebuildProductionDashboard()
                return .init(status: 200, json: ["ok": true])
            } catch {
                return .init(status: 500, json: ["error": error.localizedDescription])
            }
        case ("GET", "/v1/control/cli-path"):
            return .init(status: 200, json: CliPathInstaller.status())
        case ("POST", "/v1/control/cli-path"):
            return installCliPath(body: body)
        default:
            return .init(status: 404, json: ["error": "not found"])
        }
    }

    private func installCliPath(body: Data) -> DispatchResult {
        var force = false
        if let obj = try? JSONSerialization.jsonObject(with: body) as? [String: Any] {
            if let flag = obj["force"] as? Bool {
                force = flag
            } else if let flag = obj["force"] as? NSNumber {
                force = flag.boolValue
            }
        }
        let outcome = CliPathInstaller.ensureInstalled(force: force)
        var json = CliPathInstaller.outcomePayload(outcome)
        if case .failed(let message) = outcome {
            json["error"] = message
            return .init(status: 500, json: json)
        }
        return .init(status: 200, json: json)
    }

    private func statusPayload() -> [String: Any] {
        let supervisor = SandwalkRuntime.supervisor
        let config = SandwalkRuntime.config
        let overall = supervisor?.overall.label ?? "Unknown"
        let state: String = {
            guard let overall = supervisor?.overall else { return "unknown" }
            switch overall {
            case .stopped: return "stopped"
            case .starting: return "starting"
            case .running: return "running"
            case .partial: return "partial"
            case .stopping: return "stopping"
            case .failed: return "failed"
            }
        }()
        return [
            "state": state,
            "label": overall,
            "api_base": config.apiBaseURL.absoluteString,
            "dashboard_url": config.dashboardURL.absoluteString,
            "dashboard_home_url": config.dashboardHomeURL.absoluteString,
            "bind_host": config.bindHost,
            "port": config.port,
            "dashboard_host": config.dashboardHost,
            "dashboard_port": config.dashboardPort,
            "dashboard_serve_mode": config.dashboardServeMode.rawValue,
            "auto_start": config.autoStartOnLaunch,
            "menubar_running": true,
        ]
    }

    private func settingsPayload() -> [String: Any] {
        let config = SandwalkRuntime.config
        return [
            "bind_host": config.bindHost,
            "port": config.port,
            "dashboard_host": config.dashboardHost,
            "dashboard_port": config.dashboardPort,
            "auto_start": config.autoStartOnLaunch,
            "health_check_interval_seconds": config.healthCheckIntervalSeconds,
            "dashboard_serve_mode": config.dashboardServeMode.rawValue,
            "db_auto_heal": config.dbAutoHeal,
            "keep_menubar_on_cmdq": config.keepMenubarOnCmdQ,
        ]
    }

    private func applySettings(body: Data) async -> DispatchResult {
        guard
            let json = try? JSONSerialization.jsonObject(with: body) as? [String: Any],
            let supervisor = SandwalkRuntime.supervisor
        else {
            return .init(status: 400, json: ["error": "invalid json"])
        }
        var next = supervisor.config
        if let host = json["bind_host"] as? String { next.bindHost = host }
        if let port = json["port"] as? Int { next.port = port }
        if let host = json["dashboard_host"] as? String { next.dashboardHost = host }
        if let port = json["dashboard_port"] as? Int { next.dashboardPort = port }
        if let auto = json["auto_start"] as? Bool { next.autoStartOnLaunch = auto }
        if let interval = json["health_check_interval_seconds"] as? Int {
            next.healthCheckIntervalSeconds = AppConfig.clampHealthCheckInterval(interval)
        }
        if let mode = json["dashboard_serve_mode"] as? String {
            let lower = mode.lowercased()
            if lower == "development" || lower == "dev" {
                next.dashboardServeMode = .development
            } else if lower == "production" || lower == "prod" {
                next.dashboardServeMode = .production
            }
        }
        if let heal = json["db_auto_heal"] as? Bool { next.dbAutoHeal = heal }
        if let keep = json["keep_menubar_on_cmdq"] as? Bool { next.keepMenubarOnCmdQ = keep }

        let networkChanged =
            next.bindHost != supervisor.config.bindHost
            || next.port != supervisor.config.port
            || next.dashboardHost != supervisor.config.dashboardHost
            || next.dashboardPort != supervisor.config.dashboardPort
            || next.dashboardServeMode != supervisor.config.dashboardServeMode
            || next.dbAutoHeal != supervisor.config.dbAutoHeal

        // `sandwalk serve` exits(2) on a non-loopback bind without an enabled API
        // key. Reject here so a remote toggle cannot take the agent down.
        if next.apiExposesRemote {
            let auth = AuthSettingsStore.load()
            if !(auth.authEnabled && auth.apiKeyConfigured) {
                return .init(
                    status: 400,
                    json: [
                        "error": "Remote access requires an API key. Generate one and "
                            + "enable auth (Security / `sandwalk auth enable`) before "
                            + "binding to 0.0.0.0.",
                        "needs_api_key": true,
                    ]
                )
            }
        }

        do {
            if networkChanged {
                try await supervisor.applyNetworkConfig(next)
            } else {
                try supervisor.applyGeneralPreferences(next)
                if next.healthCheckIntervalSeconds != supervisor.config.healthCheckIntervalSeconds {
                    try supervisor.applyHealthCheckInterval(next.healthCheckIntervalSeconds)
                }
            }
            writeControlFile()
            return .init(status: 200, json: settingsPayload())
        } catch {
            return .init(status: 500, json: ["error": error.localizedDescription])
        }
    }

    private func authPayload() -> [String: Any] {
        let auth = AuthSettingsStore.load()
        return [
            "auth_enabled": auth.authEnabled,
            "api_key_configured": auth.apiKeyConfigured,
            "api_key": auth.apiKey,
        ]
    }

    private func applyAuth(body: Data) async -> DispatchResult {
        guard let json = try? JSONSerialization.jsonObject(with: body) as? [String: Any] else {
            return .init(status: 400, json: ["error": "invalid json"])
        }
        var auth = AuthSettingsStore.load()
        if let generate = json["generate"] as? Bool, generate {
            auth.apiKey = AuthSettingsStore.generateAPIKey()
        }
        if let key = json["api_key"] as? String {
            auth.apiKey = key
        }
        if let enabled = json["auth_enabled"] as? Bool {
            auth.authEnabled = enabled
        }
        do {
            try AuthSettingsStore.save(auth)
            if SandwalkRuntime.supervisor?.overall.isLive == true {
                try await SandwalkRuntime.supervisor?.restartAll()
            }
            return .init(status: 200, json: authPayload())
        } catch {
            return .init(status: 500, json: ["error": error.localizedDescription])
        }
    }

    private func desktopPayload() -> [String: Any] {
        let config = SandwalkRuntime.config
        return [
            "open_at_login": LoginItemSupport.isEnabled,
            "open_at_login_status": LoginItemSupport.statusDescription,
            "auto_start": config.autoStartOnLaunch,
            "keep_menubar_on_cmdq": config.keepMenubarOnCmdQ,
        ]
    }

    private func applyDesktop(body: Data) -> DispatchResult {
        guard
            let json = try? JSONSerialization.jsonObject(with: body) as? [String: Any],
            let supervisor = SandwalkRuntime.supervisor
        else {
            return .init(status: 400, json: ["error": "invalid json"])
        }
        if let login = json["open_at_login"] as? Bool {
            do {
                try LoginItemSupport.setEnabled(login)
            } catch {
                return .init(status: 500, json: ["error": error.localizedDescription])
            }
        }
        var next = supervisor.config
        if let auto = json["auto_start"] as? Bool { next.autoStartOnLaunch = auto }
        if let keep = json["keep_menubar_on_cmdq"] as? Bool { next.keepMenubarOnCmdQ = keep }
        do {
            try supervisor.applyGeneralPreferences(next)
            return .init(status: 200, json: desktopPayload())
        } catch {
            return .init(status: 500, json: ["error": error.localizedDescription])
        }
    }

    private func logsPayload(query: String) -> DispatchResult {
        var name = "server.log"
        var lines = 200
        for part in query.split(separator: "&") {
            let kv = part.split(separator: "=", maxSplits: 1)
            guard kv.count == 2 else { continue }
            let key = String(kv[0])
            let value = String(kv[1]).removingPercentEncoding ?? String(kv[1])
            if key == "name" || key == "file" {
                name = value
            }
            if key == "lines", let n = Int(value) {
                lines = max(1, min(n, 10_000))
            }
        }
        let allowed = Set(["server.log", "web.log"])
        guard allowed.contains(name) else {
            return .init(status: 400, json: ["error": "invalid log name"])
        }
        let url = Self.logsDirectory().appendingPathComponent(name)
        guard let data = try? Data(contentsOf: url), let text = String(data: data, encoding: .utf8) else {
            return .init(status: 200, json: [
                "name": name,
                "text": "",
                "total_lines": 0,
                "path": url.path,
            ])
        }
        let all = text.split(separator: "\n", omittingEmptySubsequences: false)
        let slice = all.suffix(lines)
        return .init(status: 200, json: [
            "name": name,
            "text": slice.joined(separator: "\n"),
            "total_lines": all.count,
            "path": url.path,
        ])
    }

    private func respond(_ connection: NWConnection, status: Int, json: [String: Any]) {
        let body = (try? JSONSerialization.data(withJSONObject: json)) ?? Data("{}".utf8)
        let reason: String = {
            switch status {
            case 200: return "OK"
            case 400: return "Bad Request"
            case 401: return "Unauthorized"
            case 404: return "Not Found"
            default: return "Error"
            }
        }()
        var response = "HTTP/1.1 \(status) \(reason)\r\n"
        response += "Content-Type: application/json\r\n"
        response += "Content-Length: \(body.count)\r\n"
        response += "Connection: close\r\n"
        response += "\r\n"
        var payload = Data(response.utf8)
        payload.append(body)
        connection.send(content: payload, completion: .contentProcessed { _ in
            connection.cancel()
        })
    }
}
