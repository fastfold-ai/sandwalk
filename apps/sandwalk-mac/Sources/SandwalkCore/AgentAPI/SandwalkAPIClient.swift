import Foundation

enum SandwalkAPIError: Error, LocalizedError {
    case notRunning
    case http(Int, String)
    case decode(Error)
    case transport(Error)

    var errorDescription: String? {
        switch self {
        case .notRunning:
            return "Agent API is not running. Start Sandwalk from Status or the menu bar."
        case .http(let code, let body):
            let trimmed = body.trimmingCharacters(in: .whitespacesAndNewlines)
            return trimmed.isEmpty ? "HTTP \(code)" : "HTTP \(code): \(trimmed)"
        case .decode(let error):
            return "Could not parse response: \(error.localizedDescription)"
        case .transport(let error):
            return error.localizedDescription
        }
    }
}

/// Thin `/v1` client — same contracts as `packages/local-client`.
@MainActor
enum SandwalkAPIClient {
    private static let session: URLSession = {
        let config = URLSessionConfiguration.ephemeral
        config.timeoutIntervalForRequest = 30
        config.timeoutIntervalForResource = 120
        return URLSession(configuration: config)
    }()

    private static let decoder = JSONDecoder()
    private static let encoder = JSONEncoder()

    static var isAPILikelyUp: Bool {
        switch SandwalkRuntime.supervisor?.overall {
        case .running, .partial: return true
        default: return false
        }
    }

    // MARK: - Models

