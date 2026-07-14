import Darwin
import SwiftUI

/// Sandbox list — Local and Modal each open a detail page (matches web).
struct SandboxSettingsView: View {
    @Environment(\.sandwalkTheme) private var theme

    @State private var modalConfigured = false
    @State private var busy = false
    @State private var error: String?

    var body: some View {
        AgentAPIGate {
            VStack(alignment: .leading, spacing: 0) {
                WebUIManagementCallout(topic: "Sandbox", path: "agent/sandbox")

                SettingsSectionHeader(
                    "SANDBOX",
                    subtitle: "Chats default to Local Sandbox. Enable Modal per chat in the composer."
                )
                SettingsListGroup {
                    NavigationLink {
                        LocalSandboxDetailView()
                    } label: {
                        sandboxListLabel(
                            title: "Local Sandbox",
                            subtitle: "Python environment on this Mac — interpreter, packages, and local compute.",
                            badge: "Default"
                        )
                    }
                    .buttonStyle(.plain)

                    Divider().padding(.leading, 14)

                    NavigationLink {
                        ModalSandboxDetailView()
                    } label: {
                        sandboxListLabel(
                            title: "Modal Sandbox",
                            subtitle: modalConfigured
                                ? "Cloud compute on Modal — credentials, CPU/GPU, images, and pip packages."
                                : "Not configured — set Modal tokens under Integrations first.",
                            badge: modalConfigured ? nil : "Setup needed"
                        )
                    }
                    .buttonStyle(.plain)
                }

                AgentPaneError(message: error)
                Spacer(minLength: 0)
            }
            .padding(.top, 4)
            .task { await loadMeta() }
        }
    }

    @ViewBuilder
    private func sandboxListLabel(title: String, subtitle: String, badge: String?) -> some View {
        HStack(alignment: .center, spacing: 12) {
            VStack(alignment: .leading, spacing: 2) {
                HStack(spacing: 8) {
                    Text(title)
                        .font(.sandwalk(13, weight: .medium))
                        .foregroundStyle(theme.text)
                    if let badge {
                        Text(badge)
                            .font(.sandwalk(10, weight: .semibold))
                            .foregroundStyle(badge == "Default" ? Color.green : Color.orange)
                            .padding(.horizontal, 6)
                            .padding(.vertical, 2)
                            .background(
                                (badge == "Default" ? Color.green : Color.orange).opacity(0.15)
                            )
                            .clipShape(RoundedRectangle(cornerRadius: 4, style: .continuous))
                    }
                }
                Text(subtitle)
                    .font(.sandwalk(11.5))
                    .foregroundStyle(theme.textTertiary)
                    .fixedSize(horizontal: false, vertical: true)
            }
            Spacer(minLength: 8)
            Image(systemName: "chevron.right")
                .font(.system(size: 11, weight: .semibold))
                .foregroundStyle(theme.textTertiary)
        }
        .padding(.horizontal, 14)
        .padding(.vertical, 12)
        .contentShape(Rectangle())
    }

    @MainActor
    private func loadMeta() async {
        busy = true
        error = nil
        defer { busy = false }
        do {
            let settings = try await SandwalkAPIClient.getSandboxSettings()
            modalConfigured = settings.modalConfigured
        } catch {
            self.error = error.localizedDescription
        }
    }
}

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

// MARK: - Modal detail

struct ModalSandboxDetailView: View {
    private struct CpuPreset: Identifiable {
        let id: String
        let cpu: Double
        let ram: Double
        let label: String
    }

    private struct GpuPreset: Identifiable {
        var id: String { gpu }
        let gpu: String
        let vram: Int
        let cpu: Double
        let ram: Double
        let label: String
    }

    /// Matches `apps/local-web/src/lib/sandbox-presets.ts`.
    private static let cpuPresets: [CpuPreset] = [
        .init(id: "2c8g", cpu: 2, ram: 8, label: "2 CPU cores · 8 GB RAM"),
        .init(id: "4c16g", cpu: 4, ram: 16, label: "4 CPU cores · 16 GB RAM"),
        .init(id: "8c32g", cpu: 8, ram: 32, label: "8 CPU cores · 32 GB RAM"),
        .init(id: "16c64g", cpu: 16, ram: 64, label: "16 CPU cores · 64 GB RAM"),
    ]

