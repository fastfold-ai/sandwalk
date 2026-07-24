import AppKit
import SwiftUI

extension StatusSettingsView {
    var heroCard: some View {
        HStack(spacing: 16) {
            Image(nsImage: SandwalkIcon.menubarMark(pointSize: 52))
                .resizable()
                .interpolation(.high)
                .renderingMode(.template)
                .foregroundStyle(theme.text)
                .frame(width: 52, height: 52)

            VStack(alignment: .leading, spacing: 4) {
                HStack(spacing: 10) {
                    Text(heroTitle)
                        .font(.sandwalk(18, weight: .semibold))
                        .foregroundStyle(theme.text)
                    SettingsStatusPill(status: pillStatus)
                }
                Text(subtitle)
                    .font(.sandwalk(11.5))
                    .foregroundStyle(theme.textSecondary)
            }

            Spacer(minLength: 12)
            actionButtons
        }
        .padding(18)
        .background(theme.groupBg)
        .clipShape(RoundedRectangle(cornerRadius: 12, style: .continuous))
        .padding(.horizontal, 14)
        .padding(.bottom, 14)
    }

    var heroTitle: String {
        if let version = report?.version, !version.isEmpty {
            return "Sandwalk \(version)"
        }
        return "Sandwalk"
    }

    @ViewBuilder
    var actionButtons: some View {
        switch overall {
        case .running, .partial, .starting:
            HStack(spacing: 6) {
                Button {
                    Task { await restart() }
                } label: {
                    Label("Restart", systemImage: "arrow.clockwise")
                        .labelStyle(.titleAndIcon)
                }
                .buttonStyle(.sandwalk(.normal))
                .disabled(busy)

                Button {
                    Task { await stop() }
                } label: {
                    Label("Stop", systemImage: "stop.fill")
                        .labelStyle(.titleAndIcon)
                }
                .buttonStyle(.sandwalk(.destructive))
                .disabled(busy)
            }

        case .stopping:
            Button("Working…") {}
                .buttonStyle(.sandwalk(.normal))
                .disabled(true)

        case .stopped, .failed:
            Button {
                Task { await start() }
            } label: {
                Label("Start Sandwalk", systemImage: "play.fill")
                    .labelStyle(.titleAndIcon)
            }
            .buttonStyle(.sandwalk(.primary))
            .disabled(busy)
        }
    }

    var pillStatus: SettingsStatusPill.Status {
        switch overall {
        case .running: return .running
        case .starting: return .starting
        case .stopping: return .stopping
        case .stopped: return .stopped
        case .failed: return .error
        case .partial: return .partial
        }
    }

    var subtitle: String {
        if let report, apiLikelyUp {
            if let message = report.message, !message.isEmpty {
                return message
            }
            if let host = report.host, let port = report.port {
                return "Listening on \(host):\(port)"
            }
        }
        switch overall {
        case .running:
            return "API \(config.connectableHost):\(config.port) · UI :\(config.dashboardPort)"
        case .partial(let api, let web):
            return "API \(api ? "up" : "down") · Web \(web ? "up" : "down")"
        case .failed(let message):
            return message
        case .starting:
            return "Starting API and dashboard…"
        case .stopping:
            return "Stopping…"
        case .stopped:
            return "Stopped — start from here or the menu bar"
        }
    }

    @MainActor
    func applyHealthInterval(_ seconds: Int) async {
        let clamped = AppConfig.clampHealthCheckInterval(seconds)
        guard clamped != config.healthCheckIntervalSeconds else { return }
        do {
            if let supervisor = SandwalkRuntime.supervisor {
                try supervisor.applyHealthCheckInterval(clamped)
                config = supervisor.config
            } else {
                var next = config
                next.healthCheckIntervalSeconds = clamped
                try next.saveNetworkSettings()
                config = next
            }
            healthIntervalDraft = clamped
            statusMessage = "Health check interval set to \(Self.labelForHealthInterval(clamped))."
            errorMessage = nil
        } catch {
            errorMessage = error.localizedDescription
            healthIntervalDraft = config.healthCheckIntervalSeconds
        }
    }

    @MainActor
    func loadReport() async {
        guard apiLikelyUp else {
            report = nil
            return
        }
        do {
            report = try await SandwalkAPIClient.serverStatus()
            if errorMessage?.contains("/v1/status") == true || errorMessage?.hasPrefix("HTTP") == true {
                errorMessage = nil
            }
        } catch {
            // Keep control surface usable even if metrics fail.
            if report == nil {
                errorMessage = error.localizedDescription
            }
        }
    }

    @MainActor
    func clearCache() async {
        clearing = true
        statusMessage = nil
        defer { clearing = false }
        do {
            _ = try await SandwalkAPIClient.clearRuntimeCache()
            await loadReport()
            statusMessage = "Runtime cache cleared."
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    @MainActor
    func start() async {
        guard let supervisor = SandwalkRuntime.supervisor else {
            errorMessage = "Supervisor unavailable."
            return
        }
        busy = true
        errorMessage = nil
        defer { busy = false }
        do {
            try supervisor.startAll()
        } catch {
            errorMessage = error.localizedDescription
        }
        refresh()
        // Give serve a moment before polling status.
        try? await Task.sleep(nanoseconds: 800_000_000)
        await loadReport()
    }

    @MainActor
    func stop() async {
        busy = true
        defer { busy = false }
        await SandwalkRuntime.supervisor?.stopAll()
        refresh()
        report = nil
    }

    @MainActor
    func restart() async {
        guard let supervisor = SandwalkRuntime.supervisor else { return }
        busy = true
        errorMessage = nil
        defer { busy = false }
        do {
            try await supervisor.restartAll()
        } catch {
            errorMessage = error.localizedDescription
        }
        refresh()
        try? await Task.sleep(nanoseconds: 800_000_000)
        await loadReport()
    }
}
