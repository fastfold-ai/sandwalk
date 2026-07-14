import SwiftUI

struct MCPsSettingsView: View {
    @State private var servers: [McpServerDTO] = []
    @State private var catalog: [McpCatalogEntryDTO] = []
    @State private var search = ""
    @State private var error: String?
    @State private var status: String?
    @State private var busy = false
    @State private var showAdd = false
    @State private var newName = ""
    @State private var newCommand = ""
    @State private var connectKey = ""
    @State private var connectingId: String?

    /// Custom / hand-added servers only — catalog-backed ones live under Featured.
    private var customServers: [McpServerDTO] {
        let customs = servers.filter { server in
            let cid = server.catalogId?.trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
            return cid.isEmpty
        }
        let q = search.trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
        guard !q.isEmpty else { return customs }
        return customs.filter {
            $0.name.lowercased().contains(q) || $0.id.lowercased().contains(q)
        }
    }

    private var filteredCatalog: [McpCatalogEntryDTO] {
        let q = search.trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
        guard !q.isEmpty else { return catalog }
        return catalog.filter {
            $0.name.lowercased().contains(q)
                || $0.description.lowercased().contains(q)
        }
    }

    var body: some View {
        AgentAPIGate {
            VStack(alignment: .leading, spacing: 0) {
                WebUIManagementCallout(topic: "MCPs", path: "mcp")

                AgentSearchField(text: $search)

                SettingsSectionHeader(
                    "SUGGESTED",
                    subtitle: "\(filteredCatalog.count) catalog providers — open for tools"
                )
                SettingsListGroup {
                    if filteredCatalog.isEmpty {
                        SettingsRow(
                            label: busy ? "Loading…" : "No catalog entries",
                            isLast: true
                        ) { EmptyView() }
                    } else {
                        ForEach(Array(filteredCatalog.enumerated()), id: \.element.id) { index, entry in
                            SettingsRow(
                                label: entry.name,
                                sublabel: catalogSublabel(entry),
                                isLast: index == filteredCatalog.count - 1
                            ) {
                                HStack(spacing: 8) {
                                    catalogTrailing(entry)
                                    NavigationLink {
                                        McpDetailSettingsView(kind: .catalog(entry))
                                    } label: {
                                        Text("Open")
                                    }
                                    .buttonStyle(.sandwalk(.normal))
                                }
                                .disabled(busy)
                            }
                        }
                    }
                }

                SettingsSectionHeader(
                    "CUSTOM",
                    subtitle: "\(customServers.count) stdio / hand-configured servers"
                )
                SettingsListGroup {
                    if customServers.isEmpty {
                        SettingsRow(
                            label: busy ? "Loading…" : "No custom MCP servers",
                            isLast: true
                        ) {
                            Button("Add") { showAdd = true }
                                .buttonStyle(.sandwalk(.normal))
                        }
                    } else {
                        ForEach(Array(customServers.enumerated()), id: \.element.id) { index, server in
                            SettingsRow(
                                label: server.name,
                                sublabel: "\(server.transport)\(server.enabled ? "" : " · disabled")",
                                isLast: index == customServers.count - 1
                            ) {
                                HStack(spacing: 6) {
                                    Toggle("", isOn: Binding(
                                        get: { server.enabled },
                                        set: { enabled in Task { await setEnabled(server, enabled) } }
                                    ))
                                    .labelsHidden()
                                    .toggleStyle(.switch)
                                    NavigationLink {
                                        McpDetailSettingsView(kind: .server(server))
                                    } label: {
                                        Text("Open")
                                    }
                                    .buttonStyle(.sandwalk(.normal))
                                    Button {
                                        Task { await remove(server) }
                                    } label: {
                                        Image(systemName: "trash")
                                    }
                                    .buttonStyle(.sandwalk(.destructive))
                                }
                                .disabled(busy)
                            }
                        }
                    }
                }

                HStack {
                    Button("Add custom") { showAdd = true }
                        .buttonStyle(.sandwalk(.normal))
                    Spacer()
                    Button("Refresh") { Task { await reload() } }
                        .buttonStyle(.sandwalk(.normal))
                        .disabled(busy)
                }
                .padding(.horizontal, 18)
                .padding(.top, 8)

                if let status {
                    Text(status)
                        .font(.sandwalk(11.5))
                        .foregroundStyle(.secondary)
                        .padding(.horizontal, 18)
                        .padding(.top, 8)
                }
                AgentPaneError(message: error)
            }
            .padding(.top, 4)
            .task { await reload() }
            .sheet(isPresented: $showAdd) {
                VStack(alignment: .leading, spacing: 12) {
                    Text("Add stdio MCP server").font(.headline)
                    TextField("Name", text: $newName)
                    TextField("Command", text: $newCommand)
                    HStack {
                        Spacer()
                        Button("Cancel") { showAdd = false }
                        Button("Create") { Task { await create() } }
                            .keyboardShortcut(.defaultAction)
                            .disabled(newName.isEmpty || newCommand.isEmpty)
                    }
                }
                .padding(20)
                .frame(width: 380)
            }
            .sheet(isPresented: Binding(
                get: { connectingId != nil },
                set: { if !$0 { connectingId = nil } }
            )) {
                VStack(alignment: .leading, spacing: 12) {
                    Text("Connect with API key").font(.headline)
                    SecureField("API key", text: $connectKey)
                    HStack {
                        Spacer()
                        Button("Cancel") { connectingId = nil }
                        Button("Connect") {
                            Task { await connectCatalog() }
                        }
                        .keyboardShortcut(.defaultAction)
                        .disabled(connectKey.isEmpty)
                    }
                }
                .padding(20)
                .frame(width: 360)
            }
        }
    }