    private static let gpuPresets: [GpuPreset] = [
        .init(gpu: "T4", vram: 16, cpu: 8, ram: 32, label: "T4 · 16 GB VRAM · 8 CPU · 32 GB RAM"),
        .init(gpu: "L4", vram: 24, cpu: 8, ram: 32, label: "L4 · 24 GB VRAM · 8 CPU · 32 GB RAM"),
        .init(gpu: "A10", vram: 24, cpu: 8, ram: 32, label: "A10 · 24 GB VRAM · 8 CPU · 32 GB RAM"),
        .init(gpu: "L40S", vram: 48, cpu: 16, ram: 64, label: "L40S · 48 GB VRAM · 16 CPU · 64 GB RAM"),
        .init(gpu: "A100", vram: 80, cpu: 16, ram: 64, label: "A100 · 80 GB VRAM · 16 CPU · 64 GB RAM"),
        .init(gpu: "RTX-PRO-6000", vram: 48, cpu: 16, ram: 64, label: "RTX-PRO-6000 · 48 GB VRAM · 16 CPU · 64 GB RAM"),
        .init(gpu: "H100", vram: 80, cpu: 16, ram: 64, label: "H100 · 80 GB VRAM · 16 CPU · 64 GB RAM"),
        .init(gpu: "H200", vram: 141, cpu: 16, ram: 64, label: "H200 · 141 GB VRAM · 16 CPU · 64 GB RAM"),
    ]

    private static let defaultCpuPreset = cpuPresets[0]
    private static let defaultGpuPreset = gpuPresets[0]

    @State private var saved = SandboxSettingsDTO.defaults
    @State private var draft = SandboxSettingsDTO.defaults
    @State private var loaded = false
    @State private var busy = false
    @State private var statusMessage: String?
    @State private var error: String?

    @Environment(\.sandwalkTheme) private var theme

    private var isDirty: Bool {
        guard loaded else { return false }
        return draft.modalApp != saved.modalApp
            || draft.cpuImage != saved.cpuImage
            || draft.gpuImage != saved.gpuImage
            || draft.pipPackages != saved.pipPackages
            || draft.computeType != saved.computeType
            || draft.gpuClass != saved.gpuClass
            || draft.cpuCores != saved.cpuCores
            || draft.ramGb != saved.ramGb
            || draft.idleTtlSeconds != saved.idleTtlSeconds
    }

    private var matchedCpuPresetId: String? {
        Self.cpuPresets.first {
            Int($0.cpu.rounded()) == Int(draft.cpuCores.rounded())
                && Int($0.ram.rounded()) == Int(draft.ramGb.rounded())
        }?.id
    }

    private var selectedGpuPreset: GpuPreset {
        Self.gpuPresets.first { $0.gpu == draft.gpuClass.trimmingCharacters(in: .whitespacesAndNewlines) }
            ?? Self.defaultGpuPreset
    }

    private var cpuPresetBinding: Binding<String> {
        Binding(
            get: { matchedCpuPresetId ?? "custom" },
            set: { id in
                guard id != "custom",
                      let preset = Self.cpuPresets.first(where: { $0.id == id })
                else { return }
                draft.computeType = "cpu"
                draft.cpuCores = preset.cpu
                draft.ramGb = preset.ram
            }
        )
    }

