import SwiftUI

/// Agent Runtime pane — LangGraph loop, tool mode, traces, timeouts, health.
/// Apply persists via `/v1/settings/runtime` then restarts services so the agent reloads config.
struct RuntimeSettingsView: View {
    @State private var saved = RuntimeSettingsDTO.defaults
    @State private var draft = RuntimeSettingsDTO.defaults
    @State private var loaded = false
    @State private var busy = false
    @State private var statusMessage: String?
    @State private var error: String?

    @Environment(\.sandwalkTheme) private var theme

    private var isDirty: Bool {
        guard loaded else { return false }
        return draft.toolMode != saved.toolMode
            || draft.groupToolTraces != saved.groupToolTraces
            || draft.toolTraceDetailLimit != saved.toolTraceDetailLimit
            || draft.backgroundWatchTimeoutS != saved.backgroundWatchTimeoutS
            || draft.interruptDrainTimeoutS != saved.interruptDrainTimeoutS
            || draft.parallelMaxThreads != saved.parallelMaxThreads
            || draft.toolHealthEnabled != saved.toolHealthEnabled
            || draft.toolHealthFailThreshold != saved.toolHealthFailThreshold
            || draft.toolHealthSuppressSeconds != saved.toolHealthSuppressSeconds
    }

    var body: some View {
        AgentAPIGate {
            VStack(alignment: .leading, spacing: 0) {
                SettingsSectionHeader(
                    "TOOL CALLING",
                    subtitle: "PTC keeps domain tools behind run_python; native exposes each tool schema."
                )
                SettingsListGroup {
                    SettingsRow(label: "Tool mode", sublabel: "Programmatic vs per-tool schemas") {
                        Picker("", selection: toolModeBinding) {
                            Text("PTC").tag("ptc")
                            Text("Native").tag("native")
                        }
                        .labelsHidden()
                        .pickerStyle(.segmented)
                        .frame(width: 160)
                    }
                    SettingsRow(
                        label: "Parallel max threads",
                        sublabel: "Cap for parallel specialist / fan-out work (1–20).",
                        isLast: true
                    ) {
                        SettingsNumberField(value: $draft.parallelMaxThreads, width: 80)
                    }
                }

                SettingsSectionHeader(
                    "TOOL TRACES",
                    subtitle: "Control how consecutive tool calls collapse in the transcript."
                )
                SettingsListGroup {
                    SettingsRow(
                        label: "Group tool traces",
                        sublabel: "Collapse older calls; keep the latest ones detailed."
                    ) {
                        Toggle("", isOn: $draft.groupToolTraces)
                            .labelsHidden()
                            .toggleStyle(.switch)
                    }
                    SettingsRow(
                        label: "Trace detail limit",
                        sublabel: "How many recent tool calls keep full args/output (1–50).",
                        isLast: true
                    ) {
                        SettingsNumberField(value: $draft.toolTraceDetailLimit, width: 80)
                            .disabled(!draft.groupToolTraces)
                            .opacity(draft.groupToolTraces ? 1 : 0.45)
                    }
                }

                SettingsSectionHeader(
                    "TIMEOUTS",
                    subtitle: "Background watches and interrupt drain windows for long-running work."
                )
                SettingsListGroup {
                    SettingsRow(
                        label: "Background watch",
                        sublabel: "Max wait in seconds (60–86400)."
                    ) {
                        SettingsNumberField(value: $draft.backgroundWatchTimeoutS, width: 88)
                    }
                    SettingsRow(
                        label: "Interrupt drain",
                        sublabel: "Seconds to finish in-flight work after stop (1–120).",
                        isLast: true
                    ) {
                        SettingsNumberField(value: $draft.interruptDrainTimeoutS, width: 80)
                    }
                }

                SettingsSectionHeader(
                    "TOOL HEALTH",
                    subtitle: "Temporarily suppress tools that fail repeatedly during a session."
                )
                SettingsListGroup {
                    SettingsRow(
                        label: "Enable tool health",
                        sublabel: "Auto-suppress flaky tools after repeated failures."
                    ) {
                        Toggle("", isOn: $draft.toolHealthEnabled)
                            .labelsHidden()
                            .toggleStyle(.switch)
                    }
                    SettingsRow(
                        label: "Fail threshold",
                        sublabel: "Failures before a tool is suppressed (1–20)."
                    ) {
                        SettingsNumberField(value: $draft.toolHealthFailThreshold, width: 80)
                            .disabled(!draft.toolHealthEnabled)
                            .opacity(draft.toolHealthEnabled ? 1 : 0.45)
                    }
                    SettingsRow(
                        label: "Suppress seconds",
                        sublabel: "How long a suppressed tool stays off (30–86400).",
                        isLast: true
                    ) {
                        SettingsNumberField(value: $draft.toolHealthSuppressSeconds, width: 88)
                            .disabled(!draft.toolHealthEnabled)
                            .opacity(draft.toolHealthEnabled ? 1 : 0.45)
                    }
                }

                AgentPaneError(message: error)

                HStack {
                    if let statusMessage {
                        Text(statusMessage)
                            .font(.sandwalk(11.5))
                            .foregroundStyle(theme.textSecondary)
                            .lineLimit(2)
                    }
                    Spacer()
                    Button(busy ? "Applying…" : "Apply") {
                        Task { await apply() }
                    }
                    .buttonStyle(.sandwalk(.primary))
                    .keyboardShortcut(.defaultAction)
                    .disabled(busy || !isDirty || !loaded)
                }
                .padding(.horizontal, 18)
                .padding(.top, 10)

                Text("Apply saves runtime config and restarts API + web so the agent reloads it.")
                    .font(.sandwalk(11))
                    .foregroundStyle(theme.textTertiary)
                    .padding(.horizontal, 18)
                    .padding(.top, 6)
            }
            .padding(.top, 4)
            .task { await reload() }
        }
    }

