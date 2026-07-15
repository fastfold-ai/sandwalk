import Foundation

extension SandwalkAPIClient {
    // MARK: - Models

    static func listModels(enabledOnly: Bool = false, discover: Bool = true) async throws -> [AgentModelDTO] {
        var q: [URLQueryItem] = [
            .init(name: "discover", value: discover ? "true" : "false"),
        ]
        if enabledOnly { q.append(.init(name: "enabled_only", value: "true")) }
        let wrap: DataList<AgentModelDTO> = try await get("/v1/models", query: q)
        return wrap.data
    }

    static func setModelEnabled(id: String, enabled: Bool) async throws -> AgentModelDTO {
        try await patch("/v1/models/\(enc(id))", body: ["enabled": enabled])
    }

    static func createCustomModel(id: String, provider: String = "openai", label: String?) async throws -> AgentModelDTO {
        var body: [String: Any] = ["id": id, "provider": provider]
        if let label { body["label"] = label }
        return try await post("/v1/models", body: body)
    }

    static func deleteCustomModel(id: String) async throws {
        try await delete("/v1/models/\(enc(id))")
    }

    static func listModelProfiles(includeCloud: Bool = true) async throws -> [ModelProfileDTO] {
        var q: [URLQueryItem] = []
        if !includeCloud {
            q.append(.init(name: "include_cloud", value: "false"))
        }
        let wrap: DataList<ModelProfileDTO> = try await get("/v1/model-profiles", query: q)
        return wrap.data
    }

    static func createModelProfile(_ input: [String: Any]) async throws -> ModelProfileDTO {
        try await post("/v1/model-profiles", body: input)
    }

    static func updateModelProfile(id: String, _ input: [String: Any]) async throws -> ModelProfileDTO {
        try await patch("/v1/model-profiles/\(enc(id))", body: input)
    }

    static func deleteModelProfile(id: String) async throws {
        try await delete("/v1/model-profiles/\(enc(id))")
    }

    static func probeModelProfile(id: String) async throws -> ModelProfileProbeDTO {
        try await post("/v1/model-profiles/\(enc(id))/probe", body: [:] as [String: Any])
    }

    static func discoverModelEndpoint(
        backend: String,
        baseUrl: String,
        apiKey: String? = nil
    ) async throws -> ModelProfileProbeDTO {
        var body: [String: Any] = [
            "backend": backend,
            "baseUrl": baseUrl,
        ]
        if let apiKey, !apiKey.isEmpty {
            body["apiKey"] = apiKey
        }
        return try await post("/v1/model-profiles/discover", body: body)
    }

    // MARK: - Tools

    static func listTools() async throws -> ToolCatalogDTO {
        try await get("/v1/tools")
    }

    static func setToolEnabled(id: String, enabled: Bool) async throws -> ToolSummaryDTO {
        try await patch("/v1/tools/\(enc(id))", body: ["enabled": enabled])
    }

    // MARK: - Datasets

    static func listDatasets() async throws -> [DatasetSummaryDTO] {
        let wrap: DataList<DatasetSummaryDTO> = try await get("/v1/datasets")
        return wrap.data
    }

    static func installDataset(id: String) async throws -> DatasetInstallDTO {
        try await post("/v1/datasets/\(enc(id))/install", body: [:] as [String: Any])
    }

    // MARK: - Skills

    static func listSkills() async throws -> [AgentSkillDTO] {
        let wrap: DataList<AgentSkillDTO> = try await get("/v1/skills")
        return wrap.data
    }

    static func setSkillEnabled(name: String, enabled: Bool) async throws -> AgentSkillDTO {
        try await patch("/v1/skills/\(enc(name))", body: ["enabled": enabled])
    }

    static func installSkill(source: String) async throws -> [String] {
        let result: InstalledListDTO = try await post("/v1/skills", body: ["source": source])
        return result.installed
    }

    static func removeSkill(name: String) async throws {
        try await delete("/v1/skills/\(enc(name))")
    }
}
