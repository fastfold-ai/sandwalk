import CoreImage
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
                        sublabel: apiLANURL,
                        isLast: !remoteNeedsAuth
                    ) {
                        lanActions(apiLANURL)
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
                        sublabel: dashboardLANURL,
                        isLast: false
                    ) {
                        lanActions(dashboardLANURL)
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

    private var apiLANURL: String {
        "http://\(localLANHint()):\(draft.port)"
    }

    private var dashboardLANURL: String {
        "http://\(localLANHint()):\(draft.dashboardPort)"
    }

    private func lanActions(_ url: String) -> some View {
        HStack(alignment: .center, spacing: 8) {
            copyButton(url)
            LANQRCodeView(url: lanSignInURL(url))
        }
    }

    /// Same LAN address, plus the API key the dashboard already accepts as
    /// `sw_key`. The page strips that query after it signs in, so the key
    /// does not stay in the address bar. The visible hint and copy button
    /// stay the plain URL.
    private func lanSignInURL(_ url: String) -> String {
        let auth = AuthSettingsStore.load()
        guard auth.authEnabled, auth.apiKeyConfigured else { return url }
        guard var components = URLComponents(string: url) else { return url }
        var items = components.queryItems ?? []
        items.append(URLQueryItem(name: "sw_http", value: url))
        items.append(URLQueryItem(name: "sw_key", value: auth.apiKey))
        components.queryItems = items
        return components.string ?? url
    }

    private func copyButton(_ url: String) -> some View {
        Button {
            NSPasteboard.general.clearContents()
            NSPasteboard.general.setString(url, forType: .string)
            statusMessage = "Copied."
        } label: {
            Image(systemName: "doc.on.doc")
        }
        .buttonStyle(.sandwalk(.normal))
        .help("Copy")
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

/// Black-on-white QR for a LAN URL. Phones need the quiet white margin to scan it.
private struct LANQRCodeView: View {
    let url: String
    private let side: CGFloat = 84

    var body: some View {
        if let image = Self.makeImage(url: url) {
            Image(nsImage: image)
                .interpolation(.none)
                .resizable()
                .frame(width: side, height: side)
                .padding(6)
                .background(Color.white)
                .clipShape(RoundedRectangle(cornerRadius: 6, style: .continuous))
                .accessibilityLabel("QR code to open and sign in")
                .help("Scan to open this address and sign in")
        }
    }

    private static func makeImage(url: String) -> NSImage? {
        guard let data = url.data(using: .utf8),
              let filter = CIFilter(name: "CIQRCodeGenerator") else { return nil }
        filter.setValue(data, forKey: "inputMessage")
        filter.setValue("M", forKey: "inputCorrectionLevel")
        guard let output = filter.outputImage else { return nil }
        let module = output.extent.width
        guard module > 0 else { return nil }
        let scale = max(1, floor(180 / module))
        let scaled = output.transformed(by: CGAffineTransform(scaleX: scale, y: scale))
        let white = CIImage(color: CIColor(red: 1, green: 1, blue: 1)).cropped(to: scaled.extent)
        let composited = scaled.composited(over: white)
        let context = CIContext()
        guard let cg = context.createCGImage(composited, from: composited.extent) else { return nil }
        return NSImage(cgImage: cg, size: NSSize(width: composited.extent.width, height: composited.extent.height))
    }
}
