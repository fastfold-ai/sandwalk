import Foundation

extension ServerProcess {
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

    func cancelRecovery() {
        recoveryTask?.cancel()
        recoveryTask = nil
    }

    /// After an unexpected API death, adopt a healthy listener on our port or respawn.
    func scheduleRecovery(reason: String) {
        if suppressAutoRecovery {
            NSLog("Sandwalk: API recovery skipped (fatal startup) (%@)", reason)
            return
        }
        cancelRecovery()
        recoveryTask = Task { @MainActor [weak self] in
            guard let self else { return }
            // Brief pause so a replacement `sandwalk serve` can bind first.
            try? await Task.sleep(for: .milliseconds(900))
            guard !Task.isCancelled else { return }
            if self.suppressAutoRecovery { return }
            switch self.state {
            case .failed, .stopped:
                break
            default:
                return
            }
            if self.tryAdoptHealthyListener() {
                self.consecutiveRecoveries = 0
                self.consecutiveStartupFailures = 0
                self.everHealthy = true
                NSLog("Sandwalk: API recovered by adopting listener (%@)", reason)
                return
            }
            if self.consecutiveRecoveries >= self.maxAutoRecoveries {
                self.suppressAutoRecovery = true
                NSLog("Sandwalk: API recovery gave up after %d attempts (%@)", self.maxAutoRecoveries, reason)
                return
            }
            // Don't thrash forever on cold-start failures that never become healthy.
            if !self.everHealthy, self.consecutiveStartupFailures > self.maxStartupRecoveries {
                self.suppressAutoRecovery = true
                NSLog(
                    "Sandwalk: API recovery stopped after %d startup failures (%@)",
                    self.consecutiveStartupFailures,
                    reason
                )
                return
            }
            self.consecutiveRecoveries += 1
            do {
                try self.doStart()
                NSLog("Sandwalk: API respawned after %@ (attempt %d)", reason, self.consecutiveRecoveries)
            } catch {
                NSLog("Sandwalk: API respawn failed (%@): %@", reason, error.localizedDescription)
                // Try again with backoff.
                try? await Task.sleep(for: .seconds(2))
                guard !Task.isCancelled else { return }
                self.scheduleRecovery(reason: "retry")
            }
        }
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
            consecutiveRecoveries = 0
            consecutiveStartupFailures = 0
            everHealthy = true
            let pid = process?.processIdentifier ?? adoptedPid
                ?? PortSupport.listenerPid(port: config.port) ?? 0
            if case .starting = state {
                update(.running(pid: pid))
            } else if case .running = state, process == nil, adoptedPid == nil, pid != 0 {
                adoptedPid = pid
                update(.running(pid: pid))
            } else if case .running = state, let adopted = adoptedPid, adopted != 0 {
                // Child was replaced out-of-band — track the live listener.
                if let live = PortSupport.listenerPid(port: config.port), live != adopted {
                    adoptedPid = live
                    update(.running(pid: live))
                }
            }
        } else {
            consecutiveFailures += 1
            if process == nil, adoptedPid != nil || PortSupport.listenerPid(port: config.port) == nil {
                // Adopted listener disappeared.
                if consecutiveFailures >= maxHealthFailures {
                    adoptedPid = nil
                    update(.failed(message: "API stopped responding on \(config.healthURL.absoluteString)"))
                    cancelHealthLoop()
                    if !suppressAutoRecovery {
                        scheduleRecovery(reason: "health-lost")
                    }
                }
                return
            }
            // Supervised child still listed as running but health is down —
            // if the PID is gone, recover instead of waiting forever.
            if let proc = process, !proc.isRunning {
                process = nil
                update(.failed(message: "API process ended while unhealthy"))
                cancelHealthLoop()
                if !suppressAutoRecovery {
                    scheduleRecovery(reason: "stale-child")
                }
                return
            }
            if case .starting = state, consecutiveFailures >= maxHealthFailures {
                // Keep waiting a bit longer during cold start — uv can be slow.
                if consecutiveFailures >= maxHealthFailures * 3 {
                    update(.failed(message: "Health check timed out on \(config.healthURL.absoluteString)"))
                    expectingExit = true
                    process?.terminate()
                    if !suppressAutoRecovery {
                        scheduleRecovery(reason: "start-timeout")
                    }
                }
            }
        }
    }

    func probeHealth() async -> Bool {
        if let code = await Task.detached(priority: .utility, operation: {
            PortSupport.curlStatusPublic(url: self.config.healthURL, timeout: 2)
        }).value {
            return code == 200
        }
        var request = URLRequest(url: config.healthURL)
        request.timeoutInterval = 2
        request.httpMethod = "GET"
        do {
            let (_, response) = try await URLSession.shared.data(for: request)
            return (response as? HTTPURLResponse)?.statusCode == 200
        } catch {
            return false
        }
    }
}
