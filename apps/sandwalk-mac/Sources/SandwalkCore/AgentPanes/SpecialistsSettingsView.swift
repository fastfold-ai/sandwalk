import SwiftUI

/// List + create/edit specialists (same `/v1/specialists` store as web + CLI).
struct SpecialistsSettingsView: View {
    @State private var specialists: [SpecialistDTO] = []
    @State private var search = ""
    @State private var error: String?
    @State private var status: String?
    @State private var busy = false

    @Environment(\.sandwalkTheme) private var theme

    private var filtered: [SpecialistDTO] {
        let q = search.trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
        guard !q.isEmpty else { return specialists }
        return specialists.filter {
            $0.name.lowercased().contains(q)
                || $0.slug.lowercased().contains(q)
                || ($0.description ?? "").lowercased().contains(q)
        }
    }

    var body: some View {
        AgentAPIGate {
            VStack(alignment: .leading, spacing: 0) {
                WebUIManagementCallout(topic: "specialists", path: "specialists")

                HStack {
                    Spacer(minLength: 0)
                    NavigationLink {
                        SpecialistDetailSettingsView(specialistId: nil)
                    } label: {
                        Label("New Specialist", systemImage: "plus")
                    }
                    .buttonStyle(.sandwalk(.primary))
                }
                .padding(.horizontal, 18)
                .padding(.bottom, 8)

                if let status {
                    Text(status)
                        .font(.sandwalk(11.5))
                        .foregroundStyle(theme.textSecondary)
                        .padding(.horizontal, 18)
                        .padding(.bottom, 4)
                }

                AgentSearchField(text: $search)
                SettingsSectionHeader(
                    "SPECIALISTS",
                    subtitle: "\(filtered.count) profiles — tools + skills + MCPs + instructions"
                )
                SettingsListGroup {
                    if filtered.isEmpty {
                        SettingsRow(
                            label: busy ? "Loading…" : "No specialists yet",
                            sublabel: "Create one here or in the web dashboard.",
                            isLast: true
                        ) {
                            EmptyView()
                        }
                    } else {
                        ForEach(Array(filtered.enumerated()), id: \.element.id) { index, item in
                            SettingsRow(
                                label: item.name,
                                sublabel: specialistSublabel(item),
                                isLast: index == filtered.count - 1
                            ) {
                                HStack(spacing: 8) {
                                    Toggle(
                                        "",
                                        isOn: Binding(
                                            get: { item.enabled },
                                            set: { enabled in
                                                Task { await setEnabled(item, enabled) }
                                            }
                                        )
                                    )
                                    .labelsHidden()
                                    .toggleStyle(.switch)
                                    .disabled(busy)

                                    NavigationLink {
                                        SpecialistDetailSettingsView(specialistId: item.id)
                                    } label: {
                                        Text("Edit")
                                    }
                                    .buttonStyle(.sandwalk(.normal))

                                    Button {
                                        Task { await remove(item) }
                                    } label: {
                                        Image(systemName: "trash")
                                    }
                                    .buttonStyle(.sandwalk(.destructive))
                                    .disabled(busy)
                                }
                            }
                        }
                    }
                }
                AgentPaneError(message: error)
            }
            .padding(.top, 4)
            .task { await reload() }
            .onAppear { Task { await reload() } }
        }
    }

    private func specialistSublabel(_ item: SpecialistDTO) -> String {
        let tools = item.toolNames.count
        let skills = item.skillNames.count
        let mcps = item.mcpServerIds.count + item.mcpCatalogIds.count
        let parts = [
            item.slug,
            "\(tools) tool\(tools == 1 ? "" : "s")",
            "\(skills) skill\(skills == 1 ? "" : "s")",
            "\(mcps) MCP\(mcps == 1 ? "" : "s")",
            item.enabled ? nil : "disabled",
        ].compactMap { $0 }
        return parts.joined(separator: " · ")
    }

    @MainActor
    private func reload() async {
        busy = true
        error = nil
        defer { busy = false }
        do {
            specialists = try await SandwalkAPIClient.listSpecialists()
                .sorted { $0.name.localizedCaseInsensitiveCompare($1.name) == .orderedAscending }
        } catch {
            self.error = error.localizedDescription
        }
    }

