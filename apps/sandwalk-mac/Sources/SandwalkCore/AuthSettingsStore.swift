import Foundation
import Security

/// Shared auth settings file (same path/schema as the Python CLI).
struct SandwalkAuthSettings: Equatable, Sendable {
    var apiKey: String
    var authEnabled: Bool
    var secretKey: String

    var apiKeyConfigured: Bool { !apiKey.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty }

    static let empty = SandwalkAuthSettings(apiKey: "", authEnabled: false, secretKey: "")
}

enum AuthSettingsStore {
    /// Always Application Support — same default as the CLI — so Settings,
    /// SessionsAPI Bearer, and `sandwalk auth` stay on one file. Do not honor
    /// shell `SANDWALK_SETTINGS_PATH` overrides here (those are for CLI tests).
    static func settingsFileURL() -> URL {
        let base = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask).first
            ?? URL(fileURLWithPath: NSHomeDirectory()).appendingPathComponent("Library/Application Support")
        return base.appendingPathComponent("Sandwalk/settings.json")
    }

    static func load() -> SandwalkAuthSettings {
        let url = settingsFileURL()
        guard
            let data = try? Data(contentsOf: url),
            let root = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
            let auth = root["auth"] as? [String: Any]
        else {
            return .empty
        }
        return SandwalkAuthSettings(
            apiKey: (auth["api_key"] as? String) ?? "",
            authEnabled: (auth["auth_enabled"] as? Bool) ?? false,
            secretKey: (auth["secret_key"] as? String) ?? ""
        )
    }

    static func save(_ settings: SandwalkAuthSettings) throws {
        let url = settingsFileURL()
        try FileManager.default.createDirectory(
            at: url.deletingLastPathComponent(),
            withIntermediateDirectories: true
        )
        var root: [String: Any] = [:]
        if let data = try? Data(contentsOf: url),
           let existing = try? JSONSerialization.jsonObject(with: data) as? [String: Any]
        {
            root = existing
        }
        var secret = settings.secretKey
        if secret.isEmpty {
            secret = randomSecret()
        }
        root["auth"] = [
            "api_key": settings.apiKey,
            "auth_enabled": settings.authEnabled,
            "secret_key": secret,
        ]
        let data = try JSONSerialization.data(withJSONObject: root, options: [.prettyPrinted, .sortedKeys])
        try data.write(to: url, options: .atomic)
    }

    static func generateAPIKey() -> String {
        let alphabet = Array("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789")
        var suffix = ""
        for _ in 0..<24 {
            suffix.append(alphabet.randomElement()!)
        }
        return "sk-sandwalk-\(suffix)"
    }

    private static func randomSecret() -> String {
        var bytes = [UInt8](repeating: 0, count: 32)
        _ = SecRandomCopyBytes(kSecRandomDefault, bytes.count, &bytes)
        return Data(bytes).base64EncodedString()
            .replacingOccurrences(of: "+", with: "-")
            .replacingOccurrences(of: "/", with: "_")
            .replacingOccurrences(of: "=", with: "")
    }
}
