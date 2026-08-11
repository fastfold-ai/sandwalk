import SwiftUI

extension SpecialistDetailSettingsView {
    @ViewBuilder
    var toolsSection: some View {
        SettingsSectionHeader(
            "TOOLS",
            subtitle: "\(selectedTools.count) selected · Core are usual defaults; Extra are opt-in"
        )
        HStack(spacing: 8) {
            Button("All core") { setTierTools(coreTools, enabled: true) }
                .buttonStyle(.sandwalk(.normal))
            Button("None core") { setTierTools(coreTools, enabled: false) }
                .buttonStyle(.sandwalk(.normal))
            Button("All extra") { setTierTools(extraTools, enabled: true) }
                .buttonStyle(.sandwalk(.normal))
            Button("None extra") { setTierTools(extraTools, enabled: false) }
                .buttonStyle(.sandwalk(.normal))
            Spacer(minLength: 0)
        }
        .padding(.horizontal, 18)
        .padding(.bottom, 6)
        AgentSearchField(text: $toolFilter)
        SettingsListGroup {
            if catalogTools.isEmpty {
                SettingsRow(label: busy ? "Loading tools…" : "No tools in catalog", isLast: true) {
                    EmptyView()
                }
            } else if filteredCatalogTools.isEmpty {
                SettingsRow(label: "No tools match", isLast: true) {
                    EmptyView()
                }
            } else {
                toolGroupRows(label: "Core", tools: coreTools, trailingEmpty: extraTools.isEmpty)
                toolGroupRows(label: "Extra", tools: extraTools, trailingEmpty: true)
            }
        }
    }

    @ViewBuilder
    var skillsSection: some View {
        SettingsSectionHeader(
            "SKILLS",
            subtitle: "\(selectedSkills.count) selected · only these load when this specialist is active"
        )
        AgentSearchField(text: $skillFilter)
        SettingsListGroup {
            if filteredSkills.isEmpty {
                SettingsRow(label: busy ? "Loading skills…" : "No skills match", isLast: true) {
                    EmptyView()
                }
            } else {
                ForEach(Array(filteredSkills.enumerated()), id: \.element.name) { index, skill in
                    SettingsRow(
                        label: skill.name,
                        sublabel: skill.description,
                        isLast: index == filteredSkills.count - 1
                    ) {
                        Toggle(
                            "",
                            isOn: Binding(
                                get: { selectedSkills.contains(skill.name) },
                                set: { on in
                                    if on { selectedSkills.insert(skill.name) }
                                    else { selectedSkills.remove(skill.name) }
                                }
                            )
                        )
                        .labelsHidden()
                        .toggleStyle(.switch)
                    }
                }
            }
        }
    }

    @ViewBuilder
    var mcpsSection: some View {
        SettingsSectionHeader(
            "MCPs",
            subtitle: "\(selectedMcpServers.count + selectedMcpCatalogs.count) selected"
        )
        AgentSearchField(text: $mcpFilter)
        SettingsListGroup {
            let catalogRows = filteredMcpCatalog
            let serverRows = filteredMcpServers
            if catalogRows.isEmpty && serverRows.isEmpty {
                SettingsRow(label: busy ? "Loading MCPs…" : "No MCP servers match", isLast: true) {
                    EmptyView()
                }
            } else {
                ForEach(Array(catalogRows.enumerated()), id: \.element.id) { index, entry in
                    SettingsRow(
                        label: entry.name,
                        sublabel: "catalog · \(entry.id)",
                        isLast: index == catalogRows.count - 1 && serverRows.isEmpty
                    ) {
                        Toggle(
                            "",
                            isOn: Binding(
                                get: { selectedMcpCatalogs.contains(entry.id) },
                                set: { on in
                                    if on { selectedMcpCatalogs.insert(entry.id) }
                                    else { selectedMcpCatalogs.remove(entry.id) }
                                }
                            )
                        )
                        .labelsHidden()
                        .toggleStyle(.switch)
                    }
                }
                ForEach(Array(serverRows.enumerated()), id: \.element.id) { index, server in
                    SettingsRow(
                        label: server.name,
                        sublabel: "custom · \(server.transport)",
                        isLast: index == serverRows.count - 1
                    ) {
                        Toggle(
                            "",
                            isOn: Binding(
                                get: { selectedMcpServers.contains(server.id) },
                                set: { on in
                                    if on { selectedMcpServers.insert(server.id) }
                                    else { selectedMcpServers.remove(server.id) }
                                }
                            )
                        )
                        .labelsHidden()
                        .toggleStyle(.switch)
                    }
                }
            }
        }
    }

    @ViewBuilder
    func toolGroupRows(label: String, tools: [ToolSummaryDTO], trailingEmpty: Bool) -> some View {
        if !tools.isEmpty {
            ForEach(Array(tools.enumerated()), id: \.element.id) { index, tool in
                SettingsRow(
                    label: tool.name,
                    sublabel: "\(label) · \(tool.category) · \(tool.id)",
                    isLast: trailingEmpty && index == tools.count - 1
                ) {
                    Toggle(
                        "",
                        isOn: Binding(
                            get: { selectedTools.contains(tool.id) },
                            set: { on in
                                if on { selectedTools.insert(tool.id) }
                                else { selectedTools.remove(tool.id) }
                            }
                        )
                    )
                    .labelsHidden()
                    .toggleStyle(.switch)
                }
            }
        }
    }
}
