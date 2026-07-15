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
