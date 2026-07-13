import SwiftUI

struct DatasetsSettingsView: View {
    @State private var datasets: [DatasetSummaryDTO] = []
    @State private var search = ""
    @State private var error: String?
    @State private var status: String?
    @State private var busy = false
    @State private var installing: String?

    var filtered: [DatasetSummaryDTO] {
        let q = search.trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
        guard !q.isEmpty else { return datasets }
        return datasets.filter {
            $0.id.lowercased().contains(q) || $0.description.lowercased().contains(q)
        }
    }

    var body: some View {
        AgentAPIGate {
            VStack(alignment: .leading, spacing: 0) {
                AgentSearchField(text: $search)
                SettingsSectionHeader("DATASETS", subtitle: "Install catalog datasets")
                SettingsListGroup {
                    if filtered.isEmpty {
                        SettingsRow(label: busy ? "Loading…" : "No datasets", isLast: true) {
                            EmptyView()
                        }
                    } else {
                        ForEach(Array(filtered.enumerated()), id: \.element.id) { index, ds in
                            SettingsRow(
                                label: ds.id,
                                sublabel: "\(ds.status) · \(ds.sizeDisplay ?? ds.description)",
                                isLast: index == filtered.count - 1
                            ) {
                                if ds.status == "complete" {
                                    Text("Installed")
                                        .font(.sandwalk(11))
                                        .foregroundStyle(.secondary)
                                } else {
                                    Button(installing == ds.id ? "Installing…" : "Install") {
                                        Task { await install(ds) }
                                    }
                                    .buttonStyle(.sandwalk(.primary))
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
        }
    }

    @MainActor
    private func reload() async {
        busy = true
        error = nil
        defer { busy = false }
        do {
            datasets = try await SandwalkAPIClient.listDatasets()
        } catch {
            self.error = error.localizedDescription
        }
    }

    @MainActor
    private func install(_ ds: DatasetSummaryDTO) async {
        busy = true
        installing = ds.id
        defer {
            busy = false
            installing = nil
        }
        do {
            let result = try await SandwalkAPIClient.installDataset(id: ds.id)
            status = result.summary ?? "Installed \(ds.id)."
            await reload()
        } catch {
            self.error = error.localizedDescription
        }
    }
}
