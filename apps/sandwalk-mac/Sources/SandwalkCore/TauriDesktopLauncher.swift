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

    /// Written for the Tauri client to pick up if argv / single-instance drops it.
    static func pendingRouteURL() -> URL {
        // Keep this off the MainActor — ControlPlane.supportDirectory() is isolated.
        let base = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask).first
            ?? URL(fileURLWithPath: NSHomeDirectory()).appendingPathComponent("Library/Application Support")
        return base
            .appendingPathComponent("Sandwalk", isDirectory: true)
            .appendingPathComponent("pending-desktop-route")
    }

    /// Returns true if the Tauri client was launched or activated.
    @discardableResult
    static func open(path: String? = nil) -> Bool {
        let route = normalizedRoute(path)
        writePendingRoute(route)
        // Prefer the Sandwalk.app that nests this Server helper — Launch Services
        // can resolve the wrong bundle when multiple copies exist.
        if let nested = nestedHostApp(), openApp(at: nested, route: route) {
            return true
        }
        if launchByBundleId(route: route) { return true }
        if launchByApplications(route: route) { return true }
        #if DEBUG
        if launchByDevBinary(route: route) { return true }
        #endif
        return false
    }

    static func isInstalled() -> Bool {
        if nestedHostApp() != nil { return true }
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

    /// `Sandwalk.app/Contents/Helpers/Sandwalk Server.app` → parent `Sandwalk.app`.
    private static func nestedHostApp() -> URL? {
        let server = Bundle.main.bundleURL
        let host = server
            .deletingLastPathComponent() // Helpers
            .deletingLastPathComponent() // Contents
            .deletingLastPathComponent() // Sandwalk.app
        guard host.pathExtension == "app" else { return nil }
        let exe = host
            .appendingPathComponent("Contents", isDirectory: true)
            .appendingPathComponent("MacOS", isDirectory: true)
            .appendingPathComponent("sandwalk-desktop")
        guard FileManager.default.isExecutableFile(atPath: exe.path) else { return nil }
        return host
    }

    private static func normalizedRoute(_ path: String?) -> String {
        guard let path, !path.isEmpty else { return "/" }
        if path.hasPrefix("/") { return path }
        return "/\(path)"
    }

    private static func writePendingRoute(_ route: String) {
        let file = pendingRouteURL()
        try? FileManager.default.createDirectory(
            at: file.deletingLastPathComponent(),
            withIntermediateDirectories: true
        )
        try? route.write(to: file, atomically: true, encoding: .utf8)
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
        // Do not use sandwalk:// — Server owns that scheme for Settings.
        // Plain NSWorkspace.openApplication on a running hide-on-close app often
        // activates without showing the window or delivering argv. `open -n`
        // forces a second instance so tauri-plugin-single-instance can focus the
        // existing window and receive the route.
        let process = Process()
        process.executableURL = URL(fileURLWithPath: "/usr/bin/open")
        process.arguments = [
            "-n",
            "-a", url.path,
            "--args",
            "--",
            route,
        ]
        do {
            try process.run()
            process.waitUntilExit()
            if process.terminationStatus == 0 {
                return true
            }
            NSLog(
                "Sandwalk Server: open -n failed (status %d) for %@",
                process.terminationStatus,
                url.path
            )
        } catch {
            NSLog("Sandwalk Server: open -n error — \(error.localizedDescription)")
        }

        // Fallback: activate without -n (may still leave a hidden window invisible).
        let config = NSWorkspace.OpenConfiguration()
        config.activates = true
        config.arguments = ["--", route]
        config.createsNewApplicationInstance = true
        NSWorkspace.shared.openApplication(at: url, configuration: config) { _, error in
            if let error {
                NSLog("Sandwalk Server: failed to open Sandwalk — \(error.localizedDescription)")
            }
        }
        return true
    }
}
