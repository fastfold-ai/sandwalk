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

    private var catalogById: [String: McpCatalogEntryDTO] {
        Dictionary(uniqueKeysWithValues: catalog.map { ($0.id, $0) })
    }

    /// Every installed server (seeded catalog + custom) — mirrors local-web.
    private var installedServers: [McpServerDTO] {
        let q = search.trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
        guard !q.isEmpty else { return servers }
        return servers.filter { server in
            server.name.lowercased().contains(q)
                || server.id.lowercased().contains(q)
                || (server.catalogId?.lowercased().contains(q) ?? false)
                || (server.url?.lowercased().contains(q) ?? false)
                || (server.command?.lowercased().contains(q) ?? false)
        }
    }

    /// Catalog templates not currently installed (typically user-removed).
    private var suggestedCatalog: [McpCatalogEntryDTO] {
        let base = catalog.filter { entry in
            let sid = entry.serverId?.trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
            return sid.isEmpty
        }
        let q = search.trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
        guard !q.isEmpty else { return base }
        return base.filter {
            $0.name.lowercased().contains(q)
                || $0.description.lowercased().contains(q)
                || $0.id.lowercased().contains(q)
        }
    }

    var body: some View {
        AgentAPIGate {
            VStack(alignment: .leading, spacing: 0) {
                WebUIManagementCallout(topic: "MCPs", path: "mcp")

                AgentSearchField(text: $search)

                SettingsSectionHeader(
                    "INSTALLED",
                    subtitle: "\(installedServers.count) servers from ~/.sandwalk/mcp.json"
                )
                SettingsListGroup {
                    if installedServers.isEmpty {
                        SettingsRow(
                            label: busy ? "Loading…" : "No MCP servers installed",
                            isLast: true
                        ) {
                            Button("Add custom") { showAdd = true }
                                .buttonStyle(.sandwalk(.normal))
                        }
                    } else {
                        ForEach(Array(installedServers.enumerated()), id: \.element.id) { index, server in
                            SettingsRow(
                                label: server.name,
                                sublabel: installedSublabel(server),
                                isLast: index == installedServers.count - 1
                            ) {
                                HStack(spacing: 6) {
                                    installedTrailing(server)
                                    installedOpenLink(server)
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

                if !suggestedCatalog.isEmpty {
                    SettingsSectionHeader(
                        "SUGGESTED",
                        subtitle: "\(suggestedCatalog.count) catalog templates you can add back"
                    )
                    SettingsListGroup {
                        ForEach(Array(suggestedCatalog.enumerated()), id: \.element.id) { index, entry in
                            SettingsRow(
                                label: entry.name,
                                sublabel: suggestedSublabel(entry),
                                isLast: index == suggestedCatalog.count - 1
                            ) {
                                HStack(spacing: 8) {
                                    Button("Add") {
                                        Task { await installCatalog(entry) }
                                    }
                                    .buttonStyle(.sandwalk(.normal))
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

    private func catalogId(of server: McpServerDTO) -> String? {
        let cid = server.catalogId?.trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
        return cid.isEmpty ? nil : cid
    }

    private func catalogEntry(for server: McpServerDTO) -> McpCatalogEntryDTO? {
        guard let cid = catalogId(of: server) else { return nil }
        return catalogById[cid]
    }

    private func needsAuth(_ server: McpServerDTO) -> Bool {
        if let entry = catalogEntry(for: server) {
            return entry.configured != true
        }
        // Custom remotes without credentials.
        if server.transport == "stdio" { return false }
        if server.headersConfigured == true { return false }
        return true
    }

    private func installedSublabel(_ server: McpServerDTO) -> String {
        var parts: [String] = [server.transport]
        if catalogId(of: server) != nil {
            parts.append("catalog")
        }
        if needsAuth(server) {
            parts.append("needs auth")
        } else if server.enabled {
            if let count = server.toolCount, count > 0 {
                parts.append("Connected (\(count))")
            } else if let entry = catalogEntry(for: server),
                      let count = entry.toolCount,
                      count > 0 {
                parts.append("Connected (\(count))")
            } else {
                parts.append("enabled")
            }
        } else {
            parts.append("disabled")
        }
        if let url = server.url, !url.isEmpty {
            parts.append(url)
        } else if let command = server.command, !command.isEmpty {
            parts.append(command)
        }
        return parts.joined(separator: " · ")
    }

    private func suggestedSublabel(_ entry: McpCatalogEntryDTO) -> String {
        let desc = entry.description.trimmingCharacters(in: .whitespacesAndNewlines)
        if desc.isEmpty { return entry.id }
        return desc
    }

    @ViewBuilder
    private func installedTrailing(_ server: McpServerDTO) -> some View {
        if let entry = catalogEntry(for: server) {
            if needsAuth(server) {
                catalogConnectControls(entry)
            } else {
                Toggle("", isOn: Binding(
                    get: { server.enabled },
                    set: { enabled in Task { await setCatalogEnabled(entry, enabled) } }
                ))
                .labelsHidden()
                .toggleStyle(.switch)
            }
        } else if needsAuth(server) {
            Text("Connect in Web UI")
                .font(.sandwalk(11))
                .foregroundStyle(.secondary)
        } else {
            Toggle("", isOn: Binding(
                get: { server.enabled },
                set: { enabled in Task { await setEnabled(server, enabled) } }
            ))
            .labelsHidden()
            .toggleStyle(.switch)
        }
    }

    @ViewBuilder
    private func catalogConnectControls(_ entry: McpCatalogEntryDTO) -> some View {
        if entry.preferredAuth == "oauth" || entry.authMode == "oauth" {
            Text("OAuth in Web UI")
                .font(.sandwalk(11))
                .foregroundStyle(.secondary)
        } else {
            Button("Connect") {
                connectingId = entry.id
                connectKey = ""
            }
            .buttonStyle(.sandwalk(.normal))
        }
    }

    @ViewBuilder
    private func installedOpenLink(_ server: McpServerDTO) -> some View {
        if let entry = catalogEntry(for: server) {
            NavigationLink {
                McpDetailSettingsView(kind: .catalog(entry))
            } label: {
                Text("Open")
            }
            .buttonStyle(.sandwalk(.normal))
        } else {
            NavigationLink {
                McpDetailSettingsView(kind: .server(server))
            } label: {
                Text("Open")
            }
            .buttonStyle(.sandwalk(.normal))
        }
    }
}
