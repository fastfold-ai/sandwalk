import AppKit

/// Menubar surface: status + Start / Stop + Open Dashboard + Quit.
@MainActor
final class MenubarController: NSObject, NSMenuDelegate {
    private let server: ServerProcess
    private let config: AppConfig
    private let requestQuit: () -> Void

    private let statusItem: NSStatusItem
    private let menu = NSMenu()

    private var statusHeader: NSMenuItem!
    private var startItem: NSMenuItem!
    private var stopItem: NSMenuItem!
    private var dashboardItem: NSMenuItem!

    init(
        server: ServerProcess,
        config: AppConfig,
        requestQuit: @escaping () -> Void
    ) {
        self.server = server
        self.config = config
        self.requestQuit = requestQuit
        self.statusItem = NSStatusBar.system.statusItem(withLength: NSStatusItem.variableLength)
        super.init()

        if let button = statusItem.button {
            button.image = NSImage(
                systemSymbolName: "figure.walk",
                accessibilityDescription: "Sandwalk"
            )
            button.image?.isTemplate = true
        }

        buildMenu()
        statusItem.menu = menu
        menu.delegate = self

        NotificationCenter.default.addObserver(
            self,
            selector: #selector(serverStateChanged),
            name: ServerProcess.stateDidChangeNotification,
            object: server
        )
        refreshMenuState()
    }

    deinit {
        NotificationCenter.default.removeObserver(self)
    }

    private func buildMenu() {
        statusHeader = NSMenuItem(
            title: "Server: Stopped",
            action: nil,
            keyEquivalent: ""
        )
        statusHeader.isEnabled = false
        menu.addItem(statusHeader)
        menu.addItem(.separator())

        startItem = NSMenuItem(
            title: "Start Server",
            action: #selector(startServer),
            keyEquivalent: ""
        )
        startItem.target = self
        startItem.image = NSImage(
            systemSymbolName: "play.fill",
            accessibilityDescription: nil
        )
        menu.addItem(startItem)

        stopItem = NSMenuItem(
            title: "Stop Server",
            action: #selector(stopServer),
            keyEquivalent: ""
        )
        stopItem.target = self
        stopItem.image = NSImage(
            systemSymbolName: "stop.fill",
            accessibilityDescription: nil
        )
        menu.addItem(stopItem)

        menu.addItem(.separator())

        dashboardItem = NSMenuItem(
            title: "Open Web Dashboard",
            action: #selector(openDashboard),
            keyEquivalent: "o"
        )
        dashboardItem.keyEquivalentModifierMask = [.command]
        dashboardItem.target = self
        dashboardItem.image = NSImage(
            systemSymbolName: "globe",
            accessibilityDescription: nil
        )
        menu.addItem(dashboardItem)

        menu.addItem(.separator())

        let quit = NSMenuItem(
            title: "Quit Sandwalk",
            action: #selector(quitApp),
            keyEquivalent: "q"
        )
        quit.keyEquivalentModifierMask = [.command]
        quit.target = self
        quit.image = NSImage(
            systemSymbolName: "power",
            accessibilityDescription: nil
        )
        menu.addItem(quit)
    }

    func menuWillOpen(_ menu: NSMenu) {
        refreshMenuState()
    }

    @objc private func serverStateChanged() {
        refreshMenuState()
    }

    private func refreshMenuState() {
        let state = server.state
        let detail: String
        switch state {
        case .running:
            detail = "Listening on \(config.connectableHost):\(config.port)"
        case .failed(let message):
            detail = message
        default:
            detail = state.label
        }
        statusHeader.title = "Server: \(state.label)"
        statusHeader.toolTip = detail

        switch state {
        case .stopped, .failed:
            startItem.isHidden = false
            stopItem.isHidden = true
        case .running, .starting:
            startItem.isHidden = true
            stopItem.isHidden = false
        case .stopping:
            startItem.isHidden = true
            stopItem.isHidden = false
            stopItem.isEnabled = false
        }

        if case .stopping = state {
            // keep disabled
        } else {
            stopItem.isEnabled = true
            startItem.isEnabled = true
        }

        if let button = statusItem.button {
            let symbol =
                state.isLive
                ? "figure.walk.motion"
                : "figure.walk"
            button.image = NSImage(
                systemSymbolName: symbol,
                accessibilityDescription: "Sandwalk"
            )
            button.image?.isTemplate = true
            button.toolTip = "Sandwalk — \(detail)"
        }
    }

    @objc private func startServer() {
        do {
            _ = try server.start()
        } catch {
            NSLog("Sandwalk: start failed — \(error.localizedDescription)")
            let alert = NSAlert()
            alert.messageText = "Could not start Sandwalk"
            alert.informativeText = error.localizedDescription
            alert.alertStyle = .warning
            alert.runModal()
        }
        refreshMenuState()
    }

    @objc private func stopServer() {
        Task { @MainActor in
            await server.stop()
            refreshMenuState()
        }
    }

    @objc private func openDashboard() {
        NSWorkspace.shared.open(config.dashboardURL)
    }

    @objc private func quitApp() {
        requestQuit()
    }
}
