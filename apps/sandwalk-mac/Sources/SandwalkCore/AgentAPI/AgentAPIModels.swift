import Foundation

// MARK: - Models

struct AgentModelDTO: Codable, Identifiable, Hashable {
    let id: String
    let label: String
    let description: String?
    let provider: String
    let source: String
    let profileId: String?
    let backend: String?
    let enabled: Bool
    let health: String?
}

struct ModelProfileDTO: Codable, Identifiable, Hashable {
    let id: String
    let label: String
    let backend: String
    let baseUrl: String?
    let defaultModel: String?
    let discovery: [String]?
    let hasApiKey: Bool?
    let apiKeyPreview: String?
    let isCloud: Bool?
    let isActive: Bool?
    let isDefault: Bool?
}

struct ModelProfileProbeDTO: Codable {
    let profileId: String?
    let health: String?
    let models: [String]?
    let modelsSource: String?
    let error: String?
}
