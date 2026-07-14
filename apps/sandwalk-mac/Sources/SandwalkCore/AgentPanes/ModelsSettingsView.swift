import SwiftUI

/// Local LLM backends — mirrors web `PROFILE_BACKENDS` / CLI defaults.
enum LocalLLMBackend: String, CaseIterable, Identifiable, Hashable {
    case ollama
    case unsloth
    case omlx
    case ds4
    case llamaCpp = "llama_cpp"
    case lmStudio = "lm_studio"
    case other

    var id: String { rawValue }

    var label: String {
        switch self {
        case .ollama: return "Ollama"
        case .unsloth: return "Unsloth"
        case .omlx: return "oMLX"
        case .ds4: return "DS4"
        case .llamaCpp: return "llama.cpp"
        case .lmStudio: return "LM Studio"
        case .other: return "Other OpenAI-compatible"
        }
    }

    var hint: String {
        switch self {
        case .ollama: return "/api/tags"
        case .unsloth, .omlx: return "/v1/models · auth"
        case .ds4, .llamaCpp, .lmStudio: return "/v1/models"
        case .other: return "/v1/models then /api/tags"
        }
    }

    var defaultBaseUrl: String {
        switch self {
        case .ollama: return "http://127.0.0.1:11434/v1"
        case .unsloth: return "http://127.0.0.1:8888/v1"
        case .omlx, .ds4: return "http://127.0.0.1:8000/v1"
        case .llamaCpp: return "http://127.0.0.1:8080/v1"
        case .lmStudio: return "http://127.0.0.1:1234/v1"
        case .other: return "http://127.0.0.1:11434/v1"
        }
    }

    var defaultLabel: String {
        switch self {
        case .ollama: return "Ollama Local"
        case .unsloth: return "Unsloth Local"
        case .omlx: return "oMLX Local"
        case .ds4: return "DS4 Local"
        case .llamaCpp: return "llama.cpp Local"
        case .lmStudio: return "LM Studio Local"
        case .other: return "Custom Compatible Endpoint"
        }
    }

    /// Asset name under `Resources/local-llm/`, or `nil` for SF Symbol `cpu`.
    var iconAssetName: String? {
        switch self {
        case .ollama: return "local-llm/ollama"
        case .unsloth: return "local-llm/unsloth"
        case .omlx: return "local-llm/omlx"
        case .llamaCpp: return "local-llm/llama-cpp"
        case .lmStudio: return "local-llm/lm-studio"
        case .ds4, .other: return nil
        }
    }

    static func from(apiBackend: String) -> LocalLLMBackend {
        let raw = apiBackend == "openai" ? "other" : apiBackend
        return LocalLLMBackend(rawValue: raw) ?? .other
    }

    static var knownDefaultBaseUrls: Set<String> {
        Set(allCases.map {
            $0.defaultBaseUrl
                .trimmingCharacters(in: CharacterSet(charactersIn: "/"))
                .replacingOccurrences(of: "://localhost", with: "://127.0.0.1")
        })
    }

    static var knownDefaultLabels: Set<String> {
        Set(allCases.map { $0.defaultLabel.lowercased() })
    }
}

struct LocalLLMBackendIcon: View {
    let backend: LocalLLMBackend
    var size: CGFloat = 16

    var body: some View {
        if let name = backend.iconAssetName,
           let url = Bundle.module.url(forResource: (name as NSString).lastPathComponent, withExtension: "png", subdirectory: "local-llm"),
           let nsImage = NSImage(contentsOf: url) {
            Image(nsImage: nsImage)
                .resizable()
                .interpolation(.high)
                .frame(width: size, height: size)
                .clipShape(RoundedRectangle(cornerRadius: 3, style: .continuous))
        } else {
            Image(systemName: "cpu")
                .font(.system(size: size * 0.85, weight: .medium))
                .foregroundStyle(.secondary)
                .frame(width: size, height: size)
        }
    }
}

private func formatDiscoveredModelLabel(_ modelId: String) -> String {
    let raw = modelId.trimmingCharacters(in: .whitespacesAndNewlines)
    guard !raw.isEmpty else { return raw }
    return raw
        .replacingOccurrences(of: "_", with: "-")
        .split(separator: "-")
        .filter { !$0.isEmpty }
        .map { part in
            let s = String(part)
            guard let first = s.first else { return s }
            return String(first).uppercased() + s.dropFirst()
        }
        .joined(separator: " ")
}

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

// MARK: - Add / Edit Local LLM sheet

