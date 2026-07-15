import SwiftUI

// MARK: - Detail

enum McpDetailKind {
    case catalog(McpCatalogEntryDTO)
    case server(McpServerDTO)

    var title: String {
        switch self {
        case .catalog(let entry): return entry.name
        case .server(let server): return server.name
        }
    }

    var subtitle: String {
        switch self {
        case .catalog(let entry):
            return entry.description.trimmingCharacters(in: .whitespacesAndNewlines)
        case .server(let server):
            return server.description?.trimmingCharacters(in: .whitespacesAndNewlines)
                ?? server.transport
        }
    }
}

struct McpDetailSettingsView: View {
    let kind: McpDetailKind

    @Environment(\.sandwalkTheme) private var theme

    @State private var result: ValidateMcpDTO?
    @State private var toolQuery = ""
    @State private var busy = false
    @State private var error: String?
    @State private var enabled: Bool = true
    @State private var toggleBusy = false

    private var tools: [McpToolDetailDTO] {
        if let details = result?.toolDetails, !details.isEmpty {
            return details
        }
        return (result?.tools ?? []).map {
            McpToolDetailDTO(name: $0, title: nil, description: nil)
        }
    }

    private var filteredTools: [McpToolDetailDTO] {
        let q = toolQuery.trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
        guard !q.isEmpty else { return tools }
        return tools.filter { tool in
            [tool.name, tool.title, tool.description]
                .compactMap { $0?.lowercased() }
                .joined(separator: "\n")
                .contains(q)
        }
    }

