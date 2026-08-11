import SwiftUI

// MARK: - Modal detail

struct ModalSandboxDetailView: View {
    @State var saved = SandboxSettingsDTO.defaults
    @State var draft = SandboxSettingsDTO.defaults
    @State var loaded = false
    @State var busy = false
    @State var statusMessage: String?
    @State var error: String?

    @Environment(\.sandwalkTheme) private var theme

    var isDirty: Bool {
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

    var matchedCpuPresetId: String? {
        ModalSandboxPresets.cpuPresets.first {
            Int($0.cpu.rounded()) == Int(draft.cpuCores.rounded())
                && Int($0.ram.rounded()) == Int(draft.ramGb.rounded())
        }?.id
    }

    var selectedGpuPreset: ModalSandboxPresets.GpuPreset {
        ModalSandboxPresets.gpuPresets.first { $0.gpu == draft.gpuClass.trimmingCharacters(in: .whitespacesAndNewlines) }
            ?? ModalSandboxPresets.defaultGpuPreset
    }

    var cpuPresetBinding: Binding<String> {
        Binding(
            get: { matchedCpuPresetId ?? "custom" },
            set: { id in
                guard id != "custom",
                      let preset = ModalSandboxPresets.cpuPresets.first(where: { $0.id == id })
                else { return }
                draft.computeType = "cpu"
                draft.cpuCores = preset.cpu
                draft.ramGb = preset.ram
            }
        )
    }

    var gpuPresetBinding: Binding<String> {
        Binding(
            get: { selectedGpuPreset.gpu },
            set: { gpu in
                let preset = ModalSandboxPresets.gpuPresets.first { $0.gpu == gpu }
                    ?? ModalSandboxPresets.defaultGpuPreset
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
                                ForEach(ModalSandboxPresets.gpuPresets) { preset in
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
                                ForEach(ModalSandboxPresets.cpuPresets) { preset in
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
                        SandboxSettingsNumberField(value: $draft.idleTtlSeconds, width: 80)
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

    var computeBinding: Binding<String> {
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
                    let preset = ModalSandboxPresets.cpuPresets.first { $0.id == matchedCpuPresetId }
                        ?? ModalSandboxPresets.defaultCpuPreset
                    draft.computeType = "cpu"
                    draft.cpuCores = preset.cpu
                    draft.ramGb = preset.ram
                }
            }
        )
    }
}
