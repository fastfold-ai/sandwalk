import SwiftUI

extension MCPsSettingsView {
    @MainActor
    func reload() async {
        busy = true
        error = nil
        defer { busy = false }
        do {
            async let s = SandwalkAPIClient.listMcpServers()
            async let c = SandwalkAPIClient.listMcpCatalog()
            servers = try await s
            catalog = try await c
        } catch {
            self.error = error.localizedDescription
        }
    }

    @MainActor
    func setEnabled(_ server: McpServerDTO, _ enabled: Bool) async {
        busy = true
        defer { busy = false }
        do {
            let updated = try await SandwalkAPIClient.setMcpServerEnabled(id: server.id, enabled: enabled)
            if let idx = servers.firstIndex(where: { $0.id == server.id }) {
                servers[idx] = updated
            }
        } catch {
            self.error = error.localizedDescription
        }
    }

    @MainActor
    func setCatalogEnabled(_ entry: McpCatalogEntryDTO, _ enabled: Bool) async {
        busy = true
        defer { busy = false }
        do {
            _ = try await SandwalkAPIClient.setMcpCatalogEnabled(id: entry.id, enabled: enabled)
            await reload()
        } catch {
            self.error = error.localizedDescription
        }
    }

    @MainActor
    func remove(_ server: McpServerDTO) async {
        busy = true
        defer { busy = false }
        do {
            try await SandwalkAPIClient.deleteMcpServer(id: server.id)
            // Full reload so Suggested picks up removed catalog templates.
            await reload()
        } catch {
            self.error = error.localizedDescription
        }
    }

    @MainActor
    func installCatalog(_ entry: McpCatalogEntryDTO) async {
        busy = true
        defer { busy = false }
        do {
            _ = try await SandwalkAPIClient.installMcpCatalog(id: entry.id)
            status = "Added \(entry.name)."
            await reload()
        } catch {
            self.error = error.localizedDescription
        }
    }

    @MainActor
    func create() async {
        busy = true
        defer { busy = false }
        do {
            _ = try await SandwalkAPIClient.createMcpServer([
                "name": newName,
                "transport": "stdio",
                "command": newCommand,
                "args": [] as [String],
                "enabled": true,
            ])
            showAdd = false
            newName = ""
            newCommand = ""
            await reload()
        } catch {
            self.error = error.localizedDescription
        }
    }

    @MainActor
    func connectCatalog() async {
        guard let id = connectingId else { return }
        busy = true
        defer { busy = false }
        do {
            _ = try await SandwalkAPIClient.connectMcpCatalog(id: id, apiKey: connectKey)
            connectingId = nil
            status = "Connected \(id)."
            await reload()
        } catch {
            self.error = error.localizedDescription
        }
    }
}
