import SwiftUI

// MARK: - Add / Edit Local LLM sheet

struct LocalLLMProfileSheet: View {
    enum Mode: Hashable, Identifiable {
        case create
        case edit(ModelProfileDTO)

        var id: String {
            switch self {
            case .create: return "create"
            case .edit(let profile): return "edit-\(profile.id)"
            }
        }
    }

    let mode: Mode
    var onDone: () -> Void

    @Environment(\.dismiss) var dismiss
    @Environment(\.sandwalkTheme) private var theme

    @State var label = ""
    @State var backend: LocalLLMBackend = .ollama
    @State var baseUrl = LocalLLMBackend.ollama.defaultBaseUrl
    @State var apiKey = ""
    @State var showApiKey = false
    @State var discovered: [String] = []
    @State var discoverSource: String?
    @State var discoverError: String?
    @State var discovering = false
    @State var saving = false
    @State var error: String?

    var editing: ModelProfileDTO? {
        if case .edit(let profile) = mode { return profile }
        return nil
    }

    var isCreate: Bool { editing == nil }

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            HStack {
                Text(isCreate ? "Add Local LLM" : "Edit Local LLM")
                    .font(.sandwalk(16, weight: .semibold))
                Spacer()
                Button {
                    dismiss()
                } label: {
                    Image(systemName: "xmark.circle.fill")
                        .foregroundStyle(theme.textTertiary)
                }
                .buttonStyle(.plain)
            }
            .padding(.horizontal, 20)
            .padding(.top, 18)
            .padding(.bottom, 12)

            Form {
                TextField("Label", text: $label)
                Picker("Backend", selection: $backend) {
                    ForEach(LocalLLMBackend.allCases) { option in
                        HStack(spacing: 8) {
                            LocalLLMBackendIcon(backend: option, size: 14)
                            Text("\(option.label) · \(option.hint)")
                        }
                        .tag(option)
                    }
                }
                .onChange(of: backend) { _, next in
                    applyBackendDefaults(next)
                    clearDiscover()
                }

                TextField("Base URL", text: $baseUrl)
                    .onChange(of: baseUrl) { _, _ in clearDiscover() }
                Text("Suggested: \(backend.defaultBaseUrl)")
                    .font(.sandwalk(11))
                    .foregroundStyle(theme.textTertiary)

                HStack {
                    Group {
                        if showApiKey {
                            TextField(
                                editing?.hasApiKey == true
                                    ? "API key (leave blank to keep)"
                                    : "API key (optional)",
                                text: $apiKey
                            )
                        } else {
                            SecureField(
                                editing?.hasApiKey == true
                                    ? "API key (leave blank to keep)"
                                    : "API key (optional)",
                                text: $apiKey
                            )
                        }
                    }
                    Button {
                        showApiKey.toggle()
                    } label: {
                        Image(systemName: showApiKey ? "eye.slash" : "eye")
                    }
                    .buttonStyle(.borderless)
                }

                Section {
                    HStack {
                        Text("Models")
                            .font(.sandwalk(12, weight: .medium))
                        Spacer()
                        Button {
                            Task { await discover() }
                        } label: {
                            if discovering {
                                ProgressView().controlSize(.small)
                            } else {
                                Label("Discover", systemImage: "arrow.clockwise")
                            }
                        }
                        .disabled(discovering || baseUrl.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
                    }

                    if discovered.isEmpty {
                        Text("Discover to preview models from this endpoint. After Save they appear in the model list.")
                            .font(.sandwalk(11.5))
                            .foregroundStyle(theme.textSecondary)
                    } else {
                        ScrollView {
                            LazyVStack(alignment: .leading, spacing: 0) {
                                ForEach(discovered, id: \.self) { modelId in
                                    VStack(alignment: .leading, spacing: 2) {
                                        Text(formatDiscoveredModelLabel(modelId))
                                            .font(.sandwalk(12.5, weight: .medium))
                                            .lineLimit(1)
                                        Text("local · \(backend.label.lowercased())")
                                            .font(.sandwalk(11))
                                            .foregroundStyle(theme.textSecondary)
                                    }
                                    .frame(maxWidth: .infinity, alignment: .leading)
                                    .padding(.vertical, 8)
                                    Divider()
                                }
                            }
                        }
                        .frame(maxHeight: 180)
                        .padding(.horizontal, 4)
                        .background(
                            RoundedRectangle(cornerRadius: 8, style: .continuous)
                                .stroke(theme.rowSep, lineWidth: 0.5)
                        )

                        if let discoverSource {
                            Text("Found \(discovered.count) via \(discoverSource). After Save, all appear in the model list.")
                                .font(.sandwalk(11))
                                .foregroundStyle(theme.textSecondary)
                        }
                    }

                    if let discoverError {
                        Text(discoverError)
                            .font(.sandwalk(11.5))
                            .foregroundStyle(.red)
                    }
                }
            }
            .formStyle(.grouped)
            .padding(.horizontal, 4)

            if let error {
                Text(error)
                    .font(.sandwalk(11.5))
                    .foregroundStyle(.red)
                    .padding(.horizontal, 20)
            }

            HStack {
                Spacer()
                Button("Cancel") {
                    dismiss()
                }
                .buttonStyle(.sandwalk(.normal))
                Button(saving ? "Saving…" : "Save") {
                    Task { await save() }
                }
                .buttonStyle(.sandwalk(.primary))
                .disabled(saving)
                .keyboardShortcut(.defaultAction)
            }
            .padding(20)
        }
        .frame(width: 520, height: 620)
        .background(theme.windowBg)
        .onAppear { seedForm() }
    }
}
