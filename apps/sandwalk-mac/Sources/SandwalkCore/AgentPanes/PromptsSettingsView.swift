import SwiftUI

/// Live estimate of input token context for the current runtime + specialist allowlist.
struct PromptsSettingsView: View {
    @Environment(\.sandwalkTheme) private var theme

    @State private var specialists: [SpecialistDTO] = []
    @State private var specialistId = ""
    @State private var budget: PromptBudgetResponseDTO?
    @State private var error: String?
    @State private var loading = false
    @State private var refreshing = false

    private var selectedSpecialist: SpecialistDTO? {
        specialists.first { $0.id == specialistId }
    }

    private var isEstimating: Bool { loading || refreshing }

    private var toolCap: Int { budget?.toolCounts.openaiCap ?? 128 }
    private var totalTools: Int { budget?.toolCounts.total ?? 0 }
    private var toolShare: Double {
        min(100, (Double(totalTools) / Double(max(toolCap, 1))) * 100)
    }

    var body: some View {
        AgentAPIGate {
            content
        }
    }

    private var content: some View {
        VStack(alignment: .leading, spacing: 0) {
            HStack(alignment: .top) {
                SettingsSectionHeader(
                    "CONTEXT",
                    subtitle: "Live estimate of input token context for the current runtime and specialist allowlist."
                )
                Spacer(minLength: 8)
                Button {
                    Task { await fetchBudget(soft: budget != nil) }
                } label: {
                    Image(systemName: "arrow.clockwise")
                }
                .buttonStyle(.sandwalk(.normal))
                .disabled(isEstimating)
                .help("Refresh prompt budget")
                .padding(.trailing, 18)
                .padding(.top, 10)
            }

            SettingsSectionHeader("SPECIALIST", subtitle: "Experiment with a specialist allowlist")
            SettingsListGroup {
                SettingsRow(label: "Profile", isLast: true) {
                    Picker("", selection: $specialistId) {
                        Text("None (defaults)").tag("")
                        ForEach(specialists) { item in
                            Text(item.name).tag(item.id)
                        }
                    }
                    .labelsHidden()
                    .frame(minWidth: 180, maxWidth: 280)
                    .onChange(of: specialistId) { _, _ in
                        Task { await fetchBudget(soft: budget != nil) }
                    }
                }
            }

            if let error {
                AgentPaneError(message: error)
            }

            if isEstimating && budget == nil {
                SettingsSectionHeader("ESTIMATE", subtitle: "Building the runtime prompt and tool schemas…")
                SettingsListGroup {
                    SettingsRow(label: "Estimating…", isLast: true) {
                        ProgressView()
                            .controlSize(.small)
                    }
                }
            } else if let budget {
                estimateSections(budget)
            }
        }
        .padding(.top, 4)
        .task {
            await loadSpecialists()
            await fetchBudget(soft: false)
        }
    }

