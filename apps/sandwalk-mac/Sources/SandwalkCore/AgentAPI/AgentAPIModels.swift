import Foundation

// MARK: - Models

struct AgentModelDTO: Codable, Identifiable, Hashable {
    let id: String
    let label: String
    let description: String?
    let provider: String
    let source: String
    let profileId: String?
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
    let configured: Bool?
    let enabled: Bool?
    let connected: Bool?
    let serverId: String?
    let statusMessage: String?
}

struct ValidateMcpDTO: Codable {
    let ok: Bool?
    let message: String?
    let toolCount: Int?
}

struct ConnectMcpDTO: Codable {
    let ok: Bool?
    let serverId: String?
    let message: String?
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
    let mcpServerIds: [String]
    let mcpCatalogIds: [String]
    let enabled: Bool
    let createdAt: String?
    let updatedAt: String?
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
