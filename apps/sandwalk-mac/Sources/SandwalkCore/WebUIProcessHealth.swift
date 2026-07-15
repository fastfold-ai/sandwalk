import Foundation

extension WebUIProcess {
    var healthSleepInterval: TimeInterval {
        switch state {
        case .starting:
            return startupHealthInterval
        default:
            return TimeInterval(
                AppConfig.clampHealthCheckInterval(config.healthCheckIntervalSeconds)
            )
        }
    }

    func startHealthLoop() {
        cancelHealthLoop()
        healthTask = Task { @MainActor [weak self] in
            while !Task.isCancelled {
                guard let self else { return }
                await self.tickHealth()
                try? await Task.sleep(for: .seconds(self.healthSleepInterval))
            }
        }
    }

    func cancelHealthLoop() {
        healthTask?.cancel()
        healthTask = nil
    }

    @MainActor
    func tickHealth() async {
        switch state {
        case .starting, .running:
            break
        default:
            return
        }
        let ok = await probeHealth()
        if ok {
            consecutiveFailures = 0
            let pid = process?.processIdentifier ?? adoptedPid
                ?? PortSupport.listenerPid(port: config.dashboardPort) ?? 0
            if case .starting = state {
                update(.running(pid: pid))
            } else if case .running = state, process == nil, adoptedPid == nil, pid != 0 {
                adoptedPid = pid
                update(.running(pid: pid))
            }
        } else if process == nil, adoptedPid != nil || PortSupport.listenerPid(port: config.dashboardPort) == nil {
            consecutiveFailures += 1
            if consecutiveFailures >= 5 {
                adoptedPid = nil
                update(.failed(message: "Web UI stopped responding on \(config.webHealthURL.absoluteString)"))
                cancelHealthLoop()
            }
        } else if case .starting = state {
            consecutiveFailures += 1
            if consecutiveFailures >= maxHealthFailures {
                update(.failed(message: "Web UI health timed out on \(config.webHealthURL.absoluteString)"))
                expectingExit = true
                if let pid = process?.processIdentifier {
                    PortSupport.killProcessTree(pid: pid)
                }
            }
        }
    }

    func probeHealth() async -> Bool {
        var request = URLRequest(url: config.webHealthURL)
        request.timeoutInterval = 2
        request.httpMethod = "GET"
        do {
            let (_, response) = try await URLSession.shared.data(for: request)
            let code = (response as? HTTPURLResponse)?.statusCode ?? 0
            return (200..<500).contains(code)
        } catch {
            return false
        }
    }
}
