import Foundation

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
