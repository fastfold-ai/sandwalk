import Foundation

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
