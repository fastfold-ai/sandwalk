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

    var filteredServers: [McpServerDTO] {
        let q = search.trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
        guard !q.isEmpty else { return servers }
        return servers.filter { $0.name.lowercased().contains(q) || $0.id.lowercased().contains(q) }
    }

    var body: some View {
        AgentAPIGate {
            VStack(alignment: .leading, spacing: 0) {
                AgentSearchField(text: $search)
                SettingsSectionHeader("SERVERS", subtitle: "\(filteredServers.count) configured")
                SettingsListGroup {
                    if filteredServers.isEmpty {
                        SettingsRow(label: busy ? "Loading…" : "No MCP servers", isLast: true) {
                            Button("Add") { showAdd = true }
                                .buttonStyle(.sandwalk(.normal))
                        }
                    } else {
                        ForEach(Array(filteredServers.enumerated()), id: \.element.id) { index, server in
                            SettingsRow(
                                label: server.name,
                                sublabel: "\(server.transport)\(server.enabled ? "" : " · disabled")",
                                isLast: index == filteredServers.count - 1
                            ) {
                                HStack(spacing: 6) {
                                    Toggle("", isOn: Binding(
                                        get: { server.enabled },
                                        set: { enabled in Task { await setEnabled(server, enabled) } }
                                    ))
                                    .labelsHidden()
                                    .toggleStyle(.switch)
                                    Button {
                                        Task { await validate(server) }
                                    } label: {
                                        Image(systemName: "checkmark.seal")
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

                SettingsSectionHeader("CATALOG", subtitle: "API-key connect (OAuth deferred)")
                SettingsListGroup {
                    let entries = catalog.filter { entry in
                        let q = search.trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
                        guard !q.isEmpty else { return true }
                        return entry.name.lowercased().contains(q)
                    }
                    if entries.isEmpty {
                        SettingsRow(label: "No catalog entries", isLast: true) { EmptyView() }
                    } else {
                        ForEach(Array(entries.enumerated()), id: \.element.id) { index, entry in
                            SettingsRow(
                                label: entry.name,
                                sublabel: entry.connected == true
                                    ? "Connected"
                                    : (entry.description),
                                isLast: index == entries.count - 1
                            ) {
                                if entry.connected == true {
                                    Button("Disconnect") {
                                        Task { await disconnect(entry) }
                                    }
                                    .buttonStyle(.sandwalk(.destructive))
                                    .disabled(busy)
                                } else if entry.preferredAuth == "oauth" || entry.authMode == "oauth" {
                                    Text("OAuth")
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
                        }
                    }
                }

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
    private func validate(_ server: McpServerDTO) async {
        busy = true
        defer { busy = false }
        do {
            let result = try await SandwalkAPIClient.validateMcpServer(id: server.id)
            status = result.message ?? (result.ok == true ? "Valid (\(result.toolCount ?? 0) tools)" : "Failed")
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
