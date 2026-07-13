import SwiftUI

/// Agent Sandbox pane — builtin vs Modal deepagents backend.
struct SandboxSettingsView: View {
    private static let gpuClasses: [(id: String, label: String, detail: String)] = [
        ("T4", "T4", "Entry GPU · cost-efficient"),
        ("L4", "L4", "Efficient inference"),
        ("A10", "A10", "General purpose"),
        ("L40S", "L40S", "High memory / viz"),
        ("A100", "A100", "Training / large models"),
        ("A100-40GB", "A100 40GB", "40GB HBM"),
        ("A100-80GB", "A100 80GB", "80GB HBM"),
        ("H100", "H100", "Latest Hopper"),
        ("H200", "H200", "High-bandwidth HBM3e"),
        ("B200", "B200", "Blackwell"),
    ]

    @State private var saved = SandboxSettingsDTO.defaults
    @State private var draft = SandboxSettingsDTO.defaults
    @State private var loaded = false
    @State private var busy = false
    @State private var statusMessage: String?
    @State private var error: String?

    @Environment(\.sandwalkTheme) private var theme

    private var isDirty: Bool {
        guard loaded else { return false }
        return draft.backend != saved.backend
            || draft.modalApp != saved.modalApp
            || draft.pipPackages != saved.pipPackages
            || draft.computeType != saved.computeType
            || draft.gpuClass != saved.gpuClass
            || draft.cpuCores != saved.cpuCores
            || draft.ramGb != saved.ramGb
            || draft.idleTtlSeconds != saved.idleTtlSeconds
    }

    private var knownGpuIds: Set<String> {
        Set(Self.gpuClasses.map(\.id))
    }

    private var gpuClassBinding: Binding<String> {
        Binding(
            get: {
                let value = draft.gpuClass.trimmingCharacters(in: .whitespacesAndNewlines)
                return knownGpuIds.contains(value) ? value : "T4"
            },
            set: { draft.gpuClass = $0 }
        )
    }

    var body: some View {
        AgentAPIGate {
            VStack(alignment: .leading, spacing: 0) {
                SettingsSectionHeader(
                    "BACKEND",
                    subtitle: "Built-in uses the local workspace. Modal isolates execute/fs tools remotely; domain tools stay on this Mac."
                )
                SettingsListGroup {
                    SettingsRow(label: "Backend", sublabel: "Local FilesystemBackend vs ModalSandbox") {
                        Picker("", selection: backendBinding) {
                            Text("Built-in").tag("builtin")
                            Text("Modal").tag("modal")
                        }
                        .labelsHidden()
                        .pickerStyle(.segmented)
                        .frame(width: 180)
                    }
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

                if draft.backend == "modal" {
                    SettingsSectionHeader("MODAL", subtitle: "App name and compute for new sandboxes.")
                    SettingsListGroup {
                        SettingsRow(label: "App name", sublabel: "modal.App.lookup name") {
                            TextField("", text: $draft.modalApp)
                                .textFieldStyle(.roundedBorder)
                                .frame(width: 160)
                        }
                        SettingsRow(label: "Compute", sublabel: "CPU or GPU class") {
                            Picker("", selection: computeBinding) {
                                Text("CPU").tag("cpu")
                                Text("GPU").tag("gpu")
                            }
                            .labelsHidden()
                            .pickerStyle(.segmented)
                            .frame(width: 120)
                        }
                        if draft.computeType == "gpu" {
                            SettingsRow(label: "GPU class", sublabel: "Modal accelerator") {
                                Picker("", selection: gpuClassBinding) {
                                    ForEach(Self.gpuClasses, id: \.id) { option in
                                        Text("\(option.label) — \(option.detail)").tag(option.id)
                                    }
                                }
                                .labelsHidden()
                                .pickerStyle(.menu)
                                .frame(minWidth: 220, alignment: .trailing)
                            }
                        }
                        SettingsRow(label: "CPU cores", sublabel: "0.25–64") {
                            SettingsNumberField(value: cpuCoresBinding, width: 80)
                        }
                        SettingsRow(label: "RAM (GB)", sublabel: "0.5–256") {
                            SettingsNumberField(value: ramGbBinding, width: 80)
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
                }

                HStack(spacing: 12) {
                    Button("Apply") {
                        Task { await apply() }
                    }
                    .buttonStyle(.borderedProminent)
                    .disabled(!loaded || !isDirty || busy)

                    if busy {
                        ProgressView().controlSize(.small)
                    }
                    if let statusMessage {
                        Text(statusMessage)
                            .font(.callout)
                            .foregroundStyle(.secondary)
                    }
                    if let error {
                        Text(error)
                            .font(.callout)
                            .foregroundStyle(.red)
                    }
                    Spacer()
                }
                .padding(.top, 16)

                Spacer(minLength: 0)
            }
            .padding(20)
            .task { await load() }
        }
    }

    private var backendBinding: Binding<String> {
        Binding(
            get: { draft.backend == "modal" ? "modal" : "builtin" },
            set: { draft.backend = $0 }
        )
    }

    private var computeBinding: Binding<String> {
        Binding(
            get: { draft.computeType == "gpu" ? "gpu" : "cpu" },
            set: { draft.computeType = $0 }
        )
    }

    private var cpuCoresBinding: Binding<Int> {
        Binding(
            get: { Int(draft.cpuCores.rounded()) },
            set: { draft.cpuCores = Double($0) }
        )
    }

    private var ramGbBinding: Binding<Int> {
        Binding(
            get: { Int(draft.ramGb.rounded()) },
            set: { draft.ramGb = Double($0) }
        )
    }

    @MainActor
    private func load() async {
        busy = true
        error = nil
        defer { busy = false }
        do {
            var next = try await SandwalkAPIClient.getSandboxSettings()
            if !knownGpuIds.contains(next.gpuClass) {
                next.gpuClass = "T4"
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

        let selectedGpu = knownGpuIds.contains(draft.gpuClass) ? draft.gpuClass : "T4"
        let body: [String: Any] = [
            "backend": draft.backend == "modal" ? "modal" : "builtin",
            "modalApp": draft.modalApp.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
                ? "sandwalk" : draft.modalApp,
            "pipPackages": draft.pipPackages,
            "computeType": draft.computeType == "gpu" ? "gpu" : "cpu",
            "gpuClass": selectedGpu,
            "cpuCores": max(0.25, min(64.0, draft.cpuCores)),
            "ramGb": max(0.5, min(256.0, draft.ramGb)),
            "idleTtlSeconds": max(60, min(86400, draft.idleTtlSeconds)),
        ]

        do {
            let next = try await SandwalkAPIClient.updateSandboxSettings(body)
            saved = next
            draft = next
            statusMessage = "Saved. New agent sessions use this sandbox backend."
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
