import Foundation

// MARK: - Integrations

struct IntegrationFieldDTO: Codable, Hashable {
    let envVar: String
    let label: String
    let isSecret: Bool
    let configured: Bool
    let source: String?
    let maskedPreview: String?
}

struct IntegrationSummaryDTO: Codable, Identifiable, Hashable {
    var id: String { key }
    let key: String
    let name: String
    let category: String
    let description: String
    let envVar: String?
    let configured: Bool
    let source: String?
    let maskedPreview: String?
    let setupUrl: String?
    let free: Bool?
    let fields: [IntegrationFieldDTO]?
}

struct ValidateDTO: Codable {
    let ok: Bool
    let message: String?
}

// MARK: - MCP

struct McpServerDTO: Codable, Identifiable, Hashable {
    let id: String
    let name: String
    let transport: String
    let command: String?
    let args: [String]?
    let url: String?
    let enabled: Bool
    let catalogId: String?
    let description: String?
}

struct McpCatalogEntryDTO: Codable, Identifiable, Hashable {
    let id: String
    let name: String
    let description: String
    let url: String?
    let transport: String?
    let authMode: String?
    let preferredAuth: String?
    let docsUrl: String?
    let configured: Bool?
    let enabled: Bool?
    let connected: Bool?
    let serverId: String?
    let toolCount: Int?
    let statusMessage: String?
}

struct McpToolDetailDTO: Codable, Identifiable, Hashable {
    var id: String { name }
    let name: String
    let title: String?
    let description: String?
}

struct ValidateMcpDTO: Codable {
    let ok: Bool?
    let message: String?
    let toolCount: Int?
    let tools: [String]?
    let toolDetails: [McpToolDetailDTO]?
}

struct ConnectMcpDTO: Codable {
    let ok: Bool?
    let serverId: String?
    let message: String?
    let toolCount: Int?
}

// MARK: - Specialists

struct SpecialistDTO: Codable, Identifiable, Hashable {
    let id: String
    let name: String
    let slug: String
    let description: String?
    let instructions: String?
    let color: String
    let icon: String
    let skillNames: [String]
    let toolNames: [String]
    let mcpServerIds: [String]
    let mcpCatalogIds: [String]
    let enabled: Bool
    let createdAt: String?
    let updatedAt: String?

    init(
        id: String,
        name: String,
        slug: String,
        description: String?,
        instructions: String?,
        color: String,
        icon: String,
        skillNames: [String],
        toolNames: [String] = [],
        mcpServerIds: [String],
        mcpCatalogIds: [String],
        enabled: Bool,
        createdAt: String?,
        updatedAt: String?
    ) {
        self.id = id
        self.name = name
        self.slug = slug
        self.description = description
        self.instructions = instructions
        self.color = color
        self.icon = icon
        self.skillNames = skillNames
        self.toolNames = toolNames
        self.mcpServerIds = mcpServerIds
        self.mcpCatalogIds = mcpCatalogIds
        self.enabled = enabled
        self.createdAt = createdAt
        self.updatedAt = updatedAt
    }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        id = try c.decode(String.self, forKey: .id)
        name = try c.decode(String.self, forKey: .name)
        slug = try c.decode(String.self, forKey: .slug)
        description = try c.decodeIfPresent(String.self, forKey: .description)
        instructions = try c.decodeIfPresent(String.self, forKey: .instructions)
        color = try c.decodeIfPresent(String.self, forKey: .color) ?? "ink"
        icon = try c.decodeIfPresent(String.self, forKey: .icon) ?? "agent"
        skillNames = try c.decodeIfPresent([String].self, forKey: .skillNames) ?? []
        toolNames = try c.decodeIfPresent([String].self, forKey: .toolNames) ?? []
        mcpServerIds = try c.decodeIfPresent([String].self, forKey: .mcpServerIds) ?? []
        mcpCatalogIds = try c.decodeIfPresent([String].self, forKey: .mcpCatalogIds) ?? []
        enabled = try c.decodeIfPresent(Bool.self, forKey: .enabled) ?? true
        createdAt = try c.decodeIfPresent(String.self, forKey: .createdAt)
        updatedAt = try c.decodeIfPresent(String.self, forKey: .updatedAt)
    }
}

struct DeleteSpecialistDTO: Codable {
    let deleted: Bool?
}
