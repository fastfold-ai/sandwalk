import Foundation
@testable import SandwalkCore

/// Backup / restore `~/Library/Application Support/Sandwalk/settings.json` around tests.
enum SettingsTestSupport {
    static func backupSettings() -> Data? {
        try? Data(contentsOf: AuthSettingsStore.settingsFileURL())
    }

    static func removeSettings() {
        try? FileManager.default.removeItem(at: AuthSettingsStore.settingsFileURL())
    }

    static func restoreSettings(from data: Data?) {
        removeSettings()
        guard let data else { return }
        let url = AuthSettingsStore.settingsFileURL()
        try? FileManager.default.createDirectory(
            at: url.deletingLastPathComponent(),
            withIntermediateDirectories: true
        )
        try? data.write(to: url, options: .atomic)
    }

    static func writeSettingsJSON(_ root: [String: Any]) throws {
        let url = AuthSettingsStore.settingsFileURL()
        try FileManager.default.createDirectory(
            at: url.deletingLastPathComponent(),
            withIntermediateDirectories: true
        )
        let data = try JSONSerialization.data(withJSONObject: root, options: [.prettyPrinted, .sortedKeys])
        try data.write(to: url, options: .atomic)
    }
}

enum EnvTestSupport {
    static func unset(_ keys: [String]) {
        for key in keys {
            unsetenv(key)
        }
    }
}
