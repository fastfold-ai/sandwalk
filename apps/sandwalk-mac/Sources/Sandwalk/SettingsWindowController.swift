import AppKit
import SwiftUI

/// oMLX-style settings shell: sidebar + detail for server + agent CRUD.
struct SettingsRootView: View {
    @Environment(\.colorScheme) private var colorScheme
    @State private var selection: SettingsSection?
    @State private var columnVisibility: NavigationSplitViewVisibility = .all
    @State private var theme = SandwalkTheme.current()

    init(initialSection: SettingsSection = .status) {
        _selection = State(initialValue: initialSection)
    }

    var body: some View {
        NavigationSplitView(columnVisibility: $columnVisibility) {
            List(selection: $selection) {
                Section {
                    SidebarRow(section: .status)
                    SidebarRow(section: .network)
                    SidebarRow(section: .security)
                    SidebarRow(section: .logs)
                } header: {
                    Text("Server")
                }

                Section {
                    SidebarRow(section: .models)
                    SidebarRow(section: .tools)
                    SidebarRow(section: .datasets)
                    SidebarRow(section: .skills)
                    SidebarRow(section: .specialists)
                    SidebarRow(section: .integrations)
                    SidebarRow(section: .mcps)
                } header: {
                    Text("Capabilities")
                }

                Section {
                    SidebarRow(section: .doctor)
                    SidebarRow(section: .storage)
                    SidebarRow(section: .environment)
                } header: {
                    Text("Workspace")
                }

                Section {
                    SidebarRow(section: .about)
                } header: {
                    Text("General")
                }
            }
            .listStyle(.sidebar)
            .navigationSplitViewColumnWidth(min: 180, ideal: 200, max: 240)
            .toolbar(removing: .sidebarToggle)
        } detail: {
            NavigationStack {
                SettingsDetailScaffold(section: selection ?? .status)
            }
            .toolbar {
                ToolbarItem(placement: .navigation) {
                    Button {
                        withAnimation(.easeInOut(duration: 0.2)) {
                            columnVisibility = columnVisibility == .detailOnly ? .all : .detailOnly
                        }
                    } label: {
                        Image(systemName: "sidebar.leading")
                    }
                    .help(columnVisibility == .detailOnly ? "Show Sidebar" : "Hide Sidebar")
                }
            }
        }
        .navigationSplitViewStyle(.balanced)
        .frame(minWidth: 880, minHeight: 600)
        .environment(\.sandwalkTheme, theme)
        .background(theme.windowBg)
        .onChange(of: colorScheme) { _, _ in
            theme = SandwalkTheme.current()
        }
        .onReceive(NotificationCenter.default.publisher(for: .sandwalkSelectSettingsSection)) { note in
            if let section = note.object as? SettingsSection {
                selection = section
            }
        }
    }
}

private struct SidebarRow: View {
    let section: SettingsSection

    var body: some View {
        NavigationLink(value: section) {
            Label(section.title, systemImage: section.symbol)
        }
        .tag(section)
    }
}

private struct SettingsDetailScaffold: View {
    let section: SettingsSection
    @Environment(\.sandwalkTheme) private var theme

    var body: some View {
        Group {
            switch section {
            case .logs:
                LogsSettingsView()
                    .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .top)
                    .padding(.top, 4)
                    .background(theme.windowBg)
            case .integrations:
                // Own navigation stack so Edit pushes a detail page cleanly.
                ScrollView {
                    IntegrationsSettingsView()
                        .frame(maxWidth: 720, alignment: .topLeading)
                        .frame(maxWidth: .infinity, alignment: .top)
                        .padding(.bottom, 36)
                }
                .scrollContentBackground(.hidden)
                .background(theme.windowBg)
            case .specialists:
                ScrollView {
                    SpecialistsSettingsView()
                        .frame(maxWidth: 720, alignment: .topLeading)
                        .frame(maxWidth: .infinity, alignment: .top)
                        .padding(.bottom, 36)
                }
                .scrollContentBackground(.hidden)
                .background(theme.windowBg)
            default:
                ScrollView {
                    detailContent
                        .frame(maxWidth: 720, alignment: .topLeading)
                        .frame(maxWidth: .infinity, alignment: .top)
                        .padding(.bottom, 36)
                }
                .scrollContentBackground(.hidden)
                .background(theme.windowBg)
            }
        }
        .navigationTitle(section.title)
    }

    @ViewBuilder
    private var detailContent: some View {
        switch section {
        case .models: ModelsSettingsView()
        case .tools: ToolsSettingsView()
        case .datasets: DatasetsSettingsView()
        case .skills: SkillsSettingsView()
        case .specialists: EmptyView()
        case .integrations: EmptyView()
        case .mcps: MCPsSettingsView()
        case .doctor: DoctorSettingsView()
        case .storage: StorageSettingsView()
        case .environment: EnvironmentSettingsView()
        case .status: StatusSettingsView()
        case .network: NetworkSettingsView()
        case .security: SecuritySettingsView()
        case .about: AboutSettingsView()
        case .logs: EmptyView()
        }
    }
}

/// Owns the Settings window; shows Dock while open, drops back to menubar-only when closed.
@MainActor
final class SettingsWindowController: NSObject, NSWindowDelegate {
    static let shared = SettingsWindowController()

    private var window: NSWindow?

    func show(section: SettingsSection? = nil) {
        if NSApp.activationPolicy() != .regular {
            NSApp.setActivationPolicy(.regular)
        }
        NSApp.activate(ignoringOtherApps: true)

        if let window {
            window.makeKeyAndOrderFront(nil)
            if let section {
                NotificationCenter.default.post(
                    name: .sandwalkSelectSettingsSection,
                    object: section
                )
            }
            return
        }

        let hosting = NSHostingController(
            rootView: SettingsRootView(initialSection: section ?? .status)
        )
        let win = NSWindow(
            contentRect: NSRect(x: 0, y: 0, width: 920, height: 640),
            styleMask: [.titled, .closable, .miniaturizable, .resizable],
            backing: .buffered,
            defer: false
        )
        win.title = ""
        win.titleVisibility = .hidden
        win.toolbarStyle = .unified
        win.contentViewController = hosting
        win.delegate = self
        win.isReleasedWhenClosed = false
        win.minSize = NSSize(width: 880, height: 600)
        win.center()
        win.setFrameAutosaveName("SandwalkSettingsWindow")
        win.makeKeyAndOrderFront(nil)
        self.window = win
    }

    func windowWillClose(_ notification: Notification) {
        DispatchQueue.main.async {
            if NSApp.windows.filter({ $0.isVisible && $0 !== self.window }).isEmpty {
                NSApp.setActivationPolicy(.accessory)
            }
        }
    }
}
