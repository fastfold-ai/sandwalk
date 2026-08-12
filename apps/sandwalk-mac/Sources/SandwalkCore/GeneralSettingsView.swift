import SwiftUI

/// General → Settings — login item, agent auto-start, Cmd+Q vs Quit behavior.
struct GeneralSettingsView: View {
    @State private var draft = AppConfig.load()
    @State private var openAtLogin = LoginItemSupport.isEnabled
    @State private var statusMessage: String?
    @State private var busy = false

    @Environment(\.sandwalkTheme) private var theme

    private var liveConfig: AppConfig { SandwalkRuntime.config }

    private var isDirty: Bool {
        draft.autoStartOnLaunch != liveConfig.autoStartOnLaunch
            || draft.keepMenubarOnCmdQ != liveConfig.keepMenubarOnCmdQ
            || openAtLogin != LoginItemSupport.isEnabled
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            SettingsSectionHeader(
                "STARTUP",
                subtitle: "How Sandwalk attaches to this Mac and when the agent API starts."
            )
            SettingsListGroup {
                SettingsRow(
                    label: "Open at Login",
                    sublabel: LoginItemSupport.statusDescription,
                    isLast: false
                ) {
                    Toggle("", isOn: $openAtLogin)
                        .labelsHidden()
                        .toggleStyle(.switch)
                }
                SettingsRow(
                    label: "Start agent on launch",
                    sublabel: "When Sandwalk opens, start the API (and dashboard) automatically.",
                    isLast: true
                ) {
                    Toggle("", isOn: $draft.autoStartOnLaunch)
                        .labelsHidden()
                        .toggleStyle(.switch)
                }
            }

            SettingsSectionHeader(
                "MENU BAR",
                subtitle: "Sandwalk is a menu bar app. Closing Settings never stops the agent."
            )
            SettingsListGroup {
                SettingsRow(
                    label: "Keep running on ⌘Q",
                    sublabel: draft.keepMenubarOnCmdQ
                        ? "⌘Q closes windows only — menu bar and agent keep running. Use Quit Sandwalk to stop."
                        : "⌘Q fully quits Sandwalk and stops the agent server.",
                    isLast: true
                ) {
                    Toggle("", isOn: $draft.keepMenubarOnCmdQ)
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
                .disabled(busy || !isDirty)
            }
            .padding(.horizontal, 18)
            .padding(.top, 10)

            Text("Menu bar → Quit Sandwalk always stops the agent and exits, regardless of ⌘Q.")
                .font(.sandwalk(11))
                .foregroundStyle(theme.textTertiary)
                .padding(.horizontal, 18)
                .padding(.top, 6)
        }
        .padding(.top, 4)
        .onAppear { reloadFromLive() }
        .onReceive(
            NotificationCenter.default.publisher(for: SandwalkSupervisor.configDidChangeNotification)
        ) { _ in
            reloadFromLive()
        }
    }

    @MainActor
    private func reloadFromLive() {
        draft = SandwalkRuntime.config
        openAtLogin = LoginItemSupport.isEnabled
    }

    @MainActor
    private func apply() async {
        busy = true
        statusMessage = nil
        defer { busy = false }

        do {
            if openAtLogin != LoginItemSupport.isEnabled {
                try LoginItemSupport.setEnabled(openAtLogin)
            }
            // Reflect OS truth (may still be off if approval is required).
            let wantedLogin = openAtLogin
            openAtLogin = LoginItemSupport.isEnabled
            if wantedLogin, !openAtLogin {
                statusMessage = LoginItemSupport.statusDescription
            }

            if let supervisor = SandwalkRuntime.supervisor {
                try supervisor.applyGeneralPreferences(draft)
                draft = supervisor.config
            } else {
                try draft.saveNetworkSettings()
            }

            if statusMessage == nil {
                statusMessage = "Saved."
            } else if wantedLogin, !openAtLogin {
                statusMessage = "Preferences saved. \(LoginItemSupport.statusDescription)"
            }
        } catch {
            statusMessage = error.localizedDescription
        }
    }
}
