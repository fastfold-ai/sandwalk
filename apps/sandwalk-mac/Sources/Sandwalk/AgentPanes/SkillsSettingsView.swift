import SwiftUI

struct SkillsSettingsView: View {
    @State private var skills: [AgentSkillDTO] = []
    @State private var search = ""
    @State private var source = ""
    @State private var error: String?
    @State private var status: String?
    @State private var busy = false

    var filtered: [AgentSkillDTO] {
        let q = search.trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
        guard !q.isEmpty else { return skills }
        return skills.filter {
            $0.name.lowercased().contains(q) || $0.description.lowercased().contains(q)
        }
    }

    var body: some View {
        AgentAPIGate {
            VStack(alignment: .leading, spacing: 0) {
                SettingsSectionHeader("INSTALL", subtitle: "GitHub / skills.sh source string")
                SettingsListGroup {
                    SettingsRow(label: "Source", sublabel: "e.g. owner/repo or skills URL", isLast: true) {
                        HStack {
                            TextField("source", text: $source)
                                .frame(width: 220)
                            Button("Install") { Task { await install() } }
                                .buttonStyle(.sandwalk(.primary))
                                .disabled(busy || source.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
                        }
                    }
                }

                if let status {
                    Text(status)
                        .font(.sandwalk(11.5))
                        .foregroundStyle(.secondary)
                        .padding(.horizontal, 18)
                        .padding(.top, 8)
                        .padding(.bottom, 4)
                }

                AgentSearchField(text: $search)
                SettingsSectionHeader("INSTALLED", subtitle: "\(filtered.count) skills")
                SettingsListGroup {
                    if filtered.isEmpty {
                        SettingsRow(label: busy ? "Loading…" : "No skills installed", isLast: true) {
                            EmptyView()
                        }
                    } else {
                        ForEach(Array(filtered.enumerated()), id: \.element.name) { index, skill in
                            SettingsRow(
                                label: skill.name,
                                sublabel: skill.description,
                                isLast: index == filtered.count - 1
                            ) {
                                HStack(spacing: 8) {
                                    Toggle("", isOn: Binding(
                                        get: { skill.enabled },
                                        set: { enabled in Task { await setEnabled(skill, enabled) } }
                                    ))
                                    .labelsHidden()
                                    .toggleStyle(.switch)
                                    Button {
                                        Task { await remove(skill) }
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

                AgentPaneError(message: error)
            }
            .padding(.top, 4)
            .task { await reload() }
        }
    }

    @MainActor
    private func reload() async {
        busy = true
        error = nil
        defer { busy = false }
        do {
            skills = try await SandwalkAPIClient.listSkills()
        } catch {
            self.error = error.localizedDescription
        }
    }

    @MainActor
    private func setEnabled(_ skill: AgentSkillDTO, _ enabled: Bool) async {
        busy = true
        defer { busy = false }
        do {
            let updated = try await SandwalkAPIClient.setSkillEnabled(name: skill.name, enabled: enabled)
            if let idx = skills.firstIndex(where: { $0.name == skill.name }) {
                skills[idx] = updated
            }
        } catch {
            self.error = error.localizedDescription
        }
    }

    @MainActor
    private func remove(_ skill: AgentSkillDTO) async {
        busy = true
        defer { busy = false }
        do {
            try await SandwalkAPIClient.removeSkill(name: skill.name)
            skills.removeAll { $0.name == skill.name }
            status = "Removed \(skill.name)."
        } catch {
            self.error = error.localizedDescription
        }
    }

    @MainActor
    private func install() async {
        let src = source.trimmingCharacters(in: .whitespacesAndNewlines)
        busy = true
        defer { busy = false }
        do {
            let installed = try await SandwalkAPIClient.installSkill(source: src)
            status = "Installed: \(installed.joined(separator: ", "))"
            source = ""
            await reload()
        } catch {
            self.error = error.localizedDescription
        }
    }
}
