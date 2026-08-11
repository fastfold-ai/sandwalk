import SwiftUI

struct ModelsSettingsView: View {
    @State private var models: [AgentModelDTO] = []
    @State private var profiles: [ModelProfileDTO] = []
    @State private var search = ""
    @State private var error: String?
    @State private var status: String?
    @State private var busy = false
    @State private var showCustomAdd = false
    @State private var newId = ""
    @State private var newLabel = ""
    @State private var profileSheet: LocalLLMProfileSheet.Mode?

    @Environment(\.sandwalkTheme) private var theme

    private var filtered: [AgentModelDTO] {
        let q = search.trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
        guard !q.isEmpty else { return models }
        return models.filter {
            $0.id.lowercased().contains(q)
                || $0.label.lowercased().contains(q)
                || $0.provider.lowercased().contains(q)
        }
    }

    private var localProfiles: [ModelProfileDTO] {
        profiles
            .filter { !($0.isCloud ?? false) }
            .sorted { $0.label.localizedCaseInsensitiveCompare($1.label) == .orderedAscending }
    }

    var body: some View {
        AgentAPIGate {
            VStack(alignment: .leading, spacing: 0) {
                WebUIManagementCallout(topic: "models", path: "models")

                AgentSearchField(text: $search)
                SettingsSectionHeader("MODELS", subtitle: "\(filtered.count) shown · includes discovered local models")
                SettingsListGroup {
                    if filtered.isEmpty {
                        SettingsRow(label: busy ? "Loading…" : "No models", isLast: true) {
                            EmptyView()
                        }
                    } else {
                        ForEach(Array(filtered.enumerated()), id: \.element.id) { index, model in
                            SettingsRow(
                                label: model.label,
                                sublabel: modelSublabel(model),
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

                SettingsSectionHeader("CUSTOM", subtitle: "Add cloud model ids by name")
                SettingsListGroup {
                    SettingsRow(label: "Add custom model", sublabel: "POST /v1/models", isLast: true) {
                        Button("Add") { showCustomAdd = true }
                            .buttonStyle(.sandwalk(.normal))
                    }
                }

                HStack {
                    SettingsSectionHeader(
                        "LOCAL LLM",
                        subtitle: "\(localProfiles.count) endpoints — discovered models join the list above"
                    )
                    Spacer(minLength: 8)
                    Button {
                        profileSheet = .create
                    } label: {
                        Label("Add Local LLM", systemImage: "plus")
                    }
                    .buttonStyle(.sandwalk(.primary))
                    .padding(.trailing, 18)
                    .padding(.top, 8)
                }

                SettingsListGroup {
                    if localProfiles.isEmpty {
                        SettingsRow(
                            label: "No local endpoints yet",
                            sublabel: "Add Ollama, oMLX, LM Studio, or any OpenAI-compatible server.",
                            isLast: true
                        ) {
                            EmptyView()
                        }
                    } else {
                        ForEach(Array(localProfiles.enumerated()), id: \.element.id) { index, profile in
                            let backend = LocalLLMBackend.from(apiBackend: profile.backend)
                            SettingsRow(
                                label: profile.label,
                                sublabel: profileSublabel(profile),
                                isLast: index == localProfiles.count - 1
                            ) {
                                HStack(spacing: 8) {
                                    LocalLLMBackendIcon(backend: backend, size: 18)
                                    Button("Discover") {
                                        Task { await probe(profile) }
                                    }
                                    .buttonStyle(.sandwalk(.normal))
                                    .disabled(busy)
                                    Button("Edit") {
                                        profileSheet = .edit(profile)
                                    }
                                    .buttonStyle(.sandwalk(.normal))
                                    Button {
                                        Task { await removeProfile(profile) }
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

                if let status {
                    Text(status)
                        .font(.sandwalk(11.5))
                        .foregroundStyle(theme.textSecondary)
                        .padding(.horizontal, 18)
                        .padding(.top, 6)
                }
                AgentPaneError(message: error)
            }
            .padding(.top, 4)
            .task { await reload() }
            .sheet(isPresented: $showCustomAdd) {
                VStack(alignment: .leading, spacing: 12) {
                    Text("Add custom model").font(.headline)
                    TextField("Model id", text: $newId)
                    TextField("Label (optional)", text: $newLabel)
                    HStack {
                        Spacer()
                        Button("Cancel") { showCustomAdd = false }
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
            .sheet(item: $profileSheet) { mode in
                LocalLLMProfileSheet(mode: mode) {
                    profileSheet = nil
                    Task { await reload() }
                }
            }
        }
    }

    private func modelSublabel(_ model: AgentModelDTO) -> String {
        let source: String
        switch model.source {
        case "cloud": source = "\(model.provider) · cloud"
        case "custom": source = "\(model.provider) · custom"
        case "profile":
            let backend = (model.backend ?? "").trimmingCharacters(in: .whitespacesAndNewlines)
            source = backend.isEmpty
                ? "local · \(model.profileId ?? "endpoint")"
                : "\(backend) · local"
        default: source = "\(model.provider) · \(model.source)"
        }
        return source + (model.enabled ? "" : " · disabled")
    }

    private func profileSublabel(_ profile: ModelProfileDTO) -> String {
        var parts = [profile.backend]
        if let url = profile.baseUrl, !url.isEmpty { parts.append(url) }
        if profile.isActive == true { parts.append("active") }
        if let model = profile.defaultModel, !model.isEmpty {
            parts.append("default \(model)")
        }
        return parts.joined(separator: " · ")
    }

    @MainActor
    private func reload() async {
        busy = true
        error = nil
        defer { busy = false }
        do {
            async let m = SandwalkAPIClient.listModels(discover: true)
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
            if let idx = models.firstIndex(where: { $0.id == model.id && $0.profileId == model.profileId }) {
                models[idx] = updated
            } else {
                await reload()
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
            showCustomAdd = false
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
            let models = result.models ?? []
            if let err = result.error, !err.isEmpty, models.isEmpty {
                error = err
                status = nil
            } else {
                error = nil
                let preview = models.prefix(5).joined(separator: ", ")
                status = "Discovered \(models.count) from \(profile.label)"
                    + (preview.isEmpty ? "" : ": \(preview)")
                await reload()
            }
        } catch {
            self.error = error.localizedDescription
        }
    }

    @MainActor
    private func removeProfile(_ profile: ModelProfileDTO) async {
        busy = true
        defer { busy = false }
        do {
            try await SandwalkAPIClient.deleteModelProfile(id: profile.id)
            status = "Deleted \(profile.label)."
            await reload()
        } catch {
            self.error = error.localizedDescription
        }
    }
}
