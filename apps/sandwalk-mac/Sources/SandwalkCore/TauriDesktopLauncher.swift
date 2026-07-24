import AppKit
import Foundation

/// Opens or focuses the packaged Tauri client (`Sandwalk.app`).
enum TauriDesktopLauncher {
    /// Bundle ids to try (current + legacy).
    private static let candidates: [String] = [
        "ai.fastfold.sandwalk",
        "ai.fastfold.sandwalk-desktop",
        "ai.fastfold.SandwalkDesktop",
        "com.fastfold.sandwalk-desktop",
    ]

    private static let appNames = [
        "Sandwalk.app",
        "Sandwalk Desktop.app",
        "SandwalkDesktop.app",
    ]

    /// Returns true if the Tauri client was launched or activated.
    @discardableResult
    static func open(path: String? = nil) -> Bool {
        let route = normalizedRoute(path)
        if launchByBundleId(route: route) { return true }
        if launchByApplications(route: route) { return true }
        #if DEBUG
        if launchByDevBinary(route: route) { return true }
        #endif
        return false
    }

    static func isInstalled() -> Bool {
        for id in candidates {
            if NSWorkspace.shared.urlForApplication(withBundleIdentifier: id) != nil {
                return true
            }
        }
        for name in appNames {
            let url = URL(fileURLWithPath: "\(NSHomeDirectory())/Applications/\(name)")
            if FileManager.default.fileExists(atPath: url.path) { return true }
            let sys = URL(fileURLWithPath: "/Applications/\(name)")
            if FileManager.default.fileExists(atPath: sys.path) { return true }
        }
        return false
    }

    private static func normalizedRoute(_ path: String?) -> String {
        guard let path, !path.isEmpty else { return "/" }
        if path.hasPrefix("/") { return path }
        return "/\(path)"
    }

    private static func launchByBundleId(route: String) -> Bool {
        for id in candidates {
            guard let url = NSWorkspace.shared.urlForApplication(withBundleIdentifier: id) else {
                continue
            }
            return openApp(at: url, route: route)
        }
        return false
    }

    private static func launchByApplications(route: String) -> Bool {
        for name in appNames {
            for base in ["\(NSHomeDirectory())/Applications", "/Applications"] {
                let url = URL(fileURLWithPath: "\(base)/\(name)")
                if FileManager.default.fileExists(atPath: url.path) {
                    return openApp(at: url, route: route)
                }
            }
        }
        return false
    }

    #if DEBUG
    /// Dev only: `apps/local-web/src-tauri/target/debug/sandwalk-desktop`.
    private static func launchByDevBinary(route: String) -> Bool {
        guard let repo = AppConfig.load().repoRoot else { return false }
        let candidates = [
            repo.appendingPathComponent("apps/local-web/src-tauri/target/debug/sandwalk-desktop"),
            repo.appendingPathComponent("apps/local-web/src-tauri/target/release/sandwalk-desktop"),
        ]
        for bin in candidates where FileManager.default.isExecutableFile(atPath: bin.path) {
            let proc = Process()
            proc.executableURL = bin
            proc.arguments = ["--", route]
            proc.environment = ProcessInfo.processInfo.environment.merging([
                "SANDWALK_DESKTOP_ROUTE": route,
            ]) { _, new in new }
            do {
                try proc.run()
                return true
            } catch {
                continue
            }
        }
        return false
    }
    #endif

    private static func openApp(at url: URL, route: String) -> Bool {
        // Prefer deep link so a running instance can navigate.
        for scheme in ["sandwalk", "sandwalk-desktop"] {
            if let deep = URL(string: "\(scheme)://open\(route)"),
               NSWorkspace.shared.open(deep)
            {
                return true
            }
        }
        let config = NSWorkspace.OpenConfiguration()
        config.activates = true
        config.arguments = [route]
        NSWorkspace.shared.openApplication(at: url, configuration: config) { _, error in
            if let error {
                NSLog("Sandwalk Server: failed to open Sandwalk — \(error.localizedDescription)")
            }
        }
        return true
    }
}
