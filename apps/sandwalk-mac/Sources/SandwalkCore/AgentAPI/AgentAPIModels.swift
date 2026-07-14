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

// MARK: - Server status

struct ServerSystemInfoDTO: Codable, Hashable {
    let label: String
    let platform: String
    let arch: String
    let osVersion: String
    let pythonVersion: String
    let ramUsedBytes: Int64
    let ramTotalBytes: Int64
    let thermalState: String?
    let loadAverage: [Double]?
    let chipName: String?
    let gpuCores: Int?
    let gpuUtilizationPercent: Double?
    let gpuMemoryUsedBytes: Int64?
    let gpuMemoryTotalBytes: Int64?
}

struct ServerCacheInfoDTO: Codable, Hashable {
    let fileCount: Int
    let totalBytes: Int64
    let path: String
}

struct ServerStatusReportDTO: Codable, Hashable {
    let status: String
    let service: String
    let version: String
    let message: String?
    let host: String?
    let port: Int?
    let pid: Int
    let startedAt: String
    let uptimeSeconds: Double
    let system: ServerSystemInfoDTO
    let cache: ServerCacheInfoDTO
    let checkedAt: String
}

// MARK: - Doctor / Storage / Environment

struct DoctorCheckDTO: Codable, Identifiable, Hashable {
    var id: String { "\(category)-\(name)" }
    let name: String
    let status: String
    let detail: String
    let category: String
    let fix: String?
}

struct DoctorSummaryDTO: Codable {
    let ok: Int
    let warn: Int
    let error: Int
    let total: Int
}

struct DoctorReportDTO: Codable {
    let ok: Bool
    let checkedAt: String?
    let summary: DoctorSummaryDTO
    let checks: [DoctorCheckDTO]
}

struct StorageCategoryDTO: Codable, Identifiable, Hashable {
    var id: String { label + String(bytes) }
    let label: String
    let color: String?
    let bytes: Int64
    let path: String?
}

struct StorageLocationDTO: Codable {
    let path: String
    let label: String?
    let bytes: Int64?
}

struct StorageReportDTO: Codable {
    let location: StorageLocationDTO?
    let categories: [StorageCategoryDTO]
    let totalBytes: Int64
    let availableBytes: Int64?
    let checkedAt: String?
}

struct EnvPackageDTO: Codable, Identifiable, Hashable {
    var id: String { name }
    let name: String
    let version: String?
    let installed: Bool
    let removable: Bool
}

struct EnvGroupDTO: Codable, Identifiable, Hashable {
    let id: String
    let label: String
    let description: String?
    let packages: [EnvPackageDTO]
}

struct EnvironmentReportDTO: Codable {
    let pythonPath: String?
    let envPath: String?
    let envBytes: Int64?
    let groups: [EnvGroupDTO]
    let checkedAt: String?
}

struct EnvMutationDTO: Codable {
    let ok: Bool?
    let message: String?
    let name: String?
    let installed: Bool?
}

// MARK: - Runtime settings

struct RuntimeSettingsDTO: Codable, Hashable {
    var provider: String
    var model: String
    var openaiBaseUrl: String?
    var agentProfile: String
    var toolMode: String
    var recursionLimit: Int
    var maxSdkTurns: Int
    var groupToolTraces: Bool
    var toolTraceDetailLimit: Int
    var backgroundWatchTimeoutS: Int
    var interruptDrainTimeoutS: Int
    var parallelMaxThreads: Int
    var toolHealthEnabled: Bool
    var toolHealthFailThreshold: Int
    var toolHealthSuppressSeconds: Int

    static let defaults = RuntimeSettingsDTO(
        provider: "anthropic",
        model: "",
        openaiBaseUrl: nil,
        agentProfile: "research",
        toolMode: "ptc",
        recursionLimit: 120,
        maxSdkTurns: 30,
        groupToolTraces: true,
        toolTraceDetailLimit: 1,
        backgroundWatchTimeoutS: 7200,
        interruptDrainTimeoutS: 10,
        parallelMaxThreads: 5,
        toolHealthEnabled: true,
        toolHealthFailThreshold: 2,
        toolHealthSuppressSeconds: 900
    )
}

// MARK: - Sandbox settings

struct SandboxSettingsDTO: Codable, Hashable {
    var backend: String
    var modalApp: String
    var cpuImage: String
    var gpuImage: String
    var pipPackages: String
    var computeType: String
    var gpuClass: String
    var cpuCores: Double
    var ramGb: Double
    var idleTtlSeconds: Int
    var modalConfigured: Bool

