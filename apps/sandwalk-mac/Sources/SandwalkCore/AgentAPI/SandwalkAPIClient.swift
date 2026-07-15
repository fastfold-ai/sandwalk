import Foundation

enum SandwalkAPIError: Error, LocalizedError {
    case notRunning
    case http(Int, String)
    case decode(Error)
    case transport(Error)

    var errorDescription: String? {
        switch self {
        case .notRunning:
            return "Agent API is not running. Start Sandwalk from Status or the menu bar."
        case .http(let code, let body):
            let trimmed = body.trimmingCharacters(in: .whitespacesAndNewlines)
            return trimmed.isEmpty ? "HTTP \(code)" : "HTTP \(code): \(trimmed)"
        case .decode(let error):
            return "Could not parse response: \(error.localizedDescription)"
        case .transport(let error):
            return error.localizedDescription
        }
    }
}

/// Thin `/v1` client — same contracts as `packages/local-client`.
@MainActor
enum SandwalkAPIClient {
    static let session: URLSession = {
        let config = URLSessionConfiguration.ephemeral
        config.timeoutIntervalForRequest = 30
        config.timeoutIntervalForResource = 120
        return URLSession(configuration: config)
    }()

    static let decoder = JSONDecoder()
    static let encoder = JSONEncoder()

    static var isAPILikelyUp: Bool {
        switch SandwalkRuntime.supervisor?.overall {
        case .running, .partial: return true
        default: return false
        }
    }

    // MARK: - HTTP

    static func get<T: Decodable>(_ path: String, query: [URLQueryItem] = []) async throws -> T {
        try await send(path, method: "GET", query: query, body: nil)
    }

    static func post<T: Decodable>(_ path: String, body: [String: Any]) async throws -> T {
        try await send(path, method: "POST", body: jsonData(body))
    }

    static func put<T: Decodable>(_ path: String, body: [String: Any]) async throws -> T {
        try await send(path, method: "PUT", body: jsonData(body))
    }

    static func patch<T: Decodable>(_ path: String, body: [String: Any]) async throws -> T {
        try await send(path, method: "PATCH", body: jsonData(body))
    }

    static func delete(_ path: String) async throws {
        let _: EmptyOK? = try? await send(path, method: "DELETE", body: nil)
        // Some DELETEs return empty body — treat 2xx as success via send
        _ = try await sendRaw(path, method: "DELETE", body: nil)
    }

    static func deleteReturning<T: Decodable>(_ path: String) async throws -> T {
        try await send(path, method: "DELETE", body: nil)
    }

    static func send<T: Decodable>(
        _ path: String,
        method: String,
        query: [URLQueryItem] = [],
        body: Data?
    ) async throws -> T {
        let data = try await sendRaw(path, method: method, query: query, body: body)
        if T.self == EmptyOK.self {
            return EmptyOK() as! T
        }
        if data.isEmpty, let empty = EmptyOK() as? T {
            return empty
        }
        do {
            return try decoder.decode(T.self, from: data)
        } catch {
            throw SandwalkAPIError.decode(error)
        }
    }

    @discardableResult
    static func sendRaw(
        _ path: String,
        method: String,
        query: [URLQueryItem] = [],
        body: Data?
    ) async throws -> Data {
        let base = SandwalkRuntime.config.apiBaseURL.absoluteString
            .trimmingCharacters(in: CharacterSet(charactersIn: "/"))
        let cleanPath = path.hasPrefix("/") ? path : "/\(path)"
        guard var comps = URLComponents(string: base + cleanPath) else {
            throw SandwalkAPIError.notRunning
        }
        if !query.isEmpty { comps.queryItems = query }
        guard let url = comps.url else { throw SandwalkAPIError.notRunning }

        var request = URLRequest(url: url)
        request.httpMethod = method
        request.timeoutInterval = 45
        if let body {
            request.httpBody = body
            request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        }
        applyAuth(&request)

        do {
            let (data, response) = try await session.data(for: request)
            guard let http = response as? HTTPURLResponse else {
                throw SandwalkAPIError.transport(URLError(.badServerResponse))
            }
            guard (200..<300).contains(http.statusCode) else {
                let text = String(data: data, encoding: .utf8) ?? ""
                if [0, 502, 503, 504].contains(http.statusCode) {
                    throw SandwalkAPIError.notRunning
                }
                // Connection refused surfaces as transport error, not HTTP.
                throw SandwalkAPIError.http(http.statusCode, text)
            }
            return data
        } catch let error as SandwalkAPIError {
            throw error
        } catch {
            throw SandwalkAPIError.transport(error)
        }
    }

    static func applyAuth(_ request: inout URLRequest) {
        let settings = AuthSettingsStore.load()
        if settings.authEnabled, !settings.apiKey.isEmpty {
            request.setValue("Bearer \(settings.apiKey)", forHTTPHeaderField: "Authorization")
        }
    }

    static func jsonData(_ body: [String: Any]) throws -> Data {
        try JSONSerialization.data(withJSONObject: body)
    }

    static func enc(_ value: String) -> String {
        value.addingPercentEncoding(withAllowedCharacters: .urlPathAllowed) ?? value
    }
}

struct DataList<T: Decodable>: Decodable {
    let data: [T]
}

struct InstalledListDTO: Decodable {
    let installed: [String]
}

struct EmptyOK: Decodable {
    init() {}
    init(from decoder: Decoder) throws {}
}
