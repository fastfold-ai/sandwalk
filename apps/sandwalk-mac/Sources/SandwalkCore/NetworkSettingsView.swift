import SwiftUI

/// Network pane — API / dashboard ports + remote bind (oMLX Network style).
struct NetworkSettingsView: View {
    @State private var draft = AppConfig.load()
    @State private var statusMessage: String?
    @State private var busy = false

    @Environment(\.sandwalkTheme) private var theme

    private var liveConfig: AppConfig { SandwalkRuntime.config }

    private var isDirty: Bool {
        draft.bindHost != liveConfig.bindHost
            || draft.port != liveConfig.port
            || draft.dashboardHost != liveConfig.dashboardHost
            || draft.dashboardPort != liveConfig.dashboardPort
            || draft.autoStartOnLaunch != liveConfig.autoStartOnLaunch
    }

    private var portsValid: Bool {
        guard (1...65535).contains(draft.port) else { return false }
        guard (1...65535).contains(draft.dashboardPort) else { return false }
        // Production hosts UI on the API port — dashboard port only matters in development.
        if draft.dashboardServeMode == .production {
            return true
        }
        return draft.port != draft.dashboardPort
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            SettingsSectionHeader(
                "AGENT API",
                subtitle: "Python sandwalk serve — health at /v1/health."
            )
            SettingsListGroup {
                SettingsRow(label: "Port", sublabel: "Default 8787") {
                    SettingsPortField(value: $draft.port)
                }
                SettingsRow(
                    label: "Allow remote connections",
                    sublabel: "Bind to 0.0.0.0 so other devices on your network can reach the API.",
                    isLast: !draft.apiExposesRemote
                ) {
                    Toggle("", isOn: apiRemoteBinding)
                        .labelsHidden()
                        .toggleStyle(.switch)
                }
                if draft.apiExposesRemote {
                    SettingsRow(
                        label: "LAN hint",
                        sublabel: "http://\(localLANHint()):\(draft.port)",
                        isLast: true
                    ) {
                        EmptyView()
                    }
                }
            }

            SettingsSectionHeader(
                "WEB DASHBOARD",
                subtitle: liveConfig.usesBundledDashboard
                    ? "Used in Development mode (Vite). Production serves the UI from the API port."
                    : "Vite UI supervised by the menubar."
            )
            SettingsListGroup {
                SettingsRow(label: "Port", sublabel: "Default 8969") {
                    SettingsPortField(value: $draft.dashboardPort)
                }
                SettingsRow(
                    label: "Allow remote connections",
                    sublabel: "Bind the UI to 0.0.0.0 for LAN access (use with care).",
                    isLast: !draft.dashboardExposesRemote
                ) {
                    Toggle("", isOn: dashboardRemoteBinding)
                        .labelsHidden()
                        .toggleStyle(.switch)
                }
                if draft.dashboardExposesRemote {
                    SettingsRow(
                        label: "LAN hint",
                        sublabel: "http://\(localLANHint()):\(draft.dashboardPort)",
                        isLast: true
                    ) {
                        EmptyView()
                    }
                }
            }

            SettingsSectionHeader("LAUNCH")
            SettingsListGroup {
                SettingsRow(
                    label: "Start on launch",
                    sublabel: "Automatically start API + web when the menubar app opens.",
                    isLast: true
                ) {
                    Toggle("", isOn: $draft.autoStartOnLaunch)
                        .labelsHidden()
                        .toggleStyle(.switch)
                }
            }

            HStack {
                if let statusMessage {
                    Text(statusMessage)
                        .font(.sandwalk(11.5))
                        .foregroundStyle(theme.textSecondary)
                        .lineLimit(2)
                }
                Spacer()
                Button(busy ? "Applying…" : "Apply") {
                    Task { await apply() }
                }
                .buttonStyle(.sandwalk(.primary))
                .keyboardShortcut(.defaultAction)
                .disabled(busy || !isDirty || !portsValid)
            }
            .padding(.horizontal, 18)
            .padding(.top, 10)

            Text("Changing ports or bind address restarts both services.")
                .font(.sandwalk(11))
                .foregroundStyle(theme.textTertiary)
                .padding(.horizontal, 18)
                .padding(.top, 6)
        }
        .padding(.top, 4)
        .onAppear { draft = SandwalkRuntime.config }
        .onReceive(
            NotificationCenter.default.publisher(for: SandwalkSupervisor.configDidChangeNotification)
        ) { _ in
            draft = SandwalkRuntime.config
        }
    }

    private var apiRemoteBinding: Binding<Bool> {
        Binding(
            get: { draft.bindHost == "0.0.0.0" },
            set: { draft.bindHost = $0 ? "0.0.0.0" : "127.0.0.1" }
        )
    }

    private var dashboardRemoteBinding: Binding<Bool> {
        Binding(
            get: { draft.dashboardHost == "0.0.0.0" },
            set: { draft.dashboardHost = $0 ? "0.0.0.0" : "127.0.0.1" }
        )
    }

    private func localLANHint() -> String {
        let host = ProcessInfo.processInfo.hostName
            .trimmingCharacters(in: CharacterSet(charactersIn: "."))
        return host.isEmpty ? "your-mac.local" : host
    }

    @MainActor
    private func apply() async {
        guard portsValid else {
            statusMessage = "Ports must be 1–65535 and different from each other."
            return
        }
        busy = true
        statusMessage = nil
        defer { busy = false }

        guard let supervisor = SandwalkRuntime.supervisor else {
            do {
                try draft.saveNetworkSettings()
                statusMessage = "Saved. Start Sandwalk to apply."
            } catch {
                statusMessage = error.localizedDescription
            }
            return
        }

        do {
            try await supervisor.applyNetworkConfig(draft)
            draft = supervisor.config
            statusMessage = supervisor.overall.isLive
                ? "Applied — API :\(draft.port), UI :\(draft.dashboardPort)."
                : "Saved. Use Start to run with these ports."
        } catch {
            statusMessage = error.localizedDescription
        }
    }
}