    @MainActor
    private func setEnabled(_ item: SpecialistDTO, _ enabled: Bool) async {
        busy = true
        defer { busy = false }
        do {
            let updated = try await SandwalkAPIClient.updateSpecialist(
                id: item.id,
                body: ["enabled": enabled]
            )
            if let idx = specialists.firstIndex(where: { $0.id == item.id }) {
                specialists[idx] = updated
            }
        } catch {
            self.error = error.localizedDescription
            await reload()
        }
    }

    @MainActor
    private func remove(_ item: SpecialistDTO) async {
        busy = true
        defer { busy = false }
        do {
            try await SandwalkAPIClient.deleteSpecialist(id: item.id)
            specialists.removeAll { $0.id == item.id }
            status = "Deleted \(item.name)."
        } catch {
            self.error = error.localizedDescription
        }
    }
}

/// Create or edit a specialist profile.
struct SpecialistDetailSettingsView: View {
    let specialistId: String?

    @Environment(\.dismiss) private var dismiss
    @Environment(\.sandwalkTheme) private var theme

    @State private var name = ""
    @State private var slug = ""
    @State private var slugTouched = false
    @State private var descriptionText = ""
    @State private var instructions = ""
    @State private var color = "ink"
    @State private var icon = "git-branch"
    @State private var enabled = true
    @State private var selectedTools: Set<String> = []
    @State private var selectedSkills: Set<String> = []
    @State private var selectedMcpServers: Set<String> = []
    @State private var selectedMcpCatalogs: Set<String> = []

    @State private var catalogTools: [ToolSummaryDTO] = []
    @State private var skills: [AgentSkillDTO] = []
    @State private var mcpServers: [McpServerDTO] = []
    @State private var mcpCatalog: [McpCatalogEntryDTO] = []
    @State private var toolFilter = ""
    @State private var skillFilter = ""
    @State private var mcpFilter = ""
    @State private var didSeedCoreTools = false

    @State private var error: String?
    @State private var status: String?
    @State private var busy = false

    private var isCreate: Bool { specialistId == nil }

    private var colors: [String] {
        ["ink", "blue", "teal", "green", "amber", "orange", "red", "violet", "pink"]
    }

    private var icons: [String] {
        [
            "git-branch", "agent", "sparkles", "flask", "dna", "microscope",
            "target", "atom", "database", "code", "book", "globe",
        ]
    }

    private var filteredCatalogTools: [ToolSummaryDTO] {
        let q = toolFilter.trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
        let base = catalogTools.sorted { $0.name.localizedCaseInsensitiveCompare($1.name) == .orderedAscending }
        guard !q.isEmpty else { return base }
        return base.filter {
            $0.id.lowercased().contains(q)
                || $0.name.lowercased().contains(q)
                || $0.category.lowercased().contains(q)
                || $0.description.lowercased().contains(q)
        }
    }

    private var coreTools: [ToolSummaryDTO] {
        filteredCatalogTools.filter(\.isCore)
    }

    private var extraTools: [ToolSummaryDTO] {
        filteredCatalogTools.filter { !$0.isCore }
    }

    private var filteredSkills: [AgentSkillDTO] {
        let q = skillFilter.trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
        let base = skills.sorted { $0.name.localizedCaseInsensitiveCompare($1.name) == .orderedAscending }
        guard !q.isEmpty else { return base }
        return base.filter {
            $0.name.lowercased().contains(q) || $0.description.lowercased().contains(q)
        }
    }

    private var filteredMcpServers: [McpServerDTO] {
        let q = mcpFilter.trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
        let customs = mcpServers.filter {
            ($0.catalogId ?? "").trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
        }
        guard !q.isEmpty else { return customs }
        return customs.filter {
            $0.name.lowercased().contains(q) || $0.id.lowercased().contains(q)
        }
    }

