import AppKit
import SwiftUI

/// oMLX-style Security pane: API key + enable auth toggle.
struct SecuritySettingsView: View {
    @State private var settings = AuthSettingsStore.load()
    @State private var revealKey = false
    @State private var statusMessage: String?
    @State private var busy = false

    var body: some View {
        Form {
            Section {
                Text("API KEY")
                    .font(.caption)
                    .foregroundStyle(.secondary)
                Text("Required to authenticate /v1 requests and web UI sessions when auth is enabled.")
                    .font(.caption)
                    .foregroundStyle(.secondary)

                HStack(alignment: .center, spacing: 8) {
                    Group {
                        if revealKey {
                            TextField("API Key", text: $settings.apiKey)
                        } else {
                            SecureField("API Key", text: $settings.apiKey)
                        }
                    }
                    .textFieldStyle(.roundedBorder)

                    Button {
                        revealKey.toggle()
                    } label: {
                        Image(systemName: revealKey ? "eye.slash" : "eye")
                    }
                    .help(revealKey ? "Hide" : "Show")

                    Button {
                        settings.apiKey = AuthSettingsStore.generateAPIKey()
                        statusMessage = "Generated a new key — click Save to persist."
                    } label: {
                        Image(systemName: "arrow.clockwise")
                    }
                    .help("Regenerate")

                    Button {
                        NSPasteboard.general.clearContents()
                        NSPasteboard.general.setString(settings.apiKey, forType: .string)
                        statusMessage = "Copied API key."
                    } label: {
                        Image(systemName: "doc.on.doc")
                    }
                    .help("Copy")
                    .disabled(settings.apiKey.isEmpty)
                }
            }

            Section {
                Text("AUTHENTICATION")
                    .font(.caption)
                    .foregroundStyle(.secondary)
                Toggle(isOn: $settings.authEnabled) {
                    VStack(alignment: .leading, spacing: 2) {
                        Text("Enable API key verification")
                        Text("Require API key or web login for /v1 and the dashboard.")
                            .font(.caption)
                            .foregroundStyle(.secondary)
                    }
                }
                .toggleStyle(.switch)
            }

            Section {
                HStack {
                    Button("Save") {
                        save()
                    }
                    .keyboardShortcut(.defaultAction)
                    .disabled(busy)

                    if let statusMessage {
                        Text(statusMessage)
                            .font(.caption)
                            .foregroundStyle(.secondary)
                    }
                    Spacer()
                    Text(AuthSettingsStore.settingsFileURL().path)
                        .font(.caption2)
                        .foregroundStyle(.tertiary)
                        .lineLimit(1)
                        .truncationMode(.middle)
                }
            }
        }
        .formStyle(.grouped)
        .padding()
        .frame(minWidth: 520, minHeight: 320)
        .onAppear {
            settings = AuthSettingsStore.load()
            if settings.apiKey.isEmpty {
                settings.apiKey = AuthSettingsStore.generateAPIKey()
            }
        }
    }

    private func save() {
        busy = true
        defer { busy = false }
        do {
            if settings.authEnabled, settings.apiKey.trimmingCharacters(in: .whitespacesAndNewlines).count < 4 {
                statusMessage = "API key must be at least 4 characters."
                return
            }
            try AuthSettingsStore.save(settings)
            statusMessage = "Saved. Restart Sandwalk (Stop → Start) if the server is running."
            // Best-effort live PATCH when API is up.
            Task {
                await pushToRunningServer()
            }
        } catch {
            statusMessage = error.localizedDescription
        }
    }

    private func pushToRunningServer() async {
        let config = AppConfig.load()
        var request = URLRequest(url: config.apiBaseURL.appendingPathComponent("v1/auth/settings"))
        request.httpMethod = "PATCH"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.timeoutInterval = 3
        let body: [String: Any] = [
            "apiKey": settings.apiKey,
            "authEnabled": settings.authEnabled,
        ]
        request.httpBody = try? JSONSerialization.data(withJSONObject: body)
        // When auth is already on, send Bearer.
        let prior = AuthSettingsStore.load()
        if prior.authEnabled, !prior.apiKey.isEmpty {
            request.setValue("Bearer \(prior.apiKey)", forHTTPHeaderField: "Authorization")
        } else if settings.authEnabled, !settings.apiKey.isEmpty {
            request.setValue("Bearer \(settings.apiKey)", forHTTPHeaderField: "Authorization")
        }
        _ = try? await URLSession.shared.data(for: request)
    }
}