    private func catalogSublabel(_ entry: McpCatalogEntryDTO) -> String {
        var parts: [String] = []
        if entry.connected == true {
            parts.append("Connected")
        } else {
            parts.append("Not connected")
        }
        if let count = entry.toolCount, count > 0 {
            parts.append("\(count) tools")
        }
        let desc = entry.description.trimmingCharacters(in: .whitespacesAndNewlines)
        if !desc.isEmpty {
            parts.append(desc)
        }
        return parts.joined(separator: " · ")
    }

    @ViewBuilder
    private func catalogTrailing(_ entry: McpCatalogEntryDTO) -> some View {
        if entry.connected == true {
            Button("Disconnect") {
                Task { await disconnect(entry) }
            }
            .buttonStyle(.sandwalk(.destructive))
            .disabled(busy)
        } else if entry.preferredAuth == "oauth" || entry.authMode == "oauth" {
            Text("OAuth in Web UI")
                .font(.sandwalk(11))
                .foregroundStyle(.secondary)
        } else {
            Button("Connect") {
                connectingId = entry.id
                connectKey = ""
            }
            .buttonStyle(.sandwalk(.normal))
            .disabled(busy)
        }
    }

    @MainActor
    private func reload() async {
        busy = true
        error = nil
        defer { busy = false }
        do {
            async let s = SandwalkAPIClient.listMcpServers()
            async let c = SandwalkAPIClient.listMcpCatalog()
            servers = try await s
            catalog = try await c
        } catch {
            self.error = error.localizedDescription
        }
    }

    @MainActor
    private func setEnabled(_ server: McpServerDTO, _ enabled: Bool) async {
        busy = true
        defer { busy = false }
        do {
            let updated = try await SandwalkAPIClient.setMcpServerEnabled(id: server.id, enabled: enabled)
            if let idx = servers.firstIndex(where: { $0.id == server.id }) {
                servers[idx] = updated
            }
        } catch {
            self.error = error.localizedDescription
        }
    }

    @MainActor
    private func remove(_ server: McpServerDTO) async {
        busy = true
        defer { busy = false }
        do {
            try await SandwalkAPIClient.deleteMcpServer(id: server.id)
            servers.removeAll { $0.id == server.id }
        } catch {
            self.error = error.localizedDescription
        }
    }

    @MainActor
    private func create() async {
        busy = true
        defer { busy = false }
        do {
            _ = try await SandwalkAPIClient.createMcpServer([
                "name": newName,
                "transport": "stdio",
                "command": newCommand,
                "args": [] as [String],
                "enabled": true,
            ])
            showAdd = false
            newName = ""
            newCommand = ""
            await reload()
        } catch {
            self.error = error.localizedDescription
        }
    }

    @MainActor
    private func connectCatalog() async {
        guard let id = connectingId else { return }
        busy = true
        defer { busy = false }
        do {
            _ = try await SandwalkAPIClient.connectMcpCatalog(id: id, apiKey: connectKey)
            connectingId = nil
            status = "Connected \(id)."
            await reload()
        } catch {
            self.error = error.localizedDescription
        }
    }

    @MainActor
    private func disconnect(_ entry: McpCatalogEntryDTO) async {
        busy = true
        defer { busy = false }
        do {
            try await SandwalkAPIClient.disconnectMcpCatalog(id: entry.id)
            await reload()
        } catch {
            self.error = error.localizedDescription
        }
    }
}

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
