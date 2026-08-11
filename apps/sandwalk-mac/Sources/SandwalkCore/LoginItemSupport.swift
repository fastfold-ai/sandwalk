import Foundation
import ServiceManagement

/// macOS "Open at Login" via `SMAppService.mainApp` (requires app in Applications).
enum LoginItemSupport {
    static var isEnabled: Bool {
        SMAppService.mainApp.status == .enabled
    }

    static var statusDescription: String {
        switch SMAppService.mainApp.status {
        case .enabled:
            return "Sandwalk opens when you log in to this Mac."
        case .requiresApproval:
            return "Enable Sandwalk in System Settings → General → Login Items."
        case .notRegistered:
            return "Off — Sandwalk will not open at login."
        case .notFound:
            return "Install Sandwalk to ~/Applications (or /Applications) to use Open at Login."
        @unknown default:
            return "Login item status unknown."
        }
    }

    static func setEnabled(_ enabled: Bool) throws {
        if enabled {
            try SMAppService.mainApp.register()
        } else if SMAppService.mainApp.status == .enabled {
            try SMAppService.mainApp.unregister()
        }
    }
}