    private var missingDescriptions: Bool {
        !tools.isEmpty && tools.allSatisfy {
            ($0.description ?? "").trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
        }
    }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 0) {
                SettingsSectionHeader(kind.title.uppercased(), subtitle: kind.subtitle.isEmpty ? "MCP server" : kind.subtitle)

                SettingsListGroup {
                    metaRows
                }

                SettingsSectionHeader(
                    "AVAILABLE TOOLS",
                    subtitle: "\(result?.toolCount ?? tools.count) tool calls — descriptions when the probe returns them"
                )

                if !tools.isEmpty {
                    HStack(spacing: 8) {
                        Image(systemName: "magnifyingglass")
                            .foregroundStyle(theme.textTertiary)
                        TextField("Search tools", text: $toolQuery)
                            .textFieldStyle(.plain)
                            .font(.sandwalk(13))
                    }
                    .padding(.horizontal, 14)
                    .padding(.vertical, 8)
                    .background(theme.groupBg)
                    .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
                    .padding(.horizontal, 14)
                    .padding(.bottom, 8)
                }

                if busy && result == nil {
                    SettingsListGroup {
                        SettingsRow(label: "Loading tools…", isLast: true) {
                            ProgressView().controlSize(.small)
                        }
                    }
                } else if missingDescriptions {
                    Text("Tool names loaded, but descriptions were not returned. Refresh after updating the agent server.")
                        .font(.sandwalk(11.5))
                        .foregroundStyle(.secondary)
                        .padding(.horizontal, 18)
                        .padding(.bottom, 8)
                }

                SettingsListGroup {
                    if filteredTools.isEmpty {
                        SettingsRow(
                            label: tools.isEmpty
                                ? (error == nil ? "No tools reported yet" : "Unable to load tools")
                                : "No tools match “\(toolQuery)”",
                            isLast: true
                        ) { EmptyView() }
                    } else {
                        ForEach(Array(filteredTools.enumerated()), id: \.element.id) { index, tool in
                            DisclosureGroup {
                                if let description = tool.description?
                                    .trimmingCharacters(in: .whitespacesAndNewlines),
                                   !description.isEmpty {
                                    Text(description)
                                        .font(.sandwalk(11.5))
                                        .foregroundStyle(theme.textSecondary)
                                        .frame(maxWidth: .infinity, alignment: .leading)
                                        .padding(.bottom, 8)
                                        .textSelection(.enabled)
                                } else {
                                    Text("No description provided.")
                                        .font(.sandwalk(11.5))
                                        .foregroundStyle(theme.textTertiary)
                                        .padding(.bottom, 8)
                                }
                            } label: {
                                VStack(alignment: .leading, spacing: 2) {
                                    Text(tool.name)
                                        .font(.sandwalkMono(12.5))
                                        .foregroundStyle(theme.text)
                                    if let title = tool.title?
                                        .trimmingCharacters(in: .whitespacesAndNewlines),
                                       !title.isEmpty, title != tool.name {
                                        Text(title)
                                            .font(.sandwalk(11))
                                            .foregroundStyle(theme.textTertiary)
                                    } else if let preview = firstParagraph(tool.description) {
                                        Text(preview)
                                            .font(.sandwalk(11))
                                            .foregroundStyle(theme.textTertiary)
                                            .lineLimit(2)
                                    }
                                }
                            }
                            .padding(.horizontal, 14)
                            .padding(.vertical, 8)
                            if index < filteredTools.count - 1 {
                                Divider().padding(.leading, 14)
                            }
                        }
                    }
                }

                HStack {
                    Button("Refresh tools") { Task { await loadTools() } }
                        .buttonStyle(.sandwalk(.normal))
                        .disabled(busy)
                    Spacer()
                }
                .padding(.horizontal, 18)
                .padding(.top, 10)

                AgentPaneError(message: error)
            }
            .padding(.top, 4)
            .padding(.bottom, 24)
        }
        .task { await loadTools() }
    }

    @ViewBuilder
    private var metaRows: some View {
        switch kind {
        case .catalog(let entry):
            SettingsRow(label: "Type", sublabel: "Featured") { EmptyView() }
            if let transport = entry.transport {
                SettingsRow(label: "Transport", sublabel: transport) { EmptyView() }
            }
            SettingsRow(
                label: "Auth",
                sublabel: entry.preferredAuth == "oauth" || entry.authMode == "oauth"
                    ? "OAuth" : "API key"
            ) { EmptyView() }
            SettingsRow(
                label: "Status",
                sublabel: entry.connected == true ? "Connected" : "Not connected"
            ) { EmptyView() }
            SettingsRow(
                label: "Tools",
                sublabel: "\(result?.toolCount ?? entry.toolCount ?? 0)",
                isLast: true
            ) {
                if let enabledBinding = catalogEnabledBinding(entry) {
                    Toggle("", isOn: enabledBinding)
                        .labelsHidden()
                        .toggleStyle(.switch)
                        .disabled(toggleBusy || entry.connected != true)
                }
            }
        case .server(let server):
            SettingsRow(label: "Type", sublabel: "Custom") { EmptyView() }
            SettingsRow(label: "Transport", sublabel: server.transport) { EmptyView() }
            if let url = server.url, !url.isEmpty {
                SettingsRow(label: "Endpoint", sublabel: url) { EmptyView() }
            } else if let command = server.command, !command.isEmpty {
                SettingsRow(label: "Command", sublabel: command) { EmptyView() }
            }
            SettingsRow(
                label: "Tools",
                sublabel: "\(result?.toolCount ?? tools.count)",
                isLast: true
            ) {
                Toggle("", isOn: Binding(
                    get: { enabled },
                    set: { next in Task { await setServerEnabled(server, next) } }
                ))
                .labelsHidden()
                .toggleStyle(.switch)
                .disabled(toggleBusy)
            }
        }
    }

    private func catalogEnabledBinding(_ entry: McpCatalogEntryDTO) -> Binding<Bool>? {
        Binding(
            get: { enabled },
            set: { next in Task { await setCatalogEnabled(entry, next) } }
        )
    }

    private func firstParagraph(_ text: String?) -> String? {
        guard let text else { return nil }
        let cleaned = text.replacingOccurrences(of: #"\s+"#, with: " ", options: .regularExpression)
            .trimmingCharacters(in: .whitespacesAndNewlines)
        guard !cleaned.isEmpty else { return nil }
        if let dot = cleaned.firstIndex(of: "."), cleaned.distance(from: cleaned.startIndex, to: dot) < 220 {
            return String(cleaned[...dot])
        }
        if cleaned.count <= 220 { return cleaned }
        let idx = cleaned.index(cleaned.startIndex, offsetBy: 219)
        return String(cleaned[..<idx]).trimmingCharacters(in: .whitespacesAndNewlines) + "…"
    }

    @MainActor
    private func loadTools() async {
        busy = true
        error = nil
        defer { busy = false }
        do {
            switch kind {
            case .catalog(let entry):
                enabled = entry.enabled ?? false
                result = try await SandwalkAPIClient.validateMcpCatalog(id: entry.id)
            case .server(let server):
                enabled = server.enabled
                result = try await SandwalkAPIClient.validateMcpServer(id: server.id)
            }
            if result?.ok == false {
                error = result?.message
            }
        } catch {
            self.error = error.localizedDescription
        }
    }

    @MainActor
    private func setCatalogEnabled(_ entry: McpCatalogEntryDTO, _ next: Bool) async {
        toggleBusy = true
        defer { toggleBusy = false }
        do {
            _ = try await SandwalkAPIClient.setMcpCatalogEnabled(id: entry.id, enabled: next)
            enabled = next
        } catch {
            self.error = error.localizedDescription
        }
    }

    @MainActor
    private func setServerEnabled(_ server: McpServerDTO, _ next: Bool) async {
        toggleBusy = true
        defer { toggleBusy = false }
        do {
            _ = try await SandwalkAPIClient.setMcpServerEnabled(id: server.id, enabled: next)
            enabled = next
        } catch {
            self.error = error.localizedDescription
        }
    }
}
