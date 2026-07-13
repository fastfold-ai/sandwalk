import AppKit
import SwiftUI

/// Shared chrome for agent Settings panes that need a live `/v1` API.
struct AgentAPIGate<Content: View>: View {
    @ViewBuilder var content: () -> Content
    @State private var overall: SandwalkSupervisor.OverallState = .stopped

    @Environment(\.sandwalkTheme) private var theme

    private var apiUp: Bool {
        switch overall {
        case .running, .partial: return true
        default: return false
        }
    }

    var body: some View {
        Group {
            if apiUp {
                content()
            } else {
                VStack(alignment: .leading, spacing: 12) {
                    SettingsSectionHeader("AGENT API", subtitle: "These settings require sandwalk serve.")
                    SettingsListGroup {
                        SettingsRow(
                            label: "API not running",
                            sublabel: "Start Sandwalk from Status or the menu bar, then return here.",
                            isLast: true
                        ) {
                            Button("Open Status") {
                                NotificationCenter.default.post(
                                    name: .sandwalkSelectSettingsSection,
                                    object: SettingsSection.status
                                )
                            }
                            .buttonStyle(.sandwalk(.primary))
                        }
                    }
                }
                .padding(.top, 4)
            }
        }
        .onAppear { refresh() }
        .onReceive(NotificationCenter.default.publisher(for: SandwalkSupervisor.stateDidChangeNotification)) { _ in
            refresh()
        }
    }

    private func refresh() {
        overall = SandwalkRuntime.supervisor?.overall ?? .stopped
    }
}

struct AgentPaneError: View {
    let message: String?
    @Environment(\.sandwalkTheme) private var theme

    var body: some View {
        if let message, !message.isEmpty {
            Text(message)
                .font(.sandwalk(11.5))
                .foregroundStyle(theme.redDot)
                .padding(.horizontal, 18)
                .padding(.top, 8)
        }
    }
}

struct AgentSearchField: View {
    @Binding var text: String
    @Environment(\.sandwalkTheme) private var theme

    var body: some View {
        HStack(spacing: 8) {
            Image(systemName: "magnifyingglass")
                .foregroundStyle(theme.textTertiary)
            TextField("Search", text: $text)
                .textFieldStyle(.plain)
                .font(.sandwalk(13))
        }
        .padding(.horizontal, 12)
        .padding(.vertical, 8)
        .background(theme.groupBg)
        .clipShape(RoundedRectangle(cornerRadius: 10, style: .continuous))
        .padding(.horizontal, 14)
        .padding(.bottom, 8)
    }
}

/// Tip + link to the full-featured web dashboard for a Settings pane.
struct WebUIManagementCallout: View {
    let topic: String
    let path: String

    @Environment(\.sandwalkTheme) private var theme

    private var url: URL {
        SandwalkRuntime.config.dashboardPageURL(path)
    }

    var body: some View {
        SettingsListGroup {
            HStack(alignment: .top, spacing: 12) {
                Image(systemName: "safari")
                    .font(.system(size: 14))
                    .foregroundStyle(theme.textSecondary)
                    .padding(.top, 1)

                VStack(alignment: .leading, spacing: 6) {
                    Text("Open in Web UI for full-featured \(topic) management.")
                        .font(.sandwalk(12.5))
                        .foregroundStyle(theme.text)
                        .fixedSize(horizontal: false, vertical: true)
                    Text(url.absoluteString)
                        .font(.sandwalkMono(11))
                        .foregroundStyle(theme.textTertiary)
                        .lineLimit(1)
                        .truncationMode(.middle)
                }

                Spacer(minLength: 8)

                Button {
                    NSWorkspace.shared.open(url)
                } label: {
                    Label("Open", systemImage: "arrow.up.right.square")
                        .labelStyle(.titleAndIcon)
                }
                .buttonStyle(.sandwalk(.normal))
            }
            .padding(.horizontal, 14)
            .padding(.vertical, 12)
        }
        .padding(.top, 4)
        .padding(.bottom, 6)
    }
}

extension Notification.Name {
    static let sandwalkSelectSettingsSection = Notification.Name("SandwalkSelectSettingsSection")
}

enum ByteFormat {
    static func string(_ bytes: Int64) -> String {
        let formatter = ByteCountFormatter()
        formatter.countStyle = .file
        return formatter.string(fromByteCount: bytes)
    }
}
