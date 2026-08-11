import SwiftUI

extension LocalLLMProfileSheet {
    func seedForm() {
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

    func applyBackendDefaults(_ next: LocalLLMBackend) {
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

    func clearDiscover() {
        discovered = []
        discoverSource = nil
        discoverError = nil
    }

    @MainActor
    func discover() async {
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
    func save() async {
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

extension String {
    var nilIfEmpty: String? {
        let t = trimmingCharacters(in: .whitespacesAndNewlines)
        return t.isEmpty ? nil : t
    }
}
