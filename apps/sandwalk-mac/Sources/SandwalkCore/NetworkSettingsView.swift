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

    /// `sandwalk serve` refuses a non-loopback bind without an enabled API key,
    /// exiting with code 2. Catch that here so Apply explains it instead of
    /// leaving the menubar in "Exited with code 2 — stopped auto-restart".
    private var remoteNeedsAuth: Bool {
        guard draft.apiExposesRemote else { return false }
        let auth = AuthSettingsStore.load()
        return !(auth.authEnabled && auth.apiKeyConfigured)
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
                        isLast: !remoteNeedsAuth
                    ) {
                        EmptyView()
                    }
                }
                if remoteNeedsAuth {
                    SettingsRow(
                        label: "API key required",
                        sublabel: "Remote access exposes shell, file, and credential endpoints to your network, so the agent requires auth.",
                        isLast: true
                    ) {
                        Button(busy ? "Enabling…" : "Generate & enable") {
                            Task { await enableAuthForRemote() }
                        }
                        .buttonStyle(.borderedProminent)
                        .controlSize(.small)
                        .disabled(busy)
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
                    isLast: false
                ) {
                    Toggle("", isOn: dashboardRemoteBinding)
                        .labelsHidden()
                        .toggleStyle(.switch)
                }
                if draft.dashboardExposesRemote {
                    SettingsRow(
                        label: "LAN hint",
                        sublabel: "http://\(localLANHint()):\(draft.dashboardPort)",
                        isLast: false
                    ) {
                        EmptyView()
                    }
                }
                SettingsRow(
                    label: "Web UI",
                    sublabel: liveConfig.dashboardHomeURL.absoluteString,
                    isLast: true
                ) {
                    Button("Open") {
                        NSWorkspace.shared.open(liveConfig.dashboardHomeURL)
                    }
                    .buttonStyle(.sandwalk(.normal))
                }
            }

            Text("Startup and menu bar options moved to General → Settings.")
                .font(.sandwalk(11))
                .foregroundStyle(theme.textTertiary)
                .padding(.horizontal, 18)
                .padding(.top, 10)

            HStack {
                if let statusMessage {
                    Text(statusMessage)
                        .font(.sandwalk(11.5))
                        .foregroundStyle(theme.textSecondary)
                        .lineLimit(2)
                }
                Spacer()
                Button("Open Web UI") {
                    NSWorkspace.shared.open(liveConfig.dashboardHomeURL)
                }
                .buttonStyle(.sandwalk(.normal))
                .disabled(busy)
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

    /// Generate + enable an API key so a remote bind can start.
    ///
    /// Keeps the requirement (remote exposes shell / file / credential endpoints)
    /// but makes satisfying it one click instead of a trip to Security.
    @MainActor
    private func enableAuthForRemote() async {
        busy = true
        defer { busy = false }
        var auth = AuthSettingsStore.load()
        if !auth.apiKeyConfigured {
            auth.apiKey = AuthSettingsStore.generateAPIKey()
        }
        auth.authEnabled = true
        do {
            try AuthSettingsStore.save(auth)
            statusMessage = "API key enabled. Apply to bind for remote access."
        } catch {
            statusMessage = error.localizedDescription
        }
    }

    @MainActor
    private func apply() async {
        guard portsValid else {
            statusMessage = "Ports must be 1–65535 and different from each other."
            return
        }
        if remoteNeedsAuth {
            statusMessage = """
            Remote access needs an API key — use Generate & enable above. \
            Without it the agent refuses to bind to 0.0.0.0 and exits.
            """
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
