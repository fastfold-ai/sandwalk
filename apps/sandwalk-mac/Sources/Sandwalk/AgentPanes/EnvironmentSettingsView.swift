import SwiftUI

struct EnvironmentSettingsView: View {
    @State private var report: EnvironmentReportDTO?
    @State private var error: String?
    @State private var status: String?
    @State private var busy = false

    var body: some View {
        AgentAPIGate {
            VStack(alignment: .leading, spacing: 0) {
                SettingsSectionHeader(
                    "PYTHON ENVIRONMENT",
                    subtitle: report.map {
                        "\($0.pythonPath ?? "—") · \(ByteFormat.string($0.envBytes ?? 0))"
                    } ?? "Loading…"
                )
                if let report {
                    ForEach(report.groups) { group in
                        SettingsSectionHeader(group.label.uppercased(), subtitle: group.description)
                        SettingsListGroup {
                            ForEach(Array(group.packages.enumerated()), id: \.element.name) { index, pkg in
                                SettingsRow(
                                    label: pkg.name,
                                    sublabel: pkg.installed
                                        ? (pkg.version.map { "v\($0)" } ?? "installed")
                                        : "not installed",
                                    isLast: index == group.packages.count - 1
                                ) {
                                    if pkg.installed {
                                        Button("Uninstall") {
                                            Task { await uninstall(pkg.name) }
                                        }
                                        .buttonStyle(.sandwalk(.destructive))
                                        .disabled(busy || !pkg.removable)
                                    } else {
                                        Button("Install") {
                                            Task { await install(pkg.name) }
                                        }
                                        .buttonStyle(.sandwalk(.primary))
                                        .disabled(busy)
                                    }
                                }
                            }
                        }
                    }
                }

                HStack {
                    Spacer()
                    Button("Refresh") { Task { await reload() } }
                        .buttonStyle(.sandwalk(.normal))
                        .disabled(busy)
                }
                .padding(.horizontal, 18)
                .padding(.top, 10)

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
            report = try await SandwalkAPIClient.getEnvironment()
        } catch {
            self.error = error.localizedDescription
        }
    }

    @MainActor
    private func install(_ name: String) async {
        busy = true
        defer { busy = false }
        do {
            let result = try await SandwalkAPIClient.installPackage(name: name)
            status = result.message ?? "Installed \(name)."
            await reload()
        } catch {
            self.error = error.localizedDescription
        }
    }

    @MainActor
    private func uninstall(_ name: String) async {
        busy = true
        defer { busy = false }
        do {
            let result = try await SandwalkAPIClient.uninstallPackage(name: name)
            status = result.message ?? "Uninstalled \(name)."
            await reload()
        } catch {
            self.error = error.localizedDescription
        }
    }
}
