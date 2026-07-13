import SwiftUI

struct StorageSettingsView: View {
    @State private var report: StorageReportDTO?
    @State private var error: String?
    @State private var status: String?
    @State private var busy = false

    var body: some View {
        AgentAPIGate {
            VStack(alignment: .leading, spacing: 0) {
                SettingsSectionHeader(
                    "DISK USAGE",
                    subtitle: report.map {
                        "\(ByteFormat.string($0.totalBytes)) used"
                            + ($0.availableBytes.map { " · \(ByteFormat.string($0)) free" } ?? "")
                    } ?? "Loading…"
                )
                if let loc = report?.location {
                    SettingsListGroup {
                        SettingsRow(
                            label: loc.label ?? "Sandwalk data",
                            sublabel: loc.path,
                            isLast: true
                        ) {
                            EmptyView()
                        }
                    }
                }

                SettingsSectionHeader("CATEGORIES")
                SettingsListGroup {
                    let cats = report?.categories ?? []
                    if cats.isEmpty {
                        SettingsRow(label: busy ? "Loading…" : "No data", isLast: true) {
                            EmptyView()
                        }
                    } else {
                        ForEach(Array(cats.enumerated()), id: \.element.id) { index, cat in
                            SettingsRow(
                                label: cat.label,
                                sublabel: cat.path,
                                isLast: index == cats.count - 1
                            ) {
                                Text(ByteFormat.string(cat.bytes))
                                    .font(.sandwalkMono(12))
                                    .foregroundStyle(.secondary)
                            }
                        }
                    }
                }

                HStack(spacing: 8) {
                    Button("Clear cache") { Task { await clearCache() } }
                        .buttonStyle(.sandwalk(.destructive))
                        .disabled(busy)
                    Spacer()
                    Button("Refresh") { Task { await reload() } }
                        .buttonStyle(.sandwalk(.normal))
                        .disabled(busy)
                }
                .padding(.horizontal, 18)
                .padding(.top, 12)

                if let status {
                    Text(status)
                        .font(.sandwalk(11.5))
                        .foregroundStyle(.secondary)
                        .padding(.horizontal, 18)
                        .padding(.top, 6)
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
            report = try await SandwalkAPIClient.getStorage()
        } catch {
            self.error = error.localizedDescription
        }
    }

    @MainActor
    private func clearCache() async {
        busy = true
        defer { busy = false }
        do {
            try await SandwalkAPIClient.clearCache()
            status = "Runtime cache cleared."
            await reload()
        } catch {
            self.error = error.localizedDescription
        }
    }
}
