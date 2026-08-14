import AppKit
import SwiftUI

/// Status pane — control hero + live `/v1/status` system & cache (matches web Status).
struct StatusSettingsView: View {
    @State var overall: SandwalkSupervisor.OverallState = .stopped
    @State var config = AppConfig.load()
    @State var report: ServerStatusReportDTO?
    @State var hardware = MacHardwareInfo.current()
    @State var busy = false
    @State var clearing = false
    @State var confirmClear = false
    @State var errorMessage: String?
    @State var statusMessage: String?
    @State private var hardwareTimer: Timer?
    @State var healthIntervalDraft = AppConfig.defaultHealthCheckIntervalSeconds

    @Environment(\.sandwalkTheme) var theme

    static let healthIntervalChoices = [15, 30, 60, 120, 180, 300]

    private var healthIntervalSublabel: String {
        "Default 1 min · applies without restart"
    }

    static func labelForHealthInterval(_ seconds: Int) -> String {
        if seconds < 60 { return "\(seconds)s" }
        if seconds % 60 == 0 {
            let minutes = seconds / 60
            return minutes == 1 ? "1 min" : "\(minutes) min"
        }
        return "\(seconds)s"
    }

    var apiLikelyUp: Bool {
        switch overall {
        case .running:
            return true
        case .partial(let api, _):
            // Partial with API down must not pretend the API is up — that leaves
            // Status stuck spinning on /v1/status and re-fetching on every
            // supervisor notify (crash-loop feedback).
            return api
        default:
            return false
        }
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            heroCard

            systemSection(report: report, hardware: hardware)

            if let report {
                cacheSection(report)
            } else if apiLikelyUp {
                SettingsSectionHeader("RUNTIME CACHE", subtitle: "Loading…")
                SettingsListGroup {
                    SettingsRow(label: "Fetching /v1/status…", isLast: true) {
                        ProgressView()
                            .controlSize(.small)
                    }
                }
            }

            SettingsSectionHeader(
                "HEALTH CHECKS",
                subtitle: "Probe interval while services are running. Start still uses a fast probe."
            )
            SettingsListGroup {
                SettingsRow(
                    label: "Interval",
                    sublabel: healthIntervalSublabel,
                    isLast: true
                ) {
                    Picker("", selection: $healthIntervalDraft) {
                        ForEach(Self.healthIntervalChoices, id: \.self) { seconds in
                            Text(Self.labelForHealthInterval(seconds)).tag(seconds)
                        }
                    }
                    .labelsHidden()
                    .frame(minWidth: 110)
                    .onChange(of: healthIntervalDraft) { _, newValue in
                        Task { await applyHealthInterval(newValue) }
                    }
                }
            }

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

            if let statusMessage {
                Text(statusMessage)
                    .font(.sandwalk(11.5))
                    .foregroundStyle(theme.textSecondary)
                    .padding(.horizontal, 18)
                    .padding(.top, 8)
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
        .onAppear {
            refresh()
            hardware = MacHardwareInfo.current()
            startHardwarePolling()
            Task { await loadReport() }
        }
        .onDisappear {
            hardwareTimer?.invalidate()
            hardwareTimer = nil
        }
        .onReceive(NotificationCenter.default.publisher(for: SandwalkSupervisor.stateDidChangeNotification)) { _ in
            refresh()
            Task { await loadReport() }
        }
        .onReceive(NotificationCenter.default.publisher(for: SandwalkSupervisor.configDidChangeNotification)) { _ in
            refresh()
            Task { await loadReport() }
        }
        .confirmationDialog(
            "Clear runtime cache?",
            isPresented: $confirmClear,
            titleVisibility: .visible
        ) {
            Button("Clear cache", role: .destructive) {
                Task { await clearCache() }
            }
            Button("Cancel", role: .cancel) {}
        } message: {
            Text("Clears temporary runtime cache files. Datasets and sessions are not deleted.")
        }
    }

    private func startHardwarePolling() {
        hardwareTimer?.invalidate()
        hardwareTimer = Timer.scheduledTimer(withTimeInterval: 2.0, repeats: true) { _ in
            Task { @MainActor in
                hardware = MacHardwareInfo.current()
            }
        }
    }

    @MainActor
    func refresh() {
        overall = SandwalkRuntime.supervisor?.overall ?? .stopped
        config = SandwalkRuntime.config
        healthIntervalDraft = AppConfig.clampHealthCheckInterval(
            config.healthCheckIntervalSeconds
        )
        if !apiLikelyUp {
            report = nil
        }
    }
}
