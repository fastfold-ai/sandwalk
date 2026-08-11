import SwiftUI

/// Server → Advanced — dashboard serve mode + agent DB durability.
struct AdvancedSettingsView: View {
    @State private var draft = AppConfig.load()
    @State private var statusMessage: String?
    @State private var busy = false
    @State private var rebuilding = false

    @Environment(\.sandwalkTheme) private var theme

    private var liveConfig: AppConfig { SandwalkRuntime.config }

    private var isDirty: Bool {
        draft.dashboardServeMode != liveConfig.dashboardServeMode
            || draft.dbAutoHeal != liveConfig.dbAutoHeal
    }

    private var distBuilt: Bool {
        guard let root = draft.repoRoot ?? liveConfig.repoRoot else { return false }
        return DashboardBuilder.isBuilt(repoRoot: root)
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            SettingsSectionHeader(
                "DASHBOARD MODE",
                subtitle: "Production serves the built UI from the API. Development runs Vite with hot reload."
            )
            SettingsListGroup {
                ForEach(DashboardServeMode.allCases, id: \.self) { mode in
                    SettingsRow(
                        label: mode.title,
                        sublabel: mode.detail,
                        isLast: mode == DashboardServeMode.allCases.last
                    ) {
                        Image(systemName: draft.dashboardServeMode == mode
                            ? "checkmark.circle.fill"
                            : "circle")
                            .foregroundStyle(
                                draft.dashboardServeMode == mode
                                    ? theme.accent
                                    : theme.textTertiary
                            )
                            .onTapGesture {
                                draft.dashboardServeMode = mode
                            }
                    }
                    .contentShape(Rectangle())
                    .onTapGesture {
                        draft.dashboardServeMode = mode
                    }
                }
            }

            SettingsSectionHeader(
                "PRODUCTION BUILD",
                subtitle: distBuilt
                    ? "apps/local-web/dist is ready."
                    : "Build once before production mode can start."
            )
            SettingsListGroup {
                SettingsRow(
                    label: "Rebuild dashboard",
                    sublabel: "Runs pnpm build for @sandwalk/agent-local-web. Restarts if production is live.",
                    isLast: true
                ) {
                    Button(rebuilding ? "Building…" : "Rebuild") {
                        Task { await rebuild() }
                    }
                    .buttonStyle(.sandwalk(.normal))
                    .disabled(busy || rebuilding)
                }
            }

            SettingsSectionHeader(
                "AGENT DATABASE",
                subtitle: "Protects against corrupt ~/.sandwalk/agent-server.db after hard kills."
            )
            SettingsListGroup {
                SettingsRow(
                    label: "Auto-heal on startup",
                    sublabel: draft.dbAutoHeal
                        ? "Quarantine a corrupt DB, try sqlite recover, then restore the last healthy backup."
                        : "Fail loud if the DB is corrupt — no automatic quarantine or restore.",
                    isLast: true
                ) {
                    Toggle("", isOn: $draft.dbAutoHeal)
                        .labelsHidden()
                        .toggleStyle(.switch)
                }
            }

            HStack {
                if let statusMessage {
                    Text(statusMessage)
                        .font(.sandwalk(11.5))
                        .foregroundStyle(theme.textSecondary)
                        .lineLimit(3)
                }
                Spacer()
                Button(busy ? "Applying…" : "Apply") {
                    Task { await apply() }
                }
                .buttonStyle(.sandwalk(.primary))
                .keyboardShortcut(.defaultAction)
                .disabled(busy || rebuilding || !isDirty)
            }
            .padding(.horizontal, 18)
            .padding(.top, 10)

            Text(
                draft.dashboardServeMode == .production
                    ? "Production opens the dashboard on the API port (\(draft.port))."
                    : "Development uses the dashboard port (\(draft.dashboardPort)) with Vite."
            )
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

    @MainActor
    private func apply() async {
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
            let healNote = draft.dbAutoHeal ? "auto-heal on" : "auto-heal off"
            statusMessage = supervisor.overall.isLive
                ? "Applied — \(draft.dashboardServeMode.title), \(healNote)."
                : "Saved. Use Start to run (\(healNote))."
        } catch {
            statusMessage = error.localizedDescription
        }
    }

    @MainActor
    private func rebuild() async {
        rebuilding = true
        statusMessage = nil
        defer { rebuilding = false }

        guard let supervisor = SandwalkRuntime.supervisor else {
            guard let root = draft.repoRoot ?? AppConfig.load().repoRoot else {
                statusMessage = DashboardBuilder.BuildError.missingRepo.localizedDescription
                return
            }
            do {
                try DashboardBuilder.ensureBuilt(
                    repoRoot: root,
                    force: true,
                    logURL: draft.webLogURL
                )
                statusMessage = "Dashboard rebuilt."
            } catch {
                statusMessage = error.localizedDescription
            }
            return
        }

        do {
            try await supervisor.rebuildProductionDashboard()
            draft = supervisor.config
            statusMessage = "Dashboard rebuilt."
        } catch {
            statusMessage = error.localizedDescription
        }
    }
}
