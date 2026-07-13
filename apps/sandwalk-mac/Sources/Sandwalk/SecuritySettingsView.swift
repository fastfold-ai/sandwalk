import AppKit
import SwiftUI

/// Security pane — API key generate / show / copy / reset (oMLX card style).
struct SecuritySettingsView: View {
    @State private var settings = AuthSettingsStore.load()
    @State private var revealKey = false
    @State private var statusMessage: String?
    @State private var busy = false
    @State private var confirmReset = false

    @Environment(\.sandwalkTheme) private var theme

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            SettingsSectionHeader(
                "API KEY",
                subtitle: "Same file as sandwalk auth. Required when authentication is enabled."
            )
            SettingsListGroup {
                FreeSettingsRow(isLast: false) {
                    HStack(spacing: 8) {
                        Group {
                            if revealKey {
                                TextField("API Key", text: $settings.apiKey)
                            } else {
                                SecureField("API Key", text: $settings.apiKey)
                            }
                        }
                        .font(.sandwalkMono(12.5))
                        .textFieldStyle(.plain)
                        .padding(.horizontal, 8)
                        .padding(.vertical, 6)
                        .background(theme.inputBg)
                        .clipShape(RoundedRectangle(cornerRadius: 6, style: .continuous))
                        .overlay(
                            RoundedRectangle(cornerRadius: 6, style: .continuous)
                                .strokeBorder(theme.inputBorder, lineWidth: 0.5)
                        )

                        Button {
                            revealKey.toggle()
                        } label: {
                            Image(systemName: revealKey ? "eye.slash" : "eye")
                        }
                        .buttonStyle(.sandwalk(.normal))
                        .help(revealKey ? "Hide" : "Show")

                        Button {
                            settings.apiKey = AuthSettingsStore.generateAPIKey()
                            revealKey = true
                            statusMessage = "Generated — click Save to apply."
                        } label: {
                            Image(systemName: "arrow.clockwise")
                        }
                        .buttonStyle(.sandwalk(.normal))
                        .help("Generate")

                        Button {
                            NSPasteboard.general.clearContents()
                            NSPasteboard.general.setString(settings.apiKey, forType: .string)
                            statusMessage = "Copied."
                        } label: {
                            Image(systemName: "doc.on.doc")
                        }
                        .buttonStyle(.sandwalk(.normal))
                        .disabled(settings.apiKey.isEmpty)
                        .help("Copy")

                        Button {
                            confirmReset = true
                        } label: {
                            Image(systemName: "trash")
                        }
                        .buttonStyle(.sandwalk(.destructive))
                        .help("Reset")
                    }
                }
                SettingsRow(
                    label: "Key format",
                    sublabel: "sk-sandwalk-…",
                    isLast: true
                ) {
                    EmptyView()
                }
            }

            SettingsSectionHeader("AUTHENTICATION")
            SettingsListGroup {
                SettingsRow(
                    label: "Enable API key verification",
                    sublabel: "Require API key or web login for /v1 and the dashboard. Recommended when remote connections are allowed.",
                    isLast: true
                ) {
                    Toggle("", isOn: $settings.authEnabled)
                        .labelsHidden()
                        .toggleStyle(.switch)
                }
            }

            if settings.authEnabled,
               SandwalkRuntime.config.apiExposesRemote || SandwalkRuntime.config.dashboardExposesRemote
            {
                Text("Remote exposure is on — keep auth enabled.")
                    .font(.sandwalk(11.5))
                    .foregroundStyle(theme.warningText)
                    .padding(.horizontal, 18)
                    .padding(.top, 8)
            }

            HStack {
                if let statusMessage {
                    Text(statusMessage)
                        .font(.sandwalk(11.5))
                        .foregroundStyle(theme.textSecondary)
                        .lineLimit(2)
                }
                Spacer()
                Button(busy ? "Saving…" : "Save") {
                    Task { await save() }
                }
                .buttonStyle(.sandwalk(.primary))
                .keyboardShortcut(.defaultAction)
                .disabled(busy)
            }
            .padding(.horizontal, 18)
            .padding(.top, 12)

            Text(AuthSettingsStore.settingsFileURL().path)
                .font(.sandwalk(10.5))
                .foregroundStyle(theme.textTertiary)
                .lineLimit(1)
                .truncationMode(.middle)
                .padding(.horizontal, 18)
                .padding(.top, 6)
        }
        .padding(.top, 4)
        .onAppear {
            settings = AuthSettingsStore.load()
            if settings.apiKey.isEmpty {
                settings.apiKey = AuthSettingsStore.generateAPIKey()
                statusMessage = "No key on disk — generated one. Click Save."
            }
        }
        .confirmationDialog(
            "Reset API key?",
            isPresented: $confirmReset,
            titleVisibility: .visible
        ) {
            Button("Generate new key", role: .destructive) {
                settings.apiKey = AuthSettingsStore.generateAPIKey()
                revealKey = true
                statusMessage = "New key ready — Save to revoke the old one."
            }
            Button("Cancel", role: .cancel) {}
        } message: {
            Text("Existing CLI/web sessions will need the new key after you Save.")
        }
    }

    @MainActor
    private func save() async {
        busy = true
        defer { busy = false }

        let trimmed = settings.apiKey.trimmingCharacters(in: .whitespacesAndNewlines)
        if settings.authEnabled, trimmed.count < 4 {
            statusMessage = "API key must be at least 4 characters."
            return
        }
        settings.apiKey = trimmed

        let prior = AuthSettingsStore.load()
        do {
            try AuthSettingsStore.save(settings)
        } catch {
            statusMessage = error.localizedDescription
            return
        }

        let pushed = await pushToRunningServer(prior: prior)
        statusMessage = pushed
            ? "Saved and applied to the running API."
            : "Saved. Restart if the server did not pick it up."
    }

    private func pushToRunningServer(prior: SandwalkAuthSettings) async -> Bool {
        let config = SandwalkRuntime.config
        var request = URLRequest(url: config.apiBaseURL.appendingPathComponent("v1/auth/settings"))
        request.httpMethod = "PATCH"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.timeoutInterval = 4
        let body: [String: Any] = [
            "apiKey": settings.apiKey,
            "authEnabled": settings.authEnabled,
        ]
        request.httpBody = try? JSONSerialization.data(withJSONObject: body)

        if prior.authEnabled, !prior.apiKey.isEmpty {
            request.setValue("Bearer \(prior.apiKey)", forHTTPHeaderField: "Authorization")
        } else if settings.authEnabled, !settings.apiKey.isEmpty {
            request.setValue("Bearer \(settings.apiKey)", forHTTPHeaderField: "Authorization")
        }

        guard let (_, response) = try? await URLSession.shared.data(for: request),
              let http = response as? HTTPURLResponse,
              (200..<300).contains(http.statusCode)
        else {
            return false
        }
        return true
    }
}

private struct FreeSettingsRow<Content: View>: View {
    let isLast: Bool
    @ViewBuilder var content: () -> Content
    @Environment(\.sandwalkTheme) private var theme

    var body: some View {
        content()
            .padding(.horizontal, 14)
            .padding(.vertical, 10)
            .frame(maxWidth: .infinity, alignment: .leading)
            .overlay(alignment: .bottom) {
                if !isLast {
                    Rectangle()
                        .fill(theme.rowSep)
                        .frame(height: 0.5)
                        .padding(.horizontal, 14)
                }
            }
    }
}
