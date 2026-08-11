import Foundation

// MARK: - Tools

struct ToolSummaryDTO: Codable, Identifiable, Hashable {
    let id: String
    let name: String
    let category: String
    let status: String?
    let description: String
    let requiresData: [String]?
    let enabled: Bool
    /// ``core`` or ``extra`` — optional for older API payloads.
    let tier: String?

    var isCore: Bool { (tier ?? "extra").lowercased() == "core" }
}

struct ToolCatalogDTO: Codable {
    let data: [ToolSummaryDTO]
    let count: Int?
    let categories: [String]?
}

// MARK: - Datasets

struct DatasetSummaryDTO: Codable, Identifiable, Hashable {
    let id: String
    let description: String
    let status: String
    let filesFound: Int?
    let filesExpected: Int?
    let sizeDisplay: String?
    let autoDownload: Bool?
    let path: String?
    let note: String?
}

struct DatasetInstallDTO: Codable {
    let ok: Bool?
    let id: String?
    let status: String?
    let summary: String?
}

// MARK: - Skills

struct AgentSkillDTO: Codable, Identifiable, Hashable {
    var id: String { name }
    let name: String
    let description: String
    let tags: [String]?
    let source: String?
    let author: String?
    let version: String?
    let enabled: Bool
}
