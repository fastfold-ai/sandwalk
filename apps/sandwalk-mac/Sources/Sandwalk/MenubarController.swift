import AppKit
import QuartzCore

/// Menubar: Docker/Cursor-style menu — status, recent agents, controls.
@MainActor
final class MenubarController: NSObject, NSMenuDelegate {
    private let supervisor: SandwalkSupervisor
    private let requestQuit: () -> Void
    private let openSettingsHandler: () -> Void

    private let statusItem: NSStatusItem
    private let menu = NSMenu()

    private var statusHeader: NSMenuItem!
    private var dashboardItem: NSMenuItem!
    private var newAgentItem: NSMenuItem!
    private var startItem: NSMenuItem!
    private var stopItem: NSMenuItem!
    private var restartItem: NSMenuItem!

    /// Dynamic recent-agent rows (rebuilt on menu open).
    private var recentSectionItems: [NSMenuItem] = []

    /// Colorful Aura pulse while starting / stopping / restarting.
    private var pulseTimer: Timer?
    private var pulseStartedAt: Date?
    private var isPulsing = false
    private var iconLayer: CALayer?

    /// Lucide `Send` ≈ SF Symbol paper plane.
    private static let sendIconName = "paperplane"

    init(
        supervisor: SandwalkSupervisor,
        requestQuit: @escaping () -> Void,
        openSettings: @escaping () -> Void
    ) {
        self.supervisor = supervisor
        self.requestQuit = requestQuit
        self.openSettingsHandler = openSettings
        self.statusItem = NSStatusBar.system.statusItem(withLength: SandwalkIcon.pointSize + 6)
        super.init()

        menu.autoenablesItems = false
        configureStatusButton()

        buildMenu()
        statusItem.menu = menu
        menu.delegate = self

        NotificationCenter.default.addObserver(
            self,
            selector: #selector(stateChanged),
            name: SandwalkSupervisor.stateDidChangeNotification,
            object: supervisor
        )
        refreshMenuState()
    }

    deinit {
        pulseTimer?.invalidate()
        NotificationCenter.default.removeObserver(self)
    }

    private func configureStatusButton() {
        guard let button = statusItem.button else { return }
        button.title = ""
        button.imagePosition = .imageOnly
        button.wantsLayer = true
        button.imageScaling = .scaleProportionallyDown

        let layer = CALayer()
        layer.contentsGravity = .resizeAspect
        layer.frame = CGRect(
            x: 3,
            y: 3,
            width: SandwalkIcon.pointSize,
            height: SandwalkIcon.pointSize
        )
        layer.actions = [
            "contents": NSNull(),
            "contentsScale": NSNull(),
            "bounds": NSNull(),
            "position": NSNull(),
        ]
        button.layer?.addSublayer(layer)
        iconLayer = layer

        button.image = SandwalkIcon.menubarMark()
    }

    private func sendImage() -> NSImage? {
        NSImage(systemSymbolName: Self.sendIconName, accessibilityDescription: "Send")
    }

    private func buildMenu() {
        statusHeader = NSMenuItem(title: "Sandwalk is stopped", action: nil, keyEquivalent: "")
        statusHeader.isEnabled = false
        menu.addItem(statusHeader)

        menu.addItem(.separator())

        // Placeholder — replaced in rebuildRecentSection().
        let recentAnchor = NSMenuItem(title: "Recent Agents", action: nil, keyEquivalent: "")
        recentAnchor.isEnabled = false
        menu.addItem(recentAnchor)
        recentSectionItems = [recentAnchor]

        menu.addItem(.separator())

        newAgentItem = NSMenuItem(
            title: "New Agent",
            action: #selector(newAgent),
            keyEquivalent: "n"
        )
        newAgentItem.keyEquivalentModifierMask = [.command]
        newAgentItem.target = self
        newAgentItem.image = sendImage()
        menu.addItem(newAgentItem)

        dashboardItem = NSMenuItem(
            title: "Open Web Dashboard",
            action: #selector(openDashboard),
            keyEquivalent: "o"
        )
        dashboardItem.keyEquivalentModifierMask = [.command]
        dashboardItem.target = self
        dashboardItem.image = NSImage(
            systemSymbolName: "rectangle.split.2x2",
            accessibilityDescription: "Dashboard"
        )
        menu.addItem(dashboardItem)

        let settingsItem = NSMenuItem(
            title: "Settings…",
            action: #selector(openSettings),
            keyEquivalent: ","
        )
        settingsItem.keyEquivalentModifierMask = [.command]
        settingsItem.target = self
        settingsItem.image = NSImage(systemSymbolName: "gearshape", accessibilityDescription: nil)
        menu.addItem(settingsItem)

        menu.addItem(.separator())

        startItem = NSMenuItem(
            title: "Start",
            action: #selector(startAll),
            keyEquivalent: ""
        )
        startItem.target = self
        startItem.image = NSImage(systemSymbolName: "play.fill", accessibilityDescription: nil)
        menu.addItem(startItem)

        stopItem = NSMenuItem(
            title: "Stop",
            action: #selector(stopAll),
            keyEquivalent: ""
        )
        stopItem.target = self
        stopItem.image = NSImage(systemSymbolName: "pause.fill", accessibilityDescription: nil)
        menu.addItem(stopItem)

        restartItem = NSMenuItem(
            title: "Restart",
            action: #selector(restartAll),
            keyEquivalent: "r"
        )
        restartItem.keyEquivalentModifierMask = [.command]
        restartItem.target = self
        restartItem.image = NSImage(systemSymbolName: "arrow.clockwise", accessibilityDescription: nil)
        menu.addItem(restartItem)

        menu.addItem(.separator())

        let quit = NSMenuItem(
            title: "Quit Sandwalk",
            action: #selector(quitApp),
            keyEquivalent: "q"
        )
        quit.keyEquivalentModifierMask = [.command]
        quit.target = self
        quit.image = NSImage(systemSymbolName: "power", accessibilityDescription: nil)
        menu.addItem(quit)
    }