    static func listModels(enabledOnly: Bool = false) async throws -> [AgentModelDTO] {
        var q: [URLQueryItem] = []
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

    static func listModelProfiles() async throws -> [ModelProfileDTO] {
        let wrap: DataList<ModelProfileDTO> = try await get("/v1/model-profiles")
        return wrap.data
    }

    static func createModelProfile(_ input: [String: Any]) async throws -> ModelProfileDTO {
        try await post("/v1/model-profiles", body: input)
    }

    static func deleteModelProfile(id: String) async throws {
        try await delete("/v1/model-profiles/\(enc(id))")
    }

    static func probeModelProfile(id: String) async throws -> ModelProfileProbeDTO {
        try await post("/v1/model-profiles/\(enc(id))/probe", body: [:] as [String: Any])
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

    static func connectMcpCatalog(id: String, apiKey: String) async throws -> ConnectMcpDTO {
        try await post(
            "/v1/mcp-servers/catalog/\(enc(id))/connect",
            body: ["method": "api_key", "apiKey": apiKey]
        )
    }

    static func disconnectMcpCatalog(id: String) async throws {
        try await delete("/v1/mcp-servers/catalog/\(enc(id))/connect")
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

    // MARK: - Runtime settings

    static func getRuntimeSettings() async throws -> RuntimeSettingsDTO {
        try await get("/v1/settings/runtime")
    }

    static func updateRuntimeSettings(_ changes: [String: Any]) async throws -> RuntimeSettingsDTO {
        try await patch("/v1/settings/runtime", body: changes)
    }

    // MARK: - Doctor / Storage / Environment

    static func runDoctor() async throws -> DoctorReportDTO {
        try await get("/v1/doctor")
    }

    static func getStorage() async throws -> StorageReportDTO {
        try await get("/v1/storage")
    }

    static func clearCache() async throws {
        let _: EmptyOK = try await post("/v1/storage/cache/clear", body: [:] as [String: Any])
    }

    static func getEnvironment() async throws -> EnvironmentReportDTO {
        try await get("/v1/environment")
    }

    static func installPackage(name: String) async throws -> EnvMutationDTO {
        try await post("/v1/environment/packages/install", body: ["name": name])
    }

    static func uninstallPackage(name: String) async throws -> EnvMutationDTO {
        try await post("/v1/environment/packages/uninstall", body: ["name": name])
    }

    // MARK: - Server status

    static func serverStatus() async throws -> ServerStatusReportDTO {
        try await get("/v1/status")
    }

    static func clearRuntimeCache() async throws -> ServerCacheInfoDTO {
        try await post("/v1/storage/cache/clear", body: [:])
    }

    // MARK: - HTTP

    private static func get<T: Decodable>(_ path: String, query: [URLQueryItem] = []) async throws -> T {
        try await send(path, method: "GET", query: query, body: nil)
    }

    private static func post<T: Decodable>(_ path: String, body: [String: Any]) async throws -> T {
        try await send(path, method: "POST", body: jsonData(body))
    }

    private static func put<T: Decodable>(_ path: String, body: [String: Any]) async throws -> T {
        try await send(path, method: "PUT", body: jsonData(body))
    }

    private static func patch<T: Decodable>(_ path: String, body: [String: Any]) async throws -> T {
        try await send(path, method: "PATCH", body: jsonData(body))
    }

    private static func delete(_ path: String) async throws {
        let _: EmptyOK? = try? await send(path, method: "DELETE", body: nil)
        // Some DELETEs return empty body — treat 2xx as success via send
        _ = try await sendRaw(path, method: "DELETE", body: nil)
    }

    private static func deleteReturning<T: Decodable>(_ path: String) async throws -> T {
        try await send(path, method: "DELETE", body: nil)
    }

    private static func send<T: Decodable>(
        _ path: String,
        method: String,
        query: [URLQueryItem] = [],
        body: Data?
    ) async throws -> T {
        let data = try await sendRaw(path, method: method, query: query, body: body)
        if T.self == EmptyOK.self {
            return EmptyOK() as! T
        }
        if data.isEmpty, let empty = EmptyOK() as? T {
            return empty
        }
        do {
            return try decoder.decode(T.self, from: data)
        } catch {
            throw SandwalkAPIError.decode(error)
        }
    }

    @discardableResult
    private static func sendRaw(
        _ path: String,
        method: String,
        query: [URLQueryItem] = [],
        body: Data?
    ) async throws -> Data {
        let base = SandwalkRuntime.config.apiBaseURL.absoluteString
            .trimmingCharacters(in: CharacterSet(charactersIn: "/"))
        let cleanPath = path.hasPrefix("/") ? path : "/\(path)"
        guard var comps = URLComponents(string: base + cleanPath) else {
            throw SandwalkAPIError.notRunning
        }
        if !query.isEmpty { comps.queryItems = query }
        guard let url = comps.url else { throw SandwalkAPIError.notRunning }

        var request = URLRequest(url: url)
        request.httpMethod = method
        request.timeoutInterval = 45
        if let body {
            request.httpBody = body
            request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        }
        applyAuth(&request)

        do {
            let (data, response) = try await session.data(for: request)
            guard let http = response as? HTTPURLResponse else {
                throw SandwalkAPIError.transport(URLError(.badServerResponse))
            }
            guard (200..<300).contains(http.statusCode) else {
                let text = String(data: data, encoding: .utf8) ?? ""
                if [0, 502, 503, 504].contains(http.statusCode) {
                    throw SandwalkAPIError.notRunning
                }
                // Connection refused surfaces as transport error, not HTTP.
                throw SandwalkAPIError.http(http.statusCode, text)
            }
            return data
        } catch let error as SandwalkAPIError {
            throw error
        } catch {
            throw SandwalkAPIError.transport(error)
        }
    }

    private static func applyAuth(_ request: inout URLRequest) {
        let settings = AuthSettingsStore.load()
        if settings.authEnabled, !settings.apiKey.isEmpty {
            request.setValue("Bearer \(settings.apiKey)", forHTTPHeaderField: "Authorization")
        }
    }

    private static func jsonData(_ body: [String: Any]) throws -> Data {
        try JSONSerialization.data(withJSONObject: body)
    }

    private static func enc(_ value: String) -> String {
        value.addingPercentEncoding(withAllowedCharacters: .urlPathAllowed) ?? value
    }
}

private struct DataList<T: Decodable>: Decodable {
    let data: [T]
}

private struct InstalledListDTO: Decodable {
    let installed: [String]
}

private struct EmptyOK: Decodable {
    init() {}
    init(from decoder: Decoder) throws {}
}
