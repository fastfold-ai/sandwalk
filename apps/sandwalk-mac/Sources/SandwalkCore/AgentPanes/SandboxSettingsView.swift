import SwiftUI

/// Sandbox list — Local and Modal each open a detail page (matches web).
struct SandboxSettingsView: View {
    @Environment(\.sandwalkTheme) private var theme

    @State private var modalConfigured = false
    @State private var busy = false
    @State private var error: String?

    var body: some View {
        AgentAPIGate {
            VStack(alignment: .leading, spacing: 0) {
                WebUIManagementCallout(topic: "Sandbox", path: "agent/sandbox")

                SettingsSectionHeader(
                    "SANDBOX",
                    subtitle: "Chats default to Local Sandbox. Enable Modal per chat in the composer."
                )
                SettingsListGroup {
                    NavigationLink {
                        LocalSandboxDetailView()
                    } label: {
                        sandboxListLabel(
                            title: "Local Sandbox",
                            subtitle: "Python environment on this Mac — interpreter, packages, and local compute.",
                            badge: "Default"
                        )
                    }
                    .buttonStyle(.plain)

                    Divider().padding(.leading, 14)

                    NavigationLink {
                        ModalSandboxDetailView()
                    } label: {
                        sandboxListLabel(
                            title: "Modal Sandbox",
                            subtitle: modalConfigured
                                ? "Cloud compute on Modal — credentials, CPU/GPU, images, and pip packages."
                                : "Not configured — set Modal tokens under Integrations first.",
                            badge: modalConfigured ? nil : "Setup needed"
                        )
                    }
                    .buttonStyle(.plain)
                }

                AgentPaneError(message: error)
                Spacer(minLength: 0)
            }
            .padding(.top, 4)
            .task { await loadMeta() }
        }
    }

    @ViewBuilder
    private func sandboxListLabel(title: String, subtitle: String, badge: String?) -> some View {
        HStack(alignment: .center, spacing: 12) {
            VStack(alignment: .leading, spacing: 2) {
                HStack(spacing: 8) {
                    Text(title)
                        .font(.sandwalk(13, weight: .medium))
                        .foregroundStyle(theme.text)
                    if let badge {
                        Text(badge)
                            .font(.sandwalk(10, weight: .semibold))
                            .foregroundStyle(badge == "Default" ? Color.green : Color.orange)
                            .padding(.horizontal, 6)
                            .padding(.vertical, 2)
                            .background(
                                (badge == "Default" ? Color.green : Color.orange).opacity(0.15)
                            )
                            .clipShape(RoundedRectangle(cornerRadius: 4, style: .continuous))
                    }
                }
                Text(subtitle)
                    .font(.sandwalk(11.5))
                    .foregroundStyle(theme.textTertiary)
                    .fixedSize(horizontal: false, vertical: true)
            }
            Spacer(minLength: 8)
            Image(systemName: "chevron.right")
                .font(.system(size: 11, weight: .semibold))
                .foregroundStyle(theme.textTertiary)
        }
        .padding(.horizontal, 14)
        .padding(.vertical, 12)
        .contentShape(Rectangle())
    }

    @MainActor
    private func loadMeta() async {
        busy = true
        error = nil
        defer { busy = false }
        do {
            let settings = try await SandwalkAPIClient.getSandboxSettings()
            modalConfigured = settings.modalConfigured
        } catch {
            self.error = error.localizedDescription
        }
    }
}