    func menuWillOpen(_ menu: NSMenu) {
        refreshMenuState()
        Task { @MainActor in
            await reloadRecentAgents()
        }
    }

    @objc private func stateChanged() {
        refreshMenuState()
    }

    private func refreshMenuState() {
        let overall = supervisor.overall
        let (text, color) = statusPresentation(for: overall)
        statusHeader.title = text
        statusHeader.image = Self.statusDot(color: color)

        let live = overall.isLive
        let canStart: Bool
        let canStop: Bool
        let canRestart: Bool
        switch overall {
        case .stopped, .failed:
            canStart = true
            canStop = false
            canRestart = false
        case .running, .partial:
            canStart = false
            canStop = true
            canRestart = true
        case .starting, .stopping:
            canStart = false
            canStop = false
            canRestart = false
        }

        startItem.isHidden = !canStart
        startItem.isEnabled = canStart
        stopItem.isHidden = !canStop
        stopItem.isEnabled = canStop
        restartItem.isEnabled = canRestart

        let apiUp: Bool = {
            if case .running = supervisor.api.state { return true }
            return false
        }()
        let dashOk = live || {
            if case .running = supervisor.web.state { return true }
            return false
        }()
        dashboardItem.isEnabled = dashOk
        newAgentItem.isEnabled = apiUp && dashOk

        statusItem.button?.toolTip = text
        updateStatusIcon(for: overall)
    }

    private func reloadRecentAgents() async {
        let sessions: [AgentSessionSummary]
        if case .running = supervisor.api.state {
            sessions = await SessionsAPI.fetchRecent(config: supervisor.config)
        } else {
            sessions = []
        }
        rebuildRecentSection(sessions: sessions)
    }

    private func rebuildRecentSection(sessions: [AgentSessionSummary]) {
        // Remove previous recent block.
        for item in recentSectionItems {
            menu.removeItem(item)
        }
        recentSectionItems.removeAll()

        // Insert after status + first separator (index 2).
        var index = 2
        var built: [NSMenuItem] = []

        let header = NSMenuItem(title: "Recent Agents", action: nil, keyEquivalent: "")
        header.isEnabled = false
        menu.insertItem(header, at: index)
        built.append(header)
        index += 1

        let primary = Array(sessions.prefix(SessionsAPI.listLimit))
        let overflow = Array(sessions.dropFirst(SessionsAPI.listLimit).prefix(SessionsAPI.viewMoreLimit))

        if primary.isEmpty {
            let empty = NSMenuItem(
                title: supervisor.api.state.isLive
                    ? "No recent agents"
                    : "Start Sandwalk to see agents",
                action: nil,
                keyEquivalent: ""
            )
            empty.isEnabled = false
            menu.insertItem(empty, at: index)
            built.append(empty)
            index += 1
        } else {
            for session in primary {
                let item = sessionMenuItem(session)
                menu.insertItem(item, at: index)
                built.append(item)
                index += 1
            }
        }

        if !overflow.isEmpty {
            let viewMore = NSMenuItem(
                title: "View More (\(overflow.count))",
                action: nil,
                keyEquivalent: ""
            )
            viewMore.isEnabled = true
            let submenu = NSMenu(title: "View More")
            for session in overflow {
                submenu.addItem(sessionMenuItem(session))
            }
            viewMore.submenu = submenu
            menu.insertItem(viewMore, at: index)
            built.append(viewMore)
        }

        recentSectionItems = built
    }

