import Foundation

/// Recent agent sessions from the local Sandwalk API.
struct AgentSessionSummary: Equatable, Sendable, Identifiable {
    let id: String
    let title: String
    let updatedAt: Date?
}

enum SessionsAPI {
    static let listLimit = 5
    static let viewMoreLimit = 10
    static let fetchLimit = listLimit + viewMoreLimit

    static func fetchRecent(config: AppConfig, limit: Int = fetchLimit) async -> [AgentSessionSummary] {
        var request = URLRequest(url: config.sessionsAPIURL)
        request.timeoutInterval = 2.5
        request.httpMethod = "GET"
        applyAuth(&request)
        do {
            let (data, response) = try await URLSession.shared.data(for: request)
            guard let http = response as? HTTPURLResponse, (200..<300).contains(http.statusCode) else {
                return []
            }
            return parseList(data).sorted { lhs, rhs in
                (lhs.updatedAt ?? .distantPast) > (rhs.updatedAt ?? .distantPast)
            }
            .prefix(limit)
            .map { $0 }
        } catch {
            return []
        }
    }

    static func createSession(config: AppConfig, title: String? = nil) async throws -> AgentSessionSummary {
        var request = URLRequest(url: config.sessionsAPIURL)
        request.timeoutInterval = 8
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        applyAuth(&request)
        let body: [String: Any] = title.map { ["title": $0] } ?? [:]
        request.httpBody = try JSONSerialization.data(withJSONObject: body)
        let (data, response) = try await URLSession.shared.data(for: request)
        guard let http = response as? HTTPURLResponse, (200..<300).contains(http.statusCode) else {
            throw URLError(.badServerResponse)
        }
        guard let session = parseOne(data) else {
            throw URLError(.cannotParseResponse)
        }
        return session
    }

    private static func applyAuth(_ request: inout URLRequest) {
        let settings = AuthSettingsStore.load()
        guard settings.authEnabled, !settings.apiKey.isEmpty else { return }
        request.setValue("Bearer \(settings.apiKey)", forHTTPHeaderField: "Authorization")
    }

    private static func parseList(_ data: Data) -> [AgentSessionSummary] {
        guard
            let root = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
            let items = root["data"] as? [[String: Any]]
        else { return [] }
        return items.compactMap(parseItem)
    }

    private static func parseOne(_ data: Data) -> AgentSessionSummary? {
        guard let item = try? JSONSerialization.jsonObject(with: data) as? [String: Any] else {
            return nil
        }
        return parseItem(item)
    }

    private static func parseItem(_ item: [String: Any]) -> AgentSessionSummary? {
        guard let id = item["id"] as? String else { return nil }
        let title = (item["title"] as? String)?.trimmingCharacters(in: .whitespacesAndNewlines)
        let display = (title?.isEmpty == false) ? title! : "Untitled session"
        let updated =
            parseDate(item["updatedAt"] as? String)
            ?? parseDate(item["lastMessageAt"] as? String)
            ?? parseDate(item["createdAt"] as? String)
        return AgentSessionSummary(id: id, title: display, updatedAt: updated)
    }

    private static func parseDate(_ raw: String?) -> Date? {
        guard let raw, !raw.isEmpty else { return nil }
        let iso = ISO8601DateFormatter()
        iso.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        if let date = iso.date(from: raw) { return date }
        iso.formatOptions = [.withInternetDateTime]
        return iso.date(from: raw)
    }
}