    private var filteredMcpCatalog: [McpCatalogEntryDTO] {
        let q = mcpFilter.trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
        guard !q.isEmpty else { return mcpCatalog }
        return mcpCatalog.filter {
            $0.name.lowercased().contains(q) || $0.description.lowercased().contains(q)
        }
    }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 0) {
                SettingsSectionHeader(
                    isCreate ? "NEW SPECIALIST" : "EDIT SPECIALIST",
                    subtitle: "Runs use only this profile’s tools, skills, MCPs, and instructions."
                )

                SettingsListGroup {
                    SettingsRow(label: "Name", isLast: false) {
                        TextField("Protein Designer", text: $name)
                            .frame(minWidth: 180, maxWidth: 280)
                            .onChange(of: name) { _, next in
                                if isCreate, !slugTouched {
                                    slug = Self.slugify(next)
                                }
                            }
                    }
                    SettingsRow(label: "Slug", sublabel: "URL-safe id", isLast: false) {
                        TextField("protein-designer", text: $slug)
                            .frame(minWidth: 180, maxWidth: 280)
                            .onChange(of: slug) { _, _ in
                                if isCreate { slugTouched = true }
                            }
                    }
                    SettingsRow(label: "Enabled", isLast: false) {
                        Toggle("", isOn: $enabled)
                            .labelsHidden()
                            .toggleStyle(.switch)
                    }
                    SettingsRow(label: "Color", isLast: false) {
                        Picker("", selection: $color) {
                            ForEach(colors, id: \.self) { Text($0).tag($0) }
                        }
                        .labelsHidden()
                        .frame(width: 140)
                    }
                    SettingsRow(label: "Icon", isLast: true) {
                        Picker("", selection: $icon) {
                            ForEach(icons, id: \.self) { Text($0).tag($0) }
                        }
                        .labelsHidden()
                        .frame(width: 160)
                    }
                }

                SettingsSectionHeader("DESCRIPTION", subtitle: "Shown in pickers")
                SettingsListGroup {
                    SettingsRow(label: "Summary", isLast: true) {
                        TextField("Short description", text: $descriptionText)
                            .frame(minWidth: 220, maxWidth: 360)
                    }
                }

                SettingsSectionHeader("INSTRUCTIONS", subtitle: "Appended to the system prompt")
                SettingsListGroup {
                    VStack(alignment: .leading, spacing: 8) {
                        TextEditor(text: $instructions)
                            .font(.sandwalk(12.5))
                            .frame(minHeight: 120, maxHeight: 220)
                            .scrollContentBackground(.hidden)
                        Text("\(instructions.count) characters")
                            .font(.sandwalk(11))
                            .foregroundStyle(theme.textTertiary)
                    }
                    .padding(14)
                }

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

                HStack(spacing: 8) {
                    Button(busy ? "Saving…" : (isCreate ? "Create" : "Save")) {
                        Task { await save() }
                    }
                    .buttonStyle(.sandwalk(.primary))
                    .disabled(busy || name.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)

                    if !isCreate {
                        Button("Delete") {
                            Task { await deleteCurrent() }
                        }
                        .buttonStyle(.sandwalk(.destructive))
                        .disabled(busy)
                    }

                    Spacer()
                }
                .padding(.horizontal, 18)
                .padding(.top, 12)

                if let status {
                    Text(status)
                        .font(.sandwalk(11.5))
                        .foregroundStyle(theme.textSecondary)
                        .padding(.horizontal, 18)
                        .padding(.top, 8)
                }

                AgentPaneError(message: error)
            }
            .frame(maxWidth: 720, alignment: .topLeading)
            .frame(maxWidth: .infinity, alignment: .top)
            .padding(.top, 4)
            .padding(.bottom, 36)
        }
        .scrollContentBackground(.hidden)
        .background(theme.windowBg)
        .navigationTitle(isCreate ? "New Specialist" : (name.isEmpty ? "Specialist" : name))
        .task { await load() }
    }

    @MainActor
    private func load() async {
        busy = true
        error = nil
        defer { busy = false }
        do {
            async let toolsTask = SandwalkAPIClient.listTools()
            async let skillsTask = SandwalkAPIClient.listSkills()
            async let serversTask = SandwalkAPIClient.listMcpServers()
            async let catalogTask = SandwalkAPIClient.listMcpCatalog()
            catalogTools = try await toolsTask.data
            skills = try await skillsTask
            mcpServers = try await serversTask
            mcpCatalog = try await catalogTask

            if let specialistId {
                let item = try await SandwalkAPIClient.getSpecialist(id: specialistId)
                apply(item)
            } else {
                seedCoreToolsIfNeeded()
            }
        } catch {
            self.error = error.localizedDescription
        }
    }

    private func apply(_ item: SpecialistDTO) {
        name = item.name
        slug = item.slug
        slugTouched = true
        descriptionText = item.description ?? ""
        instructions = item.instructions ?? ""
        color = item.color.isEmpty ? "ink" : item.color
        icon = item.icon.isEmpty ? "git-branch" : item.icon
        enabled = item.enabled
        selectedTools = Set(item.toolNames)
        selectedSkills = Set(item.skillNames)
        selectedMcpServers = Set(item.mcpServerIds)
        selectedMcpCatalogs = Set(item.mcpCatalogIds)
        didSeedCoreTools = true
    }

    private func seedCoreToolsIfNeeded() {
        guard isCreate, !didSeedCoreTools, selectedTools.isEmpty, !catalogTools.isEmpty else { return }
        selectedTools = Set(catalogTools.filter(\.isCore).map(\.id))
        didSeedCoreTools = true
    }

    private func setTierTools(_ tools: [ToolSummaryDTO], enabled: Bool) {
        if enabled {
            for tool in tools { selectedTools.insert(tool.id) }
        } else {
            for tool in tools { selectedTools.remove(tool.id) }
        }
    }

    @ViewBuilder
    private func toolGroupRows(label: String, tools: [ToolSummaryDTO], trailingEmpty: Bool) -> some View {
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

    @MainActor
    private func save() async {
        let trimmedName = name.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmedName.isEmpty else {
            error = "Name is required."
            return
        }
        let trimmedSlug = slug.trimmingCharacters(in: .whitespacesAndNewlines)
        let desc = descriptionText.trimmingCharacters(in: .whitespacesAndNewlines)
        let instr = instructions.trimmingCharacters(in: .whitespacesAndNewlines)

        busy = true
        defer { busy = false }
        do {
            if let specialistId {
                var body: [String: Any] = [
                    "name": trimmedName,
                    "slug": trimmedSlug.isEmpty ? Self.slugify(trimmedName) : trimmedSlug,
                    "color": color,
                    "icon": icon,
                    "enabled": enabled,
                    "toolNames": Array(selectedTools).sorted(),
                    "skillNames": Array(selectedSkills).sorted(),
                    "mcpServerIds": Array(selectedMcpServers).sorted(),
                    "mcpCatalogIds": Array(selectedMcpCatalogs).sorted(),
                    "clearDescription": desc.isEmpty,
                    "clearInstructions": instr.isEmpty,
                ]
                if !desc.isEmpty { body["description"] = desc }
                if !instr.isEmpty { body["instructions"] = instr }
                let updated = try await SandwalkAPIClient.updateSpecialist(id: specialistId, body: body)
                apply(updated)
                status = "Saved."
                error = nil
            } else {
                var body: [String: Any] = [
                    "name": trimmedName,
                    "color": color,
                    "icon": icon,
                    "enabled": enabled,
                    "toolNames": Array(selectedTools).sorted(),
                    "skillNames": Array(selectedSkills).sorted(),
                    "mcpServerIds": Array(selectedMcpServers).sorted(),
                    "mcpCatalogIds": Array(selectedMcpCatalogs).sorted(),
                ]
                if !trimmedSlug.isEmpty { body["slug"] = trimmedSlug }
                if !desc.isEmpty { body["description"] = desc }
                if !instr.isEmpty { body["instructions"] = instr }
                _ = try await SandwalkAPIClient.createSpecialist(body)
                status = "Created."
                error = nil
                dismiss()
            }
        } catch {
            self.error = error.localizedDescription
        }
    }

    @MainActor
    private func deleteCurrent() async {
        guard let specialistId else { return }
        busy = true
        defer { busy = false }
        do {
            try await SandwalkAPIClient.deleteSpecialist(id: specialistId)
            dismiss()
        } catch {
            self.error = error.localizedDescription
        }
    }

    private static func slugify(_ value: String) -> String {
        let lowered = value.lowercased()
        let mapped = lowered.map { ch -> Character in
            if ch.isLetter || ch.isNumber { return ch }
            return "-"
        }
        let collapsed = String(mapped)
            .replacingOccurrences(of: "-+", with: "-", options: .regularExpression)
            .trimmingCharacters(in: CharacterSet(charactersIn: "-"))
        return collapsed.isEmpty ? "specialist" : collapsed
    }
}