    static let defaults = SandboxSettingsDTO(
        backend: "builtin",
        modalApp: "sandwalk",
        cpuImage: "python:3.12-slim",
        gpuImage: "pytorch/pytorch:2.4.0-cuda12.4-cudnn9-runtime",
        pipPackages: "pandas,numpy,matplotlib,scipy,pillow",
        computeType: "cpu",
        gpuClass: "T4",
        cpuCores: 2.0,
        ramGb: 8.0,
        idleTtlSeconds: 600,
        modalConfigured: false
    )
}

// MARK: - Prompt budget

struct PromptBudgetBucketDTO: Codable, Identifiable, Hashable {
    let id: String
    let label: String
    let tokens: Int
    let chars: Int
    let count: Int?
    let children: [PromptBudgetBucketDTO]

    init(
        id: String,
        label: String,
        tokens: Int,
        chars: Int,
        count: Int? = nil,
        children: [PromptBudgetBucketDTO] = []
    ) {
        self.id = id
        self.label = label
        self.tokens = tokens
        self.chars = chars
        self.count = count
        self.children = children
    }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        id = try c.decode(String.self, forKey: .id)
        label = try c.decode(String.self, forKey: .label)
        tokens = try c.decodeIfPresent(Int.self, forKey: .tokens) ?? 0
        chars = try c.decodeIfPresent(Int.self, forKey: .chars) ?? 0
        count = try c.decodeIfPresent(Int.self, forKey: .count)
        children = try c.decodeIfPresent([PromptBudgetBucketDTO].self, forKey: .children) ?? []
    }
}

struct PromptBudgetToolCountsDTO: Codable, Hashable {
    let domain: Int
    let mcp: Int
    let deepagents: Int
    let total: Int
    let openaiCap: Int

    init(
        domain: Int = 0,
        mcp: Int = 0,
        deepagents: Int = 0,
        total: Int = 0,
        openaiCap: Int = 128
    ) {
        self.domain = domain
        self.mcp = mcp
        self.deepagents = deepagents
        self.total = total
        self.openaiCap = openaiCap
    }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        domain = try c.decodeIfPresent(Int.self, forKey: .domain) ?? 0
        mcp = try c.decodeIfPresent(Int.self, forKey: .mcp) ?? 0
        deepagents = try c.decodeIfPresent(Int.self, forKey: .deepagents) ?? 0
        total = try c.decodeIfPresent(Int.self, forKey: .total) ?? 0
        openaiCap = try c.decodeIfPresent(Int.self, forKey: .openaiCap) ?? 128
    }
}

struct PromptBudgetResponseDTO: Codable, Hashable {
    let totalTokens: Int
    let totalChars: Int
    let tokenizer: String
    let toolMode: String
    let provider: String?
    let model: String?
    let specialistId: String?
    let specialistName: String?
    let toolCounts: PromptBudgetToolCountsDTO
    let buckets: [PromptBudgetBucketDTO]
    let warnings: [String]
    let sampleQuery: String

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        totalTokens = try c.decodeIfPresent(Int.self, forKey: .totalTokens) ?? 0
        totalChars = try c.decodeIfPresent(Int.self, forKey: .totalChars) ?? 0
        tokenizer = try c.decodeIfPresent(String.self, forKey: .tokenizer) ?? "chars/4"
        toolMode = try c.decodeIfPresent(String.self, forKey: .toolMode) ?? "ptc"
        provider = try c.decodeIfPresent(String.self, forKey: .provider)
        model = try c.decodeIfPresent(String.self, forKey: .model)
        specialistId = try c.decodeIfPresent(String.self, forKey: .specialistId)
        specialistName = try c.decodeIfPresent(String.self, forKey: .specialistName)
        toolCounts = try c.decodeIfPresent(PromptBudgetToolCountsDTO.self, forKey: .toolCounts)
            ?? PromptBudgetToolCountsDTO()
        buckets = try c.decodeIfPresent([PromptBudgetBucketDTO].self, forKey: .buckets) ?? []
        warnings = try c.decodeIfPresent([String].self, forKey: .warnings) ?? []
        sampleQuery = try c.decodeIfPresent(String.self, forKey: .sampleQuery) ?? "Hello"
    }
}
