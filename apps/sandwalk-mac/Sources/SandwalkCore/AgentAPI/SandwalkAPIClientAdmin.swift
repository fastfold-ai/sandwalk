import Foundation

extension SandwalkAPIClient {
    // MARK: - Runtime settings

    static func getRuntimeSettings() async throws -> RuntimeSettingsDTO {
        try await get("/v1/settings/runtime")
    }

    static func updateRuntimeSettings(_ changes: [String: Any]) async throws -> RuntimeSettingsDTO {
        try await patch("/v1/settings/runtime", body: changes)
    }

    // MARK: - Sandbox settings

    static func getSandboxSettings() async throws -> SandboxSettingsDTO {
        try await get("/v1/settings/sandbox")
    }

    static func updateSandboxSettings(_ changes: [String: Any]) async throws -> SandboxSettingsDTO {
        try await patch("/v1/settings/sandbox", body: changes)
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
}
