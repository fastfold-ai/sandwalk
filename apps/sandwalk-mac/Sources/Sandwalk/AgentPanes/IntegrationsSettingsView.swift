import SwiftUI

/// Integrations list — Edit opens a dedicated detail page per provider.
struct IntegrationsSettingsView: View {
    @State private var items: [IntegrationSummaryDTO] = []
    @State private var search = ""
    @State private var error: String?
    @State private var busy = false

    @Environment(\.sandwalkTheme) private var theme

    var filtered: [IntegrationSummaryDTO] {
        let q = search.trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
        guard !q.isEmpty else { return items }
        return items.filter {
            $0.name.lowercased().contains(q)
                || $0.key.lowercased().contains(q)
                || $0.category.lowercased().contains(q)
        }
    }

    var body: some View {
        AgentAPIGate {
            VStack(alignment: .leading, spacing: 0) {
                WebUIManagementCallout(topic: "integrations", path: "integrations")

                AgentSearchField(text: $search)
                SettingsSectionHeader("INTEGRATIONS", subtitle: "\(filtered.count) providers")
                SettingsListGroup {
                    if filtered.isEmpty {
                        SettingsRow(label: busy ? "Loading…" : "No integrations", isLast: true) {
                            EmptyView()
                        }
                    } else {
                        ForEach(Array(filtered.enumerated()), id: \.element.key) { index, item in
                            NavigationLink {
                                IntegrationDetailSettingsView(integrationKey: item.key)
                            } label: {
                                HStack {
                                    VStack(alignment: .leading, spacing: 2) {
                                        Text(item.name)
                                            .font(.sandwalk(13, weight: .medium))
                                            .foregroundStyle(theme.text)
                                        Text("\(item.category) · \(item.configured ? "configured" : "not set")")
                                            .font(.sandwalk(11.5))
                                            .foregroundStyle(theme.textSecondary)
                                    }
                                    Spacer(minLength: 8)
                                    Image(systemName: "chevron.right")
                                        .font(.system(size: 11, weight: .semibold))
                                        .foregroundStyle(theme.textTertiary)
                                }
                                .padding(.horizontal, 14)
                                .padding(.vertical, 10)
                                .frame(maxWidth: .infinity, alignment: .leading)
                                .contentShape(Rectangle())
                            }
                            .buttonStyle(.plain)
                            .overlay(alignment: .bottom) {
                                if index != filtered.count - 1 {
                                    Rectangle()
                                        .fill(theme.rowSep)
                                        .frame(height: 0.5)
                                        .padding(.horizontal, 14)
                                }
                            }
                        }
                    }
                }
                AgentPaneError(message: error)
            }
            .padding(.top, 4)
            .task { await reload() }
        }
    }

    @MainActor
    private func reload() async {
        busy = true
        error = nil
        defer { busy = false }
        do {
            items = try await SandwalkAPIClient.listIntegrations()
        } catch {
            self.error = error.localizedDescription
        }
    }
}

/// Per-integration edit page (Save / Validate / Clear).
struct IntegrationDetailSettingsView: View {
    let integrationKey: String

    @State private var item: IntegrationSummaryDTO?
    @State private var draftValues: [String: String] = [:]
    @State private var error: String?
    @State private var status: String?
    @State private var busy = false

