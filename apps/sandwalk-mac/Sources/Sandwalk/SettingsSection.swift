import Foundation

enum SettingsSection: String, Hashable, CaseIterable, Identifiable {
    case models
    case tools
    case datasets
    case skills
    case integrations
    case mcps
    case doctor
    case storage
    case environment
    case status
    case network
    case logs
    case security
    case about

    var id: String { rawValue }

    var title: String {
        switch self {
        case .models: return "Models"
        case .tools: return "Tools"
        case .datasets: return "Datasets"
        case .skills: return "Skills"
        case .integrations: return "Integrations"
        case .mcps: return "MCPs"
        case .doctor: return "Doctor"
        case .storage: return "Storage"
        case .environment: return "Environment"
        case .status: return "Status"
        case .network: return "Network"
        case .logs: return "Logs"
        case .security: return "Security"
        case .about: return "About"
        }
    }

    var symbol: String {
        switch self {
        case .models: return "cube"
        case .tools: return "wrench"
        case .datasets: return "externaldrive"
        case .skills: return "wand.and.stars"
        case .integrations: return "puzzlepiece.extension"
        case .mcps: return "point.3.connected.trianglepath.dotted"
        case .doctor: return "stethoscope"
        case .storage: return "internaldrive"
        case .environment: return "hexagon.fill"
        case .status: return "gauge.with.dots.needle.50percent"
        case .network: return "network"
        case .logs: return "scroll"
        case .security: return "lock"
        case .about: return "info.circle"
        }
    }
}
