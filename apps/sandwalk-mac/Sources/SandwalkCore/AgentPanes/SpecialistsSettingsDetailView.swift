import SwiftUI

/// Create or edit a specialist profile.
struct SpecialistDetailSettingsView: View {
    let specialistId: String?

    @Environment(\.dismiss) var dismiss
    @Environment(\.sandwalkTheme) private var theme

    @State var name = ""
    @State var slug = ""
    @State var slugTouched = false
    @State var descriptionText = ""
    @State var instructions = ""
    @State var color = "ink"
    @State var icon = "git-branch"
    @State var enabled = true
    @State var selectedTools: Set<String> = []
    @State var selectedSkills: Set<String> = []
    @State var selectedMcpServers: Set<String> = []
    @State var selectedMcpCatalogs: Set<String> = []

    @State var catalogTools: [ToolSummaryDTO] = []
    @State var skills: [AgentSkillDTO] = []
    @State var mcpServers: [McpServerDTO] = []
    @State var mcpCatalog: [McpCatalogEntryDTO] = []
    @State var toolFilter = ""
    @State var skillFilter = ""
    @State var mcpFilter = ""
    @State var didSeedCoreTools = false

    @State var error: String?
    @State var status: String?
    @State var busy = false

    var isCreate: Bool { specialistId == nil }

    private var colors: [String] {
        ["ink", "blue", "teal", "green", "amber", "orange", "red", "violet", "pink"]
    }

    private var icons: [String] {
        [
            "git-branch", "agent", "sparkles", "flask", "dna", "microscope",
            "target", "atom", "database", "code", "book", "globe",
        ]
    }

    var filteredCatalogTools: [ToolSummaryDTO] {
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

    var coreTools: [ToolSummaryDTO] {
        filteredCatalogTools.filter(\.isCore)
    }

    var extraTools: [ToolSummaryDTO] {
        filteredCatalogTools.filter { !$0.isCore }
    }

    var filteredSkills: [AgentSkillDTO] {
        let q = skillFilter.trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
        let base = skills.sorted { $0.name.localizedCaseInsensitiveCompare($1.name) == .orderedAscending }
        guard !q.isEmpty else { return base }
        return base.filter {
            $0.name.lowercased().contains(q) || $0.description.lowercased().contains(q)
        }
    }

    var filteredMcpServers: [McpServerDTO] {
        let q = mcpFilter.trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
        let customs = mcpServers.filter {
            ($0.catalogId ?? "").trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
        }
        guard !q.isEmpty else { return customs }
        return customs.filter {
            $0.name.lowercased().contains(q) || $0.id.lowercased().contains(q)
        }
    }

    var filteredMcpCatalog: [McpCatalogEntryDTO] {
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

                toolsSection
                skillsSection
                mcpsSection

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
}
