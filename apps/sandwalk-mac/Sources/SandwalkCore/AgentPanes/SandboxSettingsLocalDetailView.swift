import Darwin
import SwiftUI

// MARK: - Local detail

struct LocalSandboxDetailView: View {
    @Environment(\.sandwalkTheme) private var theme

    @State private var hardware = MacHardwareInfo.current()
    @State private var status: ServerStatusReportDTO?
    @State private var env: EnvironmentReportDTO?
    @State private var busy = false
    @State private var error: String?
    @State private var actionStatus: String?

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 0) {
                SettingsSectionHeader(
                    "LOCAL SANDBOX",
                    subtitle: "Python environment the agent uses for Local Sandbox chats on this Mac."
                )

                SettingsSectionHeader("THIS MACHINE", subtitle: hardware.systemSubtitle)
                SettingsListGroup {
                    SettingsRow(
                        label: "Chip",
                        sublabel: hardware.chipName
                            ?? status?.system.chipName
                            ?? "—"
                    ) { EmptyView() }
                    SettingsRow(
                        label: "System RAM",
                        sublabel: ramLabel
                    ) { EmptyView() }
                    if let cores = hardware.gpuCores ?? status?.system.gpuCores {
                        SettingsRow(
                            label: "GPU cores",
                            sublabel: "\(cores)",
                            isLast: true
                        ) { EmptyView() }
                    } else {
                        SettingsRow(
                            label: "Arch",
                            sublabel: status?.system.arch ?? ProcessInfo.processInfo.machineHardwareName ?? "—",
                            isLast: true
                        ) { EmptyView() }
                    }
                }

                SettingsSectionHeader(
                    "PYTHON ENVIRONMENT",
                    subtitle: env.map {
                        "\($0.pythonPath ?? "—") · \(ByteFormat.string($0.envBytes ?? 0))"
                    } ?? (busy ? "Loading…" : "—")
                )

                if let env {
                    ForEach(env.groups) { group in
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

                if let actionStatus {
                    Text(actionStatus)
                        .font(.sandwalk(11.5))
                        .foregroundStyle(.secondary)
                        .padding(.horizontal, 18)
                        .padding(.top, 6)
                }
                AgentPaneError(message: error)
            }
            .padding(.top, 4)
            .padding(.bottom, 24)
        }
        .task { await reload() }
    }

    private var ramLabel: String {
        if let status {
            return "\(ByteFormat.string(status.system.ramUsedBytes)) / \(ByteFormat.string(status.system.ramTotalBytes))"
        }
        let total = ProcessInfo.processInfo.physicalMemory
        return ByteFormat.string(Int64(total))
    }

    @MainActor
    private func reload() async {
        busy = true
        error = nil
        defer { busy = false }
        hardware = MacHardwareInfo.current()
        do {
            async let statusTask = SandwalkAPIClient.serverStatus()
            async let envTask = SandwalkAPIClient.getEnvironment()
            status = try await statusTask
            env = try await envTask
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
            actionStatus = result.message ?? "Installed \(name)."
            env = try await SandwalkAPIClient.getEnvironment()
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
            actionStatus = result.message ?? "Uninstalled \(name)."
            env = try await SandwalkAPIClient.getEnvironment()
        } catch {
            self.error = error.localizedDescription
        }
    }
}

extension ProcessInfo {
    var machineHardwareName: String? {
        var size = 0
        sysctlbyname("hw.machine", nil, &size, nil, 0)
        guard size > 0 else { return nil }
        var machine = [CChar](repeating: 0, count: size)
        guard sysctlbyname("hw.machine", &machine, &size, nil, 0) == 0 else { return nil }
        return String(cString: machine)
    }
}