    @ViewBuilder
    private func estimateSections(_ budget: PromptBudgetResponseDTO) -> some View {
        let opacity = isEstimating ? 0.45 : 1.0
        let flatBuckets = Self.flattenBuckets(budget.buckets, total: max(budget.totalTokens, 1))

        Group {
            SettingsSectionHeader(
                "INPUT TOKEN CONTEXT",
                subtitle: metaLine(budget)
            )
            SettingsListGroup {
                SettingsRow(
                    label: formatTokens(budget.totalTokens),
                    sublabel: "\(budget.totalChars.formatted()) chars · \(budget.tokenizer)",
                    isLast: true
                ) {
                    if let name = selectedSpecialist?.name ?? budget.specialistName {
                        Text(name)
                            .font(.sandwalk(11.5))
                            .foregroundStyle(theme.textSecondary)
                    }
                }
            }

            if !flatBuckets.isEmpty {
                SettingsSectionHeader("BREAKDOWN", subtitle: "Share of estimated input tokens")
                SettingsListGroup {
                    ForEach(Array(flatBuckets.enumerated()), id: \.element.id) { index, row in
                        SettingsRow(
                            label: row.label,
                            sublabel: "\(formatTokens(row.tokens)) · \(String(format: "%.0f", row.share))%",
                            isLast: index == flatBuckets.count - 1
                        ) {
                            EmptyView()
                        }
                    }
                }
            }

            SettingsSectionHeader(
                "TOOL COUNTS",
                subtitle: "\(totalTools) / \(toolCap) toward the OpenAI tools cap"
            )
            SettingsListGroup {
                SettingsRow(label: "Domain", isLast: false) {
                    Text("\(budget.toolCounts.domain)")
                        .font(.sandwalkMono(12))
                        .foregroundStyle(theme.textSecondary)
                }
                SettingsRow(label: "MCP", isLast: false) {
                    Text("\(budget.toolCounts.mcp)")
                        .font(.sandwalkMono(12))
                        .foregroundStyle(theme.textSecondary)
                }
                SettingsRow(label: "Deep agents", isLast: false) {
                    Text("\(budget.toolCounts.deepagents)")
                        .font(.sandwalkMono(12))
                        .foregroundStyle(theme.textSecondary)
                }
                SettingsRow(
                    label: "Total",
                    sublabel: String(format: "%.0f%% of cap", toolShare),
                    isLast: true
                ) {
                    Text("\(budget.toolCounts.total)")
                        .font(.sandwalkMono(12))
                        .foregroundStyle(totalTools > toolCap ? Color.orange : theme.textSecondary)
                }
            }

            if !budget.warnings.isEmpty {
                SettingsSectionHeader("WARNINGS")
                SettingsListGroup {
                    ForEach(Array(budget.warnings.enumerated()), id: \.offset) { index, warning in
                        SettingsRow(label: warning, isLast: index == budget.warnings.count - 1) {
                            EmptyView()
                        }
                    }
                }
            }
        }
        .opacity(opacity)
    }

    private struct FlatBucketRow: Identifiable {
        let id: String
        let label: String
        let tokens: Int
        let share: Double
    }

    private static func flattenBuckets(
        _ buckets: [PromptBudgetBucketDTO],
        total: Int,
        depth: Int = 0,
        pathPrefix: String = ""
    ) -> [FlatBucketRow] {
        var rows: [FlatBucketRow] = []
        for bucket in buckets {
            let share = total > 0 ? (Double(bucket.tokens) / Double(total)) * 100 : 0
            let indent = String(repeating: "  ", count: depth)
            let countSuffix = bucket.count.map { " ×\($0)" } ?? ""
            let path = pathPrefix.isEmpty ? bucket.id : "\(pathPrefix)/\(bucket.id)"
            rows.append(
                FlatBucketRow(
                    id: path,
                    label: "\(indent)\(bucket.label)\(countSuffix)",
                    tokens: bucket.tokens,
                    share: share
                )
            )
            rows.append(contentsOf: flattenBuckets(bucket.children, total: total, depth: depth + 1, pathPrefix: path))
        }
        return rows
    }

    private func metaLine(_ budget: PromptBudgetResponseDTO) -> String {
        var parts: [String] = []
        if !budget.toolMode.isEmpty { parts.append(budget.toolMode) }
        if let model = budget.model, !model.isEmpty { parts.append(model) }
        if let provider = budget.provider, !provider.isEmpty { parts.append(provider) }
        return parts.isEmpty ? "Estimated assembled input" : parts.joined(separator: " · ")
    }

    private func formatTokens(_ value: Int) -> String {
        if value >= 1_000_000 { return String(format: "%.1fM", Double(value) / 1_000_000) }
        if value >= 10_000 { return "\(value / 1000)k" }
        if value >= 1000 { return String(format: "%.1fk", Double(value) / 1000) }
        return "\(value)"
    }

    @MainActor
    private func loadSpecialists() async {
        do {
            specialists = try await SandwalkAPIClient.listSpecialists()
                .filter(\.enabled)
                .sorted { $0.name.localizedCaseInsensitiveCompare($1.name) == .orderedAscending }
        } catch {
            specialists = []
        }
    }

    @MainActor
    private func fetchBudget(soft: Bool) async {
        if soft { refreshing = true } else { loading = true }
        error = nil
        defer {
            loading = false
            refreshing = false
        }
        do {
            budget = try await SandwalkAPIClient.getPromptBudget(
                specialistId: specialistId.isEmpty ? nil : specialistId
            )
        } catch {
            self.error = error.localizedDescription
            if !soft { budget = nil }
        }
    }
}
