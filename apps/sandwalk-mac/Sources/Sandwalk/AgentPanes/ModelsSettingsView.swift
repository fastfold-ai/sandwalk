import SwiftUI

struct ModelsSettingsView: View {
    @State private var models: [AgentModelDTO] = []
    @State private var profiles: [ModelProfileDTO] = []
    @State private var search = ""
    @State private var error: String?
    @State private var busy = false
    @State private var showAdd = false
    @State private var newId = ""
    @State private var newLabel = ""

    var filtered: [AgentModelDTO] {
        let q = search.trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
        guard !q.isEmpty else { return models }
        return models.filter {
            $0.id.lowercased().contains(q)
                || $0.label.lowercased().contains(q)
                || $0.provider.lowercased().contains(q)
        }
    }

    var body: some View {
        AgentAPIGate {
            VStack(alignment: .leading, spacing: 0) {
                AgentSearchField(text: $search)
                SettingsSectionHeader("MODELS", subtitle: "\(filtered.count) shown")
                SettingsListGroup {
                    if filtered.isEmpty {
                        SettingsRow(label: busy ? "Loading…" : "No models", isLast: true) {
                            EmptyView()
                        }
                    } else {
                        ForEach(Array(filtered.enumerated()), id: \.element.id) { index, model in
                            SettingsRow(
                                label: model.label,
                                sublabel: "\(model.provider) · \(model.source)\(model.enabled ? "" : " · disabled")",
                                isLast: index == filtered.count - 1
                            ) {
                                Toggle("", isOn: Binding(
                                    get: { model.enabled },
                                    set: { enabled in Task { await setEnabled(model, enabled) } }
                                ))
                                .labelsHidden()
                                .toggleStyle(.switch)
                                .disabled(busy)
                            }
                        }
                    }
                }

                SettingsSectionHeader("CUSTOM", subtitle: "Add OpenAI-compatible model ids")
                SettingsListGroup {
                    SettingsRow(label: "Add custom model", sublabel: "POST /v1/models", isLast: true) {
                        Button("Add") { showAdd = true }
                            .buttonStyle(.sandwalk(.normal))
                    }
                }

                SettingsSectionHeader("PROFILES", subtitle: "\(profiles.count) endpoints")
                SettingsListGroup {
                    if profiles.isEmpty {
                        SettingsRow(label: "No profiles", isLast: true) { EmptyView() }
                    } else {
                        ForEach(Array(profiles.enumerated()), id: \.element.id) { index, profile in
                            SettingsRow(
                                label: profile.label,
                                sublabel: "\(profile.backend)\(profile.isActive == true ? " · active" : "")",
                                isLast: index == profiles.count - 1
                            ) {
                                Button("Probe") {
                                    Task { await probe(profile) }
                                }
                                .buttonStyle(.sandwalk(.normal))
                                .disabled(busy)
                            }
                        }
                    }
                }

                HStack {
                    Spacer()
                    Button(busy ? "Refreshing…" : "Refresh") {
                        Task { await reload() }
                    }
                    .buttonStyle(.sandwalk(.normal))
                    .disabled(busy)
                }
                .padding(.horizontal, 18)
                .padding(.top, 10)

                AgentPaneError(message: error)
            }
            .padding(.top, 4)
            .task { await reload() }
            .sheet(isPresented: $showAdd) {
                VStack(alignment: .leading, spacing: 12) {
                    Text("Add custom model").font(.headline)
                    TextField("Model id", text: $newId)
                    TextField("Label (optional)", text: $newLabel)
                    HStack {
                        Spacer()
                        Button("Cancel") { showAdd = false }
                        Button("Create") {
                            Task { await createCustom() }
                        }
                        .keyboardShortcut(.defaultAction)
                        .disabled(newId.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
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
            async let m = SandwalkAPIClient.listModels()
            async let p = SandwalkAPIClient.listModelProfiles()
            models = try await m
            profiles = try await p
        } catch {
            self.error = error.localizedDescription
        }
    }

    @MainActor
    private func setEnabled(_ model: AgentModelDTO, _ enabled: Bool) async {
        busy = true
        defer { busy = false }
        do {
            let updated = try await SandwalkAPIClient.setModelEnabled(id: model.id, enabled: enabled)
            if let idx = models.firstIndex(where: { $0.id == model.id }) {
                models[idx] = updated
            }
        } catch {
            self.error = error.localizedDescription
        }
    }

    @MainActor
    private func createCustom() async {
        let id = newId.trimmingCharacters(in: .whitespacesAndNewlines)
        let label = newLabel.trimmingCharacters(in: .whitespacesAndNewlines)
        busy = true
        defer { busy = false }
        do {
            _ = try await SandwalkAPIClient.createCustomModel(
                id: id,
                label: label.isEmpty ? nil : label
            )
            showAdd = false
            newId = ""
            newLabel = ""
            await reload()
        } catch {
            self.error = error.localizedDescription
        }
    }

    @MainActor
    private func probe(_ profile: ModelProfileDTO) async {
        busy = true
        defer { busy = false }
        do {
            let result = try await SandwalkAPIClient.probeModelProfile(id: profile.id)
            if let err = result.error, !err.isEmpty {
                error = err
            } else {
                error = nil
                // Surface health briefly in error slot as status (green path uses message)
                error = "Probe \(result.health ?? "ok"): \((result.models ?? []).prefix(5).joined(separator: ", "))"
            }
        } catch {
            self.error = error.localizedDescription
        }
    }
}