    private func sessionMenuItem(_ session: AgentSessionSummary) -> NSMenuItem {
        let item = NSMenuItem(
            title: session.title,
            action: #selector(openRecentSession(_:)),
            keyEquivalent: ""
        )
        item.target = self
        item.representedObject = session.id
        item.image = nil
        item.isEnabled = true
        return item
    }

    private func updateStatusIcon(for overall: SandwalkSupervisor.OverallState) {
        switch overall {
        case .starting, .stopping:
            startPulse()
            applyPulseFrame()
        default:
            stopPulse()
            showTemplateIcon()
        }
    }

    private func showTemplateIcon() {
        guard let button = statusItem.button else { return }
        iconLayer?.isHidden = true
        iconLayer?.contents = nil
        button.image = SandwalkIcon.menubarMark()
    }

    private func startPulse() {
        guard !isPulsing else { return }
        isPulsing = true
        pulseStartedAt = Date()

        if let button = statusItem.button {
            button.image = nil
            iconLayer?.isHidden = false
        }

        let timer = Timer(timeInterval: 1.0 / 60.0, repeats: true) { [weak self] _ in
            Task { @MainActor in
                self?.applyPulseFrame()
            }
        }
        RunLoop.main.add(timer, forMode: .common)
        pulseTimer = timer
    }

    private func stopPulse() {
        pulseTimer?.invalidate()
        pulseTimer = nil
        pulseStartedAt = nil
        isPulsing = false
    }

    private func applyPulseFrame() {
        guard isPulsing, let started = pulseStartedAt, let layer = iconLayer else { return }
        let phase = Date().timeIntervalSince(started)
        let scale = statusItem.button?.window?.backingScaleFactor
            ?? NSScreen.main?.backingScaleFactor
            ?? 2
        guard let cg = SandwalkIcon.rasterCGImage(phase: phase, scale: scale) else { return }
        CATransaction.begin()
        CATransaction.setDisableActions(true)
        layer.contents = cg
        layer.contentsScale = scale
        CATransaction.commit()
    }

    private func statusPresentation(
        for overall: SandwalkSupervisor.OverallState
    ) -> (String, NSColor) {
        switch overall {
        case .stopped:
            return ("Sandwalk is stopped", .secondaryLabelColor)
        case .starting:
            return ("Sandwalk is starting…", .systemOrange)
        case .running:
            return ("Sandwalk is running", .systemGreen)
        case .partial:
            return ("Sandwalk is partially running", .systemOrange)
        case .stopping:
            return ("Sandwalk is stopping…", .systemOrange)
        case .failed:
            return ("Sandwalk failed to start", .systemRed)
        }
    }

    private static func statusDot(color: NSColor, diameter: CGFloat = 8) -> NSImage {
        let size = NSSize(width: diameter + 4, height: diameter + 4)
        let image = NSImage(size: size, flipped: false) { rect in
            let inset = (rect.width - diameter) / 2
            let circle = NSRect(
                x: inset,
                y: inset,
                width: diameter,
                height: diameter
            )
            color.setFill()
            NSBezierPath(ovalIn: circle).fill()
            return true
        }
        image.isTemplate = false
        return image
    }

    @objc private func openRecentSession(_ sender: NSMenuItem) {
        guard let id = sender.representedObject as? String else { return }
        NSWorkspace.shared.open(supervisor.config.agentSessionURL(id))
    }

    @objc private func newAgent() {
        Task { @MainActor in
            do {
                // Ensure stack is up before creating.
                if !supervisor.overall.isLive {
                    try supervisor.startAll()
                }
                let session = try await SessionsAPI.createSession(config: supervisor.config)
                NSWorkspace.shared.open(supervisor.config.agentSessionURL(session.id))
            } catch {
                NSLog("Sandwalk: new agent failed — \(error.localizedDescription)")
                // Fallback: open agents home so the UI can create one.
                NSWorkspace.shared.open(supervisor.config.agentsHomeURL)
            }
        }
    }

    @objc private func startAll() {
        do {
            try supervisor.startAll()
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

    @objc private func stopAll() {
        Task { @MainActor in
            await supervisor.stopAll()
            refreshMenuState()
        }
    }

    @objc private func restartAll() {
        Task { @MainActor in
            await supervisor.stopAll()
            do {
                try supervisor.startAll()
            } catch {
                NSLog("Sandwalk: restart failed — \(error.localizedDescription)")
                let alert = NSAlert()
                alert.messageText = "Could not restart Sandwalk"
                alert.informativeText = error.localizedDescription
                alert.alertStyle = .warning
                alert.runModal()
            }
            refreshMenuState()
        }
    }

    @objc private func openDashboard() {
        NSWorkspace.shared.open(supervisor.config.dashboardHomeURL)
    }

    @objc private func openSettings() {
        openSettingsHandler()
    }

    @objc private func quitApp() {
        requestQuit()
    }
}
