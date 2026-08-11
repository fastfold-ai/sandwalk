import Foundation

extension SandwalkSupervisor {
    /// Web-up / API-down is the common "tools killed sandwalk serve" failure mode.
    /// Kick API start (adopt-or-respawn) so the menubar doesn't stay orange forever.
    func recoverPartialAPIIfNeeded() {
        guard case .partial(let apiUp, let webUp) = overall, !apiUp, webUp else {
            partialRecoveryTask?.cancel()
            partialRecoveryTask = nil
            if case .running = overall {
                partialRecoveryAttempts = 0
            }
            return
        }
        // Fatal startup (corrupt DB, etc.) — don't keep poking Start.
        if api.suppressAutoRecovery {
            return
        }
        guard partialRecoveryTask == nil else { return }
        guard partialRecoveryAttempts < maxPartialRecoveries else {
            NSLog(
                "Sandwalk: giving up partial API recovery after %d attempts — check server.log",
                maxPartialRecoveries
            )
            return
        }
        partialRecoveryTask = Task { @MainActor [weak self] in
            guard let self else { return }
            defer { self.partialRecoveryTask = nil }
            let attempt = self.partialRecoveryAttempts + 1
            let delayMs = 700 * attempt
            try? await Task.sleep(for: .milliseconds(delayMs))
            guard !Task.isCancelled else { return }
            guard case .partial(let stillApi, let stillWeb) = self.overall, !stillApi, stillWeb else {
                return
            }
            self.partialRecoveryAttempts = attempt
            do {
                _ = try self.api.start()
                NSLog("Sandwalk: recovered API from partial state (attempt %d)", attempt)
            } catch {
                NSLog(
                    "Sandwalk: partial API recovery failed (attempt %d) — %@",
                    attempt,
                    error.localizedDescription
                )
            }
            self.recompute()
        }
    }
}
