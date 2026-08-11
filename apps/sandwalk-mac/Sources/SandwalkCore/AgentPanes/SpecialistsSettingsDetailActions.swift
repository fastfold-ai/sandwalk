import SwiftUI

extension SpecialistDetailSettingsView {
    @MainActor
    func load() async {
        busy = true
        error = nil
        defer { busy = false }
        do {
            async let toolsTask = SandwalkAPIClient.listTools()
            async let skillsTask = SandwalkAPIClient.listSkills()
            async let serversTask = SandwalkAPIClient.listMcpServers()
            async let catalogTask = SandwalkAPIClient.listMcpCatalog()
            catalogTools = try await toolsTask.data
            skills = try await skillsTask
            mcpServers = try await serversTask
            mcpCatalog = try await catalogTask

            if let specialistId {
                let item = try await SandwalkAPIClient.getSpecialist(id: specialistId)
                apply(item)
            } else {
                seedCoreToolsIfNeeded()
            }
        } catch {
            self.error = error.localizedDescription
        }
    }

    func apply(_ item: SpecialistDTO) {
        name = item.name
        slug = item.slug
        slugTouched = true
        descriptionText = item.description ?? ""
        instructions = item.instructions ?? ""
        color = item.color.isEmpty ? "ink" : item.color
        icon = item.icon.isEmpty ? "git-branch" : item.icon
        enabled = item.enabled
        selectedTools = Set(item.toolNames)
        selectedSkills = Set(item.skillNames)
        selectedMcpServers = Set(item.mcpServerIds)
        selectedMcpCatalogs = Set(item.mcpCatalogIds)
        didSeedCoreTools = true
    }

    func seedCoreToolsIfNeeded() {
        guard isCreate, !didSeedCoreTools, selectedTools.isEmpty, !catalogTools.isEmpty else { return }
        selectedTools = Set(catalogTools.filter(\.isCore).map(\.id))
        didSeedCoreTools = true
    }

    func setTierTools(_ tools: [ToolSummaryDTO], enabled: Bool) {
        if enabled {
            for tool in tools { selectedTools.insert(tool.id) }
        } else {
            for tool in tools { selectedTools.remove(tool.id) }
        }
    }

    @MainActor
    func save() async {
        let trimmedName = name.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmedName.isEmpty else {
            error = "Name is required."
            return
        }
        let trimmedSlug = slug.trimmingCharacters(in: .whitespacesAndNewlines)
        let desc = descriptionText.trimmingCharacters(in: .whitespacesAndNewlines)
        let instr = instructions.trimmingCharacters(in: .whitespacesAndNewlines)

        busy = true
        defer { busy = false }
        do {
            if let specialistId {
                var body: [String: Any] = [
                    "name": trimmedName,
                    "slug": trimmedSlug.isEmpty ? Self.slugify(trimmedName) : trimmedSlug,
                    "color": color,
                    "icon": icon,
                    "enabled": enabled,
                    "toolNames": Array(selectedTools).sorted(),
                    "skillNames": Array(selectedSkills).sorted(),
                    "mcpServerIds": Array(selectedMcpServers).sorted(),
                    "mcpCatalogIds": Array(selectedMcpCatalogs).sorted(),
                    "clearDescription": desc.isEmpty,
                    "clearInstructions": instr.isEmpty,
                ]
                if !desc.isEmpty { body["description"] = desc }
                if !instr.isEmpty { body["instructions"] = instr }
                let updated = try await SandwalkAPIClient.updateSpecialist(id: specialistId, body: body)
                apply(updated)
                status = "Saved."
                error = nil
            } else {
                var body: [String: Any] = [
                    "name": trimmedName,
                    "color": color,
                    "icon": icon,
                    "enabled": enabled,
                    "toolNames": Array(selectedTools).sorted(),
                    "skillNames": Array(selectedSkills).sorted(),
                    "mcpServerIds": Array(selectedMcpServers).sorted(),
                    "mcpCatalogIds": Array(selectedMcpCatalogs).sorted(),
                ]
                if !trimmedSlug.isEmpty { body["slug"] = trimmedSlug }
                if !desc.isEmpty { body["description"] = desc }
                if !instr.isEmpty { body["instructions"] = instr }
                _ = try await SandwalkAPIClient.createSpecialist(body)
                status = "Created."
                error = nil
                dismiss()
            }
        } catch {
            self.error = error.localizedDescription
        }
    }

    @MainActor
    func deleteCurrent() async {
        guard let specialistId else { return }
        busy = true
        defer { busy = false }
        do {
            try await SandwalkAPIClient.deleteSpecialist(id: specialistId)
            dismiss()
        } catch {
            self.error = error.localizedDescription
        }
    }

    static func slugify(_ value: String) -> String {
        let lowered = value.lowercased()
        let mapped = lowered.map { ch -> Character in
            if ch.isLetter || ch.isNumber { return ch }
            return "-"
        }
        let collapsed = String(mapped)
            .replacingOccurrences(of: "-+", with: "-", options: .regularExpression)
            .trimmingCharacters(in: CharacterSet(charactersIn: "-"))
        return collapsed.isEmpty ? "specialist" : collapsed
    }
}
