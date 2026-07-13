import SwiftUI

struct ToolsSettingsView: View {
    @State private var tools: [ToolSummaryDTO] = []
    @State private var search = ""
    @State private var error: String?
    @State private var busy = false

    var filtered: [ToolSummaryDTO] {
        let q = search.trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
        guard !q.isEmpty else { return tools }
        return tools.filter {
            $0.id.lowercased().contains(q)
                || $0.name.lowercased().contains(q)
                || $0.category.lowercased().contains(q)
                || $0.description.lowercased().contains(q)
        }
    }

    var body: some View {
        AgentAPIGate {
            VStack(alignment: .leading, spacing: 0) {
                AgentSearchField(text: $search)
                SettingsSectionHeader(
                    "TOOLS",
                    subtitle: "Enable/disable registry tools · \(filtered.count) shown"
                )
                SettingsListGroup {
                    if filtered.isEmpty {
                        SettingsRow(label: busy ? "Loading…" : "No tools", isLast: true) {
                            EmptyView()
                        }
                    } else {
                        ForEach(Array(filtered.enumerated()), id: \.element.id) { index, tool in
                            SettingsRow(
                                label: tool.name,
                                sublabel: "\(tool.category) · \(tool.id)",
                                isLast: index == filtered.count - 1
                            ) {
                                Toggle("", isOn: Binding(
                                    get: { tool.enabled },
                                    set: { enabled in Task { await setEnabled(tool, enabled) } }
                                ))
                                .labelsHidden()
                                .toggleStyle(.switch)
                                .disabled(busy)
                            }
                        }
                    }
                }
                HStack {
                    Spacer()
                    Button("Refresh") { Task { await reload() } }
                        .buttonStyle(.sandwalk(.normal))
                        .disabled(busy)
                }
                .padding(.horizontal, 18)
                .padding(.top, 10)
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
            tools = try await SandwalkAPIClient.listTools().data
        } catch {
            self.error = error.localizedDescription
        }
    }

    @MainActor
    private func setEnabled(_ tool: ToolSummaryDTO, _ enabled: Bool) async {
        busy = true
        defer { busy = false }
        do {
            let updated = try await SandwalkAPIClient.setToolEnabled(id: tool.id, enabled: enabled)
            if let idx = tools.firstIndex(where: { $0.id == tool.id }) {
                tools[idx] = updated
            }
        } catch {
            self.error = error.localizedDescription
        }
    }
}
