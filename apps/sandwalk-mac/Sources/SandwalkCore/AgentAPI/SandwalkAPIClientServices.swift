import Foundation

extension SandwalkAPIClient {
    // MARK: - Integrations

    static func listIntegrations() async throws -> [IntegrationSummaryDTO] {
        let wrap: DataList<IntegrationSummaryDTO> = try await get("/v1/integrations")
        return wrap.data
    }

    static func updateIntegration(key: String, values: [String: String]) async throws -> IntegrationSummaryDTO {
        try await put("/v1/integrations/\(enc(key))", body: ["values": values])
    }

    static func removeIntegration(key: String) async throws -> IntegrationSummaryDTO {
        try await deleteReturning("/v1/integrations/\(enc(key))")
    }

    static func validateIntegration(key: String) async throws -> ValidateDTO {
        try await post("/v1/integrations/\(enc(key))/validate", body: [:] as [String: Any])
    }

    // MARK: - MCP

    static func listMcpServers() async throws -> [McpServerDTO] {
        let wrap: DataList<McpServerDTO> = try await get("/v1/mcp-servers")
        return wrap.data
    }

    static func listMcpCatalog() async throws -> [McpCatalogEntryDTO] {
        let wrap: DataList<McpCatalogEntryDTO> = try await get("/v1/mcp-servers/catalog")
        return wrap.data
    }

    static func setMcpServerEnabled(id: String, enabled: Bool) async throws -> McpServerDTO {
        try await patch("/v1/mcp-servers/\(enc(id))", body: ["enabled": enabled])
    }

    static func createMcpServer(_ body: [String: Any]) async throws -> McpServerDTO {
        try await post("/v1/mcp-servers", body: body)
    }

    static func deleteMcpServer(id: String) async throws {
        try await delete("/v1/mcp-servers/\(enc(id))")
    }

    static func validateMcpServer(id: String) async throws -> ValidateMcpDTO {
        try await post("/v1/mcp-servers/\(enc(id))/validate", body: [:] as [String: Any])
    }

    static func validateMcpCatalog(id: String) async throws -> ValidateMcpDTO {
        try await post(
            "/v1/mcp-servers/catalog/\(enc(id))/validate",
            body: [:] as [String: Any]
        )
    }

    static func setMcpCatalogEnabled(id: String, enabled: Bool) async throws -> ConnectMcpDTO {
        try await patch(
            "/v1/mcp-servers/catalog/\(enc(id))",
            body: ["enabled": enabled]
        )
    }

    static func connectMcpCatalog(id: String, apiKey: String) async throws -> ConnectMcpDTO {
        try await post(
            "/v1/mcp-servers/catalog/\(enc(id))/connect",
            body: ["method": "api_key", "apiKey": apiKey]
        )
    }

    static func disconnectMcpCatalog(id: String) async throws {
        try await delete("/v1/mcp-servers/catalog/\(enc(id))/connect")
    }

    static func installMcpCatalog(id: String) async throws -> McpServerDTO {
        try await post(
            "/v1/mcp-servers/catalog/\(enc(id))/install",
            body: [:] as [String: Any]
        )
    }

    // MARK: - Specialists

    static func listSpecialists() async throws -> [SpecialistDTO] {
        let wrap: DataList<SpecialistDTO> = try await get("/v1/specialists")
        return wrap.data
    }

    static func getSpecialist(id: String) async throws -> SpecialistDTO {
        try await get("/v1/specialists/\(enc(id))")
    }

    static func createSpecialist(_ body: [String: Any]) async throws -> SpecialistDTO {
        try await post("/v1/specialists", body: body)
    }

    static func updateSpecialist(id: String, body: [String: Any]) async throws -> SpecialistDTO {
        try await patch("/v1/specialists/\(enc(id))", body: body)
    }

    static func deleteSpecialist(id: String) async throws {
        try await delete("/v1/specialists/\(enc(id))")
    }

    // MARK: - Prompt budget

    static func getPromptBudget(specialistId: String? = nil) async throws -> PromptBudgetResponseDTO {
        var q: [URLQueryItem] = []
        if let specialistId, !specialistId.isEmpty {
            q.append(.init(name: "specialistId", value: specialistId))
        }
        return try await get("/v1/settings/prompt-budget", query: q)
    }
}