    private var gpuPresetBinding: Binding<String> {
        Binding(
            get: { selectedGpuPreset.gpu },
            set: { gpu in
                let preset = Self.gpuPresets.first { $0.gpu == gpu } ?? Self.defaultGpuPreset
                draft.computeType = "gpu"
                draft.gpuClass = preset.gpu
                draft.cpuCores = preset.cpu
                draft.ramGb = preset.ram
            }
        )
    }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 0) {
                SettingsSectionHeader(
                    "MODAL SANDBOX",
                    subtitle: "Configure Modal compute, images, and packages. Chats enable Modal per session in the composer."
                )

                SettingsListGroup {
                    SettingsRow(
                        label: "Modal tokens",
                        sublabel: draft.modalConfigured
                            ? "Configured via Integrations → Modal"
                            : "Missing — set under Integrations → Modal",
                        isLast: true
                    ) {
                        Image(systemName: draft.modalConfigured ? "checkmark.circle.fill" : "exclamationmark.triangle.fill")
                            .foregroundStyle(draft.modalConfigured ? Color.green : Color.orange)
                    }
                }

                SettingsSectionHeader("COMPUTE", subtitle: "Default profile for chats that enable Modal Sandbox.")
                SettingsListGroup {
                    SettingsRow(label: "App name", sublabel: "modal.App.lookup name") {
                        TextField("", text: $draft.modalApp)
                            .textFieldStyle(.roundedBorder)
                            .frame(width: 160)
                    }
                    SettingsRow(label: "Mode", sublabel: "CPU or GPU profile") {
                        Picker("", selection: computeBinding) {
                            Text("CPU").tag("cpu")
                            Text("GPU").tag("gpu")
                        }
                        .labelsHidden()
                        .pickerStyle(.segmented)
                        .frame(width: 120)
                    }
                    if draft.computeType == "gpu" {
                        SettingsRow(
                            label: "GPU preset",
                            sublabel: "Modal accelerator + attached CPU/RAM"
                        ) {
                            Picker("", selection: gpuPresetBinding) {
                                ForEach(Self.gpuPresets) { preset in
                                    Text(preset.label).tag(preset.gpu)
                                }
                            }
                            .labelsHidden()
                            .pickerStyle(.menu)
                            .frame(minWidth: 260, alignment: .trailing)
                        }
                    } else {
                        SettingsRow(
                            label: "CPU preset",
                            sublabel: "Valid CPU · RAM combinations"
                        ) {
                            Picker("", selection: cpuPresetBinding) {
                                ForEach(Self.cpuPresets) { preset in
                                    Text(preset.label).tag(preset.id)
                                }
                                if matchedCpuPresetId == nil {
                                    Text("\(Int(draft.cpuCores.rounded())) CPU cores · \(Int(draft.ramGb.rounded())) GB RAM")
                                        .tag("custom")
                                }
                            }
                            .labelsHidden()
                            .pickerStyle(.menu)
                            .frame(minWidth: 220, alignment: .trailing)
                        }
                    }
                    SettingsRow(
                        label: "Idle TTL (s)",
                        sublabel: "Terminate after idle (60–86400).",
                        isLast: true
                    ) {
                        SettingsNumberField(value: $draft.idleTtlSeconds, width: 80)
                    }
                }

                SettingsSectionHeader(
                    "IMAGES",
                    subtitle: "Defaults: python:3.12-slim (CPU), pytorch/pytorch:2.4.0-cuda12.4-cudnn9-runtime (GPU)."
                )
                SettingsListGroup {
                    SettingsRow(label: "CPU image", sublabel: "Base image for CPU sandboxes") {
                        TextField("", text: $draft.cpuImage)
                            .textFieldStyle(.roundedBorder)
                            .frame(minWidth: 180, maxWidth: 280)
                    }
                    SettingsRow(label: "GPU image", sublabel: "Base image for GPU sandboxes", isLast: true) {
                        TextField("", text: $draft.gpuImage)
                            .textFieldStyle(.roundedBorder)
                            .frame(minWidth: 180, maxWidth: 280)
                    }
                }

                SettingsSectionHeader(
                    "PIP PACKAGES",
                    subtitle: "Installed into the Modal image for sandbox execute / skill scripts."
                )
                SettingsListGroup {
                    SettingsRow(label: "Packages", sublabel: "Comma-separated", isLast: true) {
                        TextField("", text: $draft.pipPackages)
                            .textFieldStyle(.roundedBorder)
                            .frame(minWidth: 220, maxWidth: 360)
                    }
                }

                HStack(spacing: 12) {
                    Button("Save") {
                        Task { await apply() }
                    }
                    .buttonStyle(.borderedProminent)
                    .controlSize(.small)
                    .disabled(!loaded || !isDirty || busy)

                    if busy {
                        ProgressView().controlSize(.small)
                    }
                    if let statusMessage {
                        Text(statusMessage)
                            .font(.callout)
                            .foregroundStyle(.secondary)
                    }
                    Spacer()
                }
                .padding(.horizontal, 18)
                .padding(.top, 16)

                AgentPaneError(message: error)
            }
            .padding(.top, 4)
            .padding(.bottom, 24)
        }
        .task { await load() }
    }

    private var computeBinding: Binding<String> {
        Binding(
            get: { draft.computeType == "gpu" ? "gpu" : "cpu" },
            set: { next in
                if next == "gpu" {
                    let preset = selectedGpuPreset
                    draft.computeType = "gpu"
                    draft.gpuClass = preset.gpu
                    draft.cpuCores = preset.cpu
                    draft.ramGb = preset.ram
                } else {
                    let preset = Self.cpuPresets.first { $0.id == matchedCpuPresetId }
                        ?? Self.defaultCpuPreset
                    draft.computeType = "cpu"
                    draft.cpuCores = preset.cpu
                    draft.ramGb = preset.ram
                }
            }
        )
    }

    @MainActor
    private func load() async {
        busy = true
        error = nil
        defer { busy = false }
        do {
            var next = try await SandwalkAPIClient.getSandboxSettings()
            if next.computeType == "gpu" {
                if Self.gpuPresets.first(where: { $0.gpu == next.gpuClass }) == nil {
                    let preset = Self.defaultGpuPreset
                    next.gpuClass = preset.gpu
                    next.cpuCores = preset.cpu
                    next.ramGb = preset.ram
                }
            } else if Self.cpuPresets.first(where: {
                Int($0.cpu.rounded()) == Int(next.cpuCores.rounded())
                    && Int($0.ram.rounded()) == Int(next.ramGb.rounded())
            }) == nil {
                let preset = Self.defaultCpuPreset
                next.cpuCores = preset.cpu
                next.ramGb = preset.ram
            }
            saved = next
            draft = next
            loaded = true
        } catch {
            self.error = error.localizedDescription
            loaded = false
        }
    }

    @MainActor
    private func apply() async {
        busy = true
        error = nil
        statusMessage = nil
        defer { busy = false }

        let selectedGpu: String
        let cores: Double
        let ram: Double
        if draft.computeType == "gpu" {
            let preset = selectedGpuPreset
            selectedGpu = preset.gpu
            cores = preset.cpu
            ram = preset.ram
        } else if let preset = Self.cpuPresets.first(where: { $0.id == matchedCpuPresetId }) {
            selectedGpu = draft.gpuClass.isEmpty ? Self.defaultGpuPreset.gpu : draft.gpuClass
            cores = preset.cpu
            ram = preset.ram
        } else {
            let preset = Self.defaultCpuPreset
            selectedGpu = draft.gpuClass.isEmpty ? Self.defaultGpuPreset.gpu : draft.gpuClass
            cores = preset.cpu
            ram = preset.ram
        }

        let body: [String: Any] = [
            "modalApp": draft.modalApp.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
                ? "sandwalk" : draft.modalApp,
            "cpuImage": draft.cpuImage.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
                ? "python:3.12-slim" : draft.cpuImage,
            "gpuImage": draft.gpuImage.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
                ? "pytorch/pytorch:2.4.0-cuda12.4-cudnn9-runtime" : draft.gpuImage,
            "pipPackages": draft.pipPackages,
            "computeType": draft.computeType == "gpu" ? "gpu" : "cpu",
            "gpuClass": selectedGpu,
            "cpuCores": cores,
            "ramGb": ram,
            "idleTtlSeconds": max(60, min(86400, draft.idleTtlSeconds)),
        ]

        do {
            let next = try await SandwalkAPIClient.updateSandboxSettings(body)
            saved = next
            draft = next
            statusMessage = "Saved. Modal chats use these compute and image settings."
        } catch {
            self.error = error.localizedDescription
        }
    }
}

private struct SettingsNumberField: View {
    @Binding var value: Int
    var width: CGFloat = 72
    @Environment(\.sandwalkTheme) private var theme

    var body: some View {
        TextField("", value: $value, format: .number.grouping(.never))
            .font(.sandwalkMono(13))
            .multilineTextAlignment(.trailing)
            .textFieldStyle(.plain)
            .padding(.horizontal, 8)
            .padding(.vertical, 5)
            .frame(width: width)
            .background(theme.inputBg)
            .clipShape(RoundedRectangle(cornerRadius: 6, style: .continuous))
            .overlay(
                RoundedRectangle(cornerRadius: 6, style: .continuous)
                    .strokeBorder(theme.inputBorder, lineWidth: 0.5)
            )
    }
}

private extension ProcessInfo {
    var machineHardwareName: String? {
        var size = 0
        sysctlbyname("hw.machine", nil, &size, nil, 0)
        guard size > 0 else { return nil }
        var machine = [CChar](repeating: 0, count: size)
        guard sysctlbyname("hw.machine", &machine, &size, nil, 0) == 0 else { return nil }
        return String(cString: machine)
    }
}
