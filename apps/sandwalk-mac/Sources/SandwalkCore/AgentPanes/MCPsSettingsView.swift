import SwiftUI

struct MCPsSettingsView: View {
    @State var servers: [McpServerDTO] = []
    @State var catalog: [McpCatalogEntryDTO] = []
    @State var search = ""
    @State var error: String?
    @State var status: String?
    @State var busy = false
    @State var showAdd = false
    @State var newName = ""
    @State var newCommand = ""
    @State var connectKey = ""
    @State var connectingId: String?

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
}
