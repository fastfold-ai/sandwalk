import SwiftUI

struct DoctorSettingsView: View {
    @State private var report: DoctorReportDTO?
    @State private var error: String?
    @State private var busy = false

    var body: some View {
        AgentAPIGate {
            VStack(alignment: .leading, spacing: 0) {
                if let report {
                    SettingsSectionHeader(
                        "SUMMARY",
                        subtitle: "\(report.summary.ok) ok · \(report.summary.warn) warn · \(report.summary.error) error"
                    )
                    SettingsListGroup {
                        SettingsRow(label: "Overall", sublabel: report.ok ? "Healthy" : "Issues found", isLast: true) {
                            SettingsStatusPill(status: report.ok ? .running : .error)
                        }
                    }

                    let grouped = Dictionary(grouping: report.checks, by: \.category)
                    ForEach(grouped.keys.sorted(), id: \.self) { category in
                        let checks = grouped[category] ?? []
                        SettingsSectionHeader(category.uppercased())
                        SettingsListGroup {
                            ForEach(Array(checks.enumerated()), id: \.element.id) { index, check in
                                SettingsRow(
                                    label: check.name,
                                    sublabel: check.detail + (check.fix.map { " · Fix: \($0)" } ?? ""),
                                    isLast: index == checks.count - 1
                                ) {
                                    Text(check.status.uppercased())
                                        .font(.sandwalk(10, weight: .semibold))
                                        .foregroundStyle(color(for: check.status))
                                }
                            }
                        }
                    }
                } else {
                    SettingsSectionHeader("DOCTOR", subtitle: "Run health checks against this install")
                }

                HStack {
                    Spacer()
                    Button(busy ? "Running…" : "Run checks") {
                        Task { await run() }
                    }
                    .buttonStyle(.sandwalk(.primary))
                    .disabled(busy)
                }
                .padding(.horizontal, 18)
                .padding(.top, 12)

                AgentPaneError(message: error)
            }
            .padding(.top, 4)
            .task { await run() }
        }
    }

    private func color(for status: String) -> Color {
        switch status {
        case "ok": return .green
        case "warn": return .orange
        default: return .red
        }
    }

    @MainActor
    private func run() async {
        busy = true
        error = nil
        defer { busy = false }
        do {
            report = try await SandwalkAPIClient.runDoctor()
        } catch {
            self.error = error.localizedDescription
        }
    }
}
