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

func formatDiscoveredModelLabel(_ modelId: String) -> String {
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