struct LocalLLMProfileSheet: View {
    enum Mode: Hashable, Identifiable {
        case create
        case edit(ModelProfileDTO)

        var id: String {
            switch self {
            case .create: return "create"
            case .edit(let profile): return "edit-\(profile.id)"
            }
        }
    }

    let mode: Mode
    var onDone: () -> Void

    @Environment(\.dismiss) private var dismiss
    @Environment(\.sandwalkTheme) private var theme

    @State private var label = ""
    @State private var backend: LocalLLMBackend = .ollama
    @State private var baseUrl = LocalLLMBackend.ollama.defaultBaseUrl
    @State private var apiKey = ""
    @State private var showApiKey = false
    @State private var discovered: [String] = []
    @State private var discoverSource: String?
    @State private var discoverError: String?
    @State private var discovering = false
    @State private var saving = false
    @State private var error: String?

    private var editing: ModelProfileDTO? {
        if case .edit(let profile) = mode { return profile }
        return nil
    }

    private var isCreate: Bool { editing == nil }

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            HStack {
                Text(isCreate ? "Add Local LLM" : "Edit Local LLM")
                    .font(.sandwalk(16, weight: .semibold))
                Spacer()
                Button {
                    dismiss()
                } label: {
                    Image(systemName: "xmark.circle.fill")
                        .foregroundStyle(theme.textTertiary)
                }
                .buttonStyle(.plain)
            }
            .padding(.horizontal, 20)
            .padding(.top, 18)
            .padding(.bottom, 12)

