import Foundation

enum SettingsSection: String, Hashable, CaseIterable, Identifiable {
    case status
    case network
    case advanced
    case security
    case logs
    case runtime
    case sandbox
    case prompts
    case models
    case tools
    case datasets
    case skills
    case specialists
    case integrations
    case mcps
    case doctor
    case storage
    case environment
    case about

    var id: String { rawValue }

    var title: String {
        switch self {
        case .runtime: return "Runtime"
        case .sandbox: return "Sandbox"
        case .prompts: return "Prompts"
        case .models: return "Models"
        case .tools: return "Tools"
        case .datasets: return "Datasets"
        case .skills: return "Skills"
        case .specialists: return "Specialists"
        case .integrations: return "Integrations"
        case .mcps: return "MCPs"
        case .doctor: return "Doctor"
        case .storage: return "Storage"
        case .environment: return "Environment"
        case .status: return "Status"
        case .network: return "Network"
        case .advanced: return "Advanced"
        case .logs: return "Logs"
        case .security: return "Security"
        case .about: return "About"
        }
    }

    var symbol: String {
        switch self {
        case .runtime: return "cpu"
        case .sandbox: return "shippingbox"
        case .prompts: return "text.alignleft"
        case .models: return "cube"
        case .tools: return "wrench"
        case .datasets: return "externaldrive"
        case .skills: return "wand.and.stars"
        case .specialists: return "arrow.triangle.branch"
        case .integrations: return "puzzlepiece.extension"
        case .mcps: return "point.3.connected.trianglepath.dotted"
        case .doctor: return "stethoscope"
        case .storage: return "internaldrive"
        case .environment: return "hexagon.fill"
        case .status: return "gauge.with.dots.needle.50percent"
        case .network: return "network"
        case .advanced: return "gearshape.2"
        case .logs: return "scroll"
        case .security: return "lock"
        case .about: return "info.circle"
        }
    }

    /// Parse `sandwalk://settings/security`, `sandwalk://security`, etc.
    static func fromDeepLink(_ url: URL) -> SettingsSection? {
        let host = (url.host ?? "").lowercased()
        let parts = url.path
            .split(separator: "/")
            .map { String($0).lowercased() }
            .filter { !$0.isEmpty }

        if host == "settings" {
            guard let raw = parts.first else { return nil }
            return SettingsSection(rawValue: raw)
        }
        if let section = SettingsSection(rawValue: host), parts.isEmpty {
            return section
        }
        if parts.first == "settings", let raw = parts.dropFirst().first {
            return SettingsSection(rawValue: raw)
        }
        if let raw = parts.first {
            return SettingsSection(rawValue: raw)
        }
        return nil
    }
}
