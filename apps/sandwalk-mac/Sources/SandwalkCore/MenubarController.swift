import AppKit
import QuartzCore

/// Menubar: Docker/Cursor-style menu — status, recent agents, controls.
@MainActor
final class MenubarController: NSObject, NSMenuDelegate {
    let supervisor: SandwalkSupervisor
    private let requestQuit: () -> Void
    private let openSettingsHandler: () -> Void

    private(set) var statusItem: NSStatusItem
    let menu = NSMenu()

    var statusHeader: NSMenuItem!
    var dashboardItem: NSMenuItem!
    var newAgentItem: NSMenuItem!
    var startItem: NSMenuItem!
    var stopItem: NSMenuItem!
    var restartItem: NSMenuItem!

    /// Dynamic agent rows (pinned + recent; rebuilt on menu open).
    var agentsSectionItems: [NSMenuItem] = []

    /// Colorful Aura pulse while starting / stopping / restarting.
    var pulseTimer: Timer?
    var pulseStartedAt: Date?
    var isPulsing = false
    var iconLayer: CALayer?

    /// Lucide `Send` ≈ SF Symbol paper plane.
    static let sendIconName = "paperplane"

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

        iconLayer?.removeFromSuperlayer()
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

    /// AppKit often leaves `NSStatusItem` unclickable after canceling
    /// `applicationShouldTerminate` (⌘Q keep-alive). Drop and recreate it.
    func reinstallStatusItem() {
        stopPulse()
        NSStatusBar.system.removeStatusItem(statusItem)
        statusItem = NSStatusBar.system.statusItem(withLength: SandwalkIcon.pointSize + 6)
        configureStatusButton()
        statusItem.menu = menu
        menu.delegate = self
        statusItem.isVisible = true
        refreshMenuState()
    }

    func menuWillOpen(_ menu: NSMenu) {
        refreshMenuState()
        Task { @MainActor in
            await reloadAgentsMenu()
        }
    }

    @objc private func stateChanged() {
        refreshMenuState()
    }

    @objc func openRecentSession(_ sender: NSMenuItem) {
        guard let id = sender.representedObject as? String else { return }
        NSWorkspace.shared.open(supervisor.config.agentSessionURL(id))
    }

    @objc func newAgent() {
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

    @objc func startAll() {
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

    @objc func stopAll() {
        Task { @MainActor in
            await supervisor.stopAll()
            refreshMenuState()
        }
    }

    @objc func restartAll() {
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

    @objc func openDashboard() {
        NSWorkspace.shared.open(supervisor.config.dashboardHomeURL)
    }

    @objc func openSettings() {
        openSettingsHandler()
    }

    @objc func quitApp() {
        requestQuit()
    }
}