    private var toolModeBinding: Binding<String> {
        Binding(
            get: { draft.toolMode == "native" ? "native" : "ptc" },
            set: { draft.toolMode = $0 }
        )
    }

    @MainActor
    private func reload() async {
        error = nil
        do {
            let settings = try await SandwalkAPIClient.getRuntimeSettings()
            saved = settings
            draft = settings
            loaded = true
            statusMessage = nil
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

        // Recursion limit is fixed high in the agent runtime (LangGraph requires a
        // finite cap; there is no documented maximum). Do not expose or overwrite it.
        let body: [String: Any] = [
            "toolMode": draft.toolMode == "native" ? "native" : "ptc",
            "groupToolTraces": draft.groupToolTraces,
            "toolTraceDetailLimit": clamp(draft.toolTraceDetailLimit, 1, 50, 1),
            "backgroundWatchTimeoutS": clamp(draft.backgroundWatchTimeoutS, 60, 86400, 7200),
            "interruptDrainTimeoutS": clamp(draft.interruptDrainTimeoutS, 1, 120, 10),
            "parallelMaxThreads": clamp(draft.parallelMaxThreads, 1, 20, 5),
            "toolHealthEnabled": draft.toolHealthEnabled,
            "toolHealthFailThreshold": clamp(draft.toolHealthFailThreshold, 1, 20, 2),
            "toolHealthSuppressSeconds": clamp(draft.toolHealthSuppressSeconds, 30, 86400, 900),
        ]

        do {
            let next = try await SandwalkAPIClient.updateRuntimeSettings(body)
            saved = next
            draft = next

            guard let supervisor = SandwalkRuntime.supervisor else {
                statusMessage = "Saved. Start Sandwalk to apply."
                return
            }

            if supervisor.overall.isLive {
                try await supervisor.restartAll()
                statusMessage = "Applied — services restarted with new runtime."
            } else {
                statusMessage = "Saved. Start Sandwalk to apply."
            }
        } catch {
            self.error = error.localizedDescription
        }
    }

    private func clamp(_ value: Int, _ min: Int, _ max: Int, _ fallback: Int) -> Int {
        guard value != Int.min, value != Int.max else { return fallback }
        return Swift.max(min, Swift.min(max, value))
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
