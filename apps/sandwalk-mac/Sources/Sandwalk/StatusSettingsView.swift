import AppKit
import SwiftUI

/// Status pane — hero card with Running pill + Start / Restart / Stop (oMLX style).
struct StatusSettingsView: View {
    @State private var overall: SandwalkSupervisor.OverallState = .stopped
    @State private var config = AppConfig.load()
    @State private var busy = false
    @State private var errorMessage: String?

    @Environment(\.sandwalkTheme) private var theme

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            heroCard

            SettingsSectionHeader("ENDPOINTS", subtitle: "Local URLs for the supervised API and dashboard.")
            SettingsListGroup {
                SettingsRow(
                    label: "Agent API",
                    sublabel: config.apiBaseURL.absoluteString
                ) {
                    Button {
                        NSWorkspace.shared.open(config.healthURL)
                    } label: {
                        Image(systemName: "arrow.up.right.square")
                    }
                    .buttonStyle(.sandwalk(.normal))
                }
                SettingsRow(
                    label: "Web dashboard",
                    sublabel: config.dashboardHomeURL.absoluteString,
                    isLast: true
                ) {
                    Button {
                        NSWorkspace.shared.open(config.dashboardHomeURL)
                    } label: {
                        Image(systemName: "arrow.up.right.square")
                    }
                    .buttonStyle(.sandwalk(.normal))
                }
            }

            if let errorMessage {
                Text(errorMessage)
                    .font(.sandwalk(11.5))
                    .foregroundStyle(theme.redDot)
                    .padding(.horizontal, 18)
                    .padding(.top, 8)
            }
        }
        .padding(.top, 8)
        .onAppear(perform: refresh)
        .onReceive(NotificationCenter.default.publisher(for: SandwalkSupervisor.stateDidChangeNotification)) { _ in
            refresh()
        }
        .onReceive(NotificationCenter.default.publisher(for: SandwalkSupervisor.configDidChangeNotification)) { _ in
            refresh()
        }
    }

    private var heroCard: some View {
        HStack(spacing: 16) {
            Image(nsImage: SandwalkIcon.menubarMark(pointSize: 52))
                .resizable()
                .interpolation(.high)
                .renderingMode(.template)
                .foregroundStyle(theme.text)
                .frame(width: 52, height: 52)

            VStack(alignment: .leading, spacing: 4) {
                HStack(spacing: 10) {
                    Text("Sandwalk")
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

    @ViewBuilder
    private var actionButtons: some View {
        switch overall {
        case .running, .partial:
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

        case .starting, .stopping:
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

    private var pillStatus: SettingsStatusPill.Status {
        switch overall {
        case .running: return .running
        case .starting: return .starting
        case .stopping: return .stopping
        case .stopped: return .stopped
        case .failed: return .error
        case .partial: return .partial
        }
    }

    private var subtitle: String {
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

    private func refresh() {
        overall = SandwalkRuntime.supervisor?.overall ?? .stopped
        config = SandwalkRuntime.config
    }

    @MainActor
    private func start() async {
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
    }

    @MainActor
    private func stop() async {
        busy = true
        defer { busy = false }
        await SandwalkRuntime.supervisor?.stopAll()
        refresh()
    }

    @MainActor
    private func restart() async {
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
    }
}