    @Environment(\.sandwalkTheme) private var theme

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 0) {
                if let item {
                    SettingsSectionHeader(
                        item.name.uppercased(),
                        subtitle: item.description
                    )
                    SettingsListGroup {
                        SettingsRow(
                            label: "Status",
                            sublabel: "\(item.category) · \(item.source ?? "none")",
                            isLast: true
                        ) {
                            Text(item.configured ? "Configured" : "Not set")
                                .font(.sandwalk(11, weight: .medium))
                                .foregroundStyle(item.configured ? theme.successText : theme.textSecondary)
                        }
                    }

                    SettingsSectionHeader("CREDENTIALS", subtitle: "Values are written to agent config")
                    SettingsListGroup {
                        let fields = item.fields ?? []
                        if fields.isEmpty {
                            SettingsRow(
                                label: item.envVar ?? item.key,
                                sublabel: item.maskedPreview ?? "Enter value",
                                isLast: true
                            ) {
                                SecureField(
                                    "Value",
                                    text: binding(for: item.envVar ?? item.key)
                                )
                                .frame(minWidth: 160, maxWidth: 240)
                            }
                        } else {
                            ForEach(Array(fields.enumerated()), id: \.element.envVar) { index, field in
                                SettingsRow(
                                    label: field.label,
                                    sublabel: field.maskedPreview ?? field.envVar,
                                    isLast: index == fields.count - 1
                                ) {
                                    Group {
                                        if field.isSecret {
                                            SecureField("Value", text: binding(for: field.envVar))
                                        } else {
                                            TextField("Value", text: binding(for: field.envVar))
                                        }
                                    }
                                    .frame(minWidth: 160, maxWidth: 240)
                                }
                            }
                        }
                    }

                    HStack(spacing: 8) {
                        Button(busy ? "Saving…" : "Save") {
                            Task { await save(item) }
                        }
                        .buttonStyle(.sandwalk(.primary))
                        .disabled(busy)

                        Button("Validate") {
                            Task { await validate(item) }
                        }
                        .buttonStyle(.sandwalk(.normal))
                        .disabled(busy)

                        Button("Clear") {
                            Task { await clear(item) }
                        }
                        .buttonStyle(.sandwalk(.destructive))
                        .disabled(busy)

                        Spacer()
                    }
                    .padding(.horizontal, 18)
                    .padding(.top, 12)

                    if let status {
                        Text(status)
                            .font(.sandwalk(11.5))
                            .foregroundStyle(theme.textSecondary)
                            .padding(.horizontal, 18)
                            .padding(.top, 8)
                    }
                } else if busy {
                    SettingsSectionHeader("LOADING")
                    SettingsListGroup {
                        SettingsRow(label: "Fetching integration…", isLast: true) {
                            EmptyView()
                        }
                    }
                }

                AgentPaneError(message: error)
            }
            .frame(maxWidth: 720, alignment: .topLeading)
            .frame(maxWidth: .infinity, alignment: .top)
            .padding(.top, 4)
            .padding(.bottom, 36)
        }
        .scrollContentBackground(.hidden)
        .background(theme.windowBg)
        .navigationTitle(item?.name ?? integrationKey)
        .task { await reload() }
    }

    private func binding(for key: String) -> Binding<String> {
        Binding(
            get: { draftValues[key] ?? "" },
            set: { draftValues[key] = $0 }
        )
    }

    @MainActor
    private func reload() async {
        busy = true
        error = nil
        defer { busy = false }
        do {
            let all = try await SandwalkAPIClient.listIntegrations()
            item = all.first(where: { $0.key == integrationKey })
            if item == nil {
                error = "Integration “\(integrationKey)” not found."
            }
        } catch {
            self.error = error.localizedDescription
        }
    }

    @MainActor
    private func save(_ item: IntegrationSummaryDTO) async {
        let values = draftValues.filter { !$0.value.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty }
        guard !values.isEmpty else {
            error = "Enter at least one value to save."
            return
        }
        busy = true
        defer { busy = false }
        do {
            self.item = try await SandwalkAPIClient.updateIntegration(key: item.key, values: values)
            status = "Saved."
            draftValues = [:]
            error = nil
        } catch {
            self.error = error.localizedDescription
        }
    }

    @MainActor
    private func validate(_ item: IntegrationSummaryDTO) async {
        busy = true
        defer { busy = false }
        do {
            let result = try await SandwalkAPIClient.validateIntegration(key: item.key)
            status = result.message ?? (result.ok ? "Valid" : "Invalid")
            error = result.ok ? nil : status
        } catch {
            self.error = error.localizedDescription
        }
    }

    @MainActor
    private func clear(_ item: IntegrationSummaryDTO) async {
        busy = true
        defer { busy = false }
        do {
            self.item = try await SandwalkAPIClient.removeIntegration(key: item.key)
            status = "Cleared credentials."
            draftValues = [:]
            error = nil
        } catch {
            self.error = error.localizedDescription
        }
    }
}