            Form {
                TextField("Label", text: $label)
                Picker("Backend", selection: $backend) {
                    ForEach(LocalLLMBackend.allCases) { option in
                        HStack(spacing: 8) {
                            LocalLLMBackendIcon(backend: option, size: 14)
                            Text("\(option.label) · \(option.hint)")
                        }
                        .tag(option)
                    }
                }
                .onChange(of: backend) { _, next in
                    applyBackendDefaults(next)
                    clearDiscover()
                }

                TextField("Base URL", text: $baseUrl)
                    .onChange(of: baseUrl) { _, _ in clearDiscover() }
                Text("Suggested: \(backend.defaultBaseUrl)")
                    .font(.sandwalk(11))
                    .foregroundStyle(theme.textTertiary)

                HStack {
                    Group {
                        if showApiKey {
                            TextField(
                                editing?.hasApiKey == true
                                    ? "API key (leave blank to keep)"
                                    : "API key (optional)",
                                text: $apiKey
                            )
                        } else {
                            SecureField(
                                editing?.hasApiKey == true
                                    ? "API key (leave blank to keep)"
                                    : "API key (optional)",
                                text: $apiKey
                            )
                        }
                    }
                    Button {
                        showApiKey.toggle()
                    } label: {
                        Image(systemName: showApiKey ? "eye.slash" : "eye")
                    }
                    .buttonStyle(.borderless)
                }

                Section {
                    HStack {
                        Text("Models")
                            .font(.sandwalk(12, weight: .medium))
                        Spacer()
                        Button {
                            Task { await discover() }
                        } label: {
                            if discovering {
                                ProgressView().controlSize(.small)
                            } else {
                                Label("Discover", systemImage: "arrow.clockwise")
                            }
                        }
                        .disabled(discovering || baseUrl.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
                    }

                    if discovered.isEmpty {
                        Text("Discover to preview models from this endpoint. After Save they appear in the model list.")
                            .font(.sandwalk(11.5))
                            .foregroundStyle(theme.textSecondary)
                    } else {
                        ScrollView {
                            LazyVStack(alignment: .leading, spacing: 0) {
                                ForEach(discovered, id: \.self) { modelId in
                                    VStack(alignment: .leading, spacing: 2) {
                                        Text(formatDiscoveredModelLabel(modelId))
                                            .font(.sandwalk(12.5, weight: .medium))
                                            .lineLimit(1)
                                        Text("local · \(backend.label.lowercased())")
                                            .font(.sandwalk(11))
                                            .foregroundStyle(theme.textSecondary)
                                    }
                                    .frame(maxWidth: .infinity, alignment: .leading)
                                    .padding(.vertical, 8)
                                    Divider()
                                }
                            }
                        }
                        .frame(maxHeight: 180)
                        .padding(.horizontal, 4)
                        .background(
                            RoundedRectangle(cornerRadius: 8, style: .continuous)
                                .stroke(theme.rowSep, lineWidth: 0.5)
                        )

                        if let discoverSource {
                            Text("Found \(discovered.count) via \(discoverSource). After Save, all appear in the model list.")
                                .font(.sandwalk(11))
                                .foregroundStyle(theme.textSecondary)
                        }
                    }

                    if let discoverError {
                        Text(discoverError)
                            .font(.sandwalk(11.5))
                            .foregroundStyle(.red)
                    }
                }
            }
            .formStyle(.grouped)
            .padding(.horizontal, 4)

            if let error {
                Text(error)
                    .font(.sandwalk(11.5))
                    .foregroundStyle(.red)
                    .padding(.horizontal, 20)
            }

            HStack {
                Spacer()
                Button("Cancel") {
                    dismiss()
                }
                .buttonStyle(.sandwalk(.normal))
                Button(saving ? "Saving…" : "Save") {
                    Task { await save() }
                }
                .buttonStyle(.sandwalk(.primary))
                .disabled(saving)
                .keyboardShortcut(.defaultAction)
            }
            .padding(20)
        }
        .frame(width: 520, height: 620)
        .background(theme.windowBg)
        .onAppear { seedForm() }
    }

    private func seedForm() {
        if let profile = editing {
            label = profile.label
            backend = LocalLLMBackend.from(apiBackend: profile.backend)
            baseUrl = profile.baseUrl ?? backend.defaultBaseUrl
            apiKey = ""
        } else {
            label = LocalLLMBackend.ollama.defaultLabel
            backend = .ollama
            baseUrl = LocalLLMBackend.ollama.defaultBaseUrl
            apiKey = ""
        }
        clearDiscover()
    }

    private func applyBackendDefaults(_ next: LocalLLMBackend) {
        let normalizedUrl = baseUrl
            .trimmingCharacters(in: .whitespacesAndNewlines)
            .trimmingCharacters(in: CharacterSet(charactersIn: "/"))
            .replacingOccurrences(of: "://localhost", with: "://127.0.0.1")
        let suggestUrl = baseUrl.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
            || LocalLLMBackend.knownDefaultBaseUrls.contains(normalizedUrl)
        let suggestLabel = label.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
            || LocalLLMBackend.knownDefaultLabels.contains(label.lowercased())
        if suggestUrl { baseUrl = next.defaultBaseUrl }
        if suggestLabel { label = next.defaultLabel }
    }

    private func clearDiscover() {
        discovered = []
        discoverSource = nil
        discoverError = nil
    }

    @MainActor
    private func discover() async {
        let url = baseUrl.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !url.isEmpty else {
            discoverError = "Enter a base URL before discovering models."
            return
        }
        discovering = true
        discoverError = nil
        defer { discovering = false }
        do {
            let result = try await SandwalkAPIClient.discoverModelEndpoint(
                backend: backend.rawValue,
                baseUrl: url,
                apiKey: apiKey.trimmingCharacters(in: .whitespacesAndNewlines).nilIfEmpty
            )
            let models = result.models ?? []
            discovered = models
            discoverSource = result.modelsSource
            if let err = result.error, !err.isEmpty, models.isEmpty {
                discoverError = err
            } else if models.isEmpty {
                discoverError = "No models found. Check the base URL and API key, then try again."
            }
        } catch {
            discoverError = error.localizedDescription
            discovered = []
            discoverSource = nil
        }
    }

    @MainActor
    private func save() async {
        saving = true
        error = nil
        defer { saving = false }
        let trimmedLabel = label.trimmingCharacters(in: .whitespacesAndNewlines)
        let trimmedUrl = baseUrl.trimmingCharacters(in: .whitespacesAndNewlines)
        var body: [String: Any] = [
            "label": trimmedLabel.isEmpty ? backend.defaultLabel : trimmedLabel,
            "backend": backend.rawValue,
            "baseUrl": trimmedUrl,
        ]
        if let key = apiKey.trimmingCharacters(in: .whitespacesAndNewlines).nilIfEmpty {
            body["apiKey"] = key
        }
        if let first = discovered.first {
            body["defaultModel"] = first
        } else if let existing = editing?.defaultModel, !existing.isEmpty {
            body["defaultModel"] = existing
        }
        do {
            if let editing {
                _ = try await SandwalkAPIClient.updateModelProfile(id: editing.id, body)
            } else {
                _ = try await SandwalkAPIClient.createModelProfile(body)
            }
            onDone()
            dismiss()
        } catch {
            self.error = error.localizedDescription
        }
    }
}

private extension String {
    var nilIfEmpty: String? {
        let t = trimmingCharacters(in: .whitespacesAndNewlines)
        return t.isEmpty ? nil : t
    }
}
