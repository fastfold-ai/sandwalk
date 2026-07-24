import AppKit

@MainActor
public final class AppDelegate: NSObject, NSApplicationDelegate {
    public override init() {
        super.init()
    }

    private var supervisor: SandwalkSupervisor?
    private var menubar: MenubarController?
    private var controlPlane: ControlPlane?
    private var cmdQMonitor: Any?

    public func applicationDidFinishLaunching(_ notification: Notification) {
        NSApp.setActivationPolicy(.accessory)

        let config = AppConfig.load()
        let supervisor = SandwalkSupervisor(config: config)
        self.supervisor = supervisor
        SandwalkRuntime.supervisor = supervisor

        let plane = ControlPlane()
        self.controlPlane = plane
        plane.start()

        self.menubar = MenubarController(
            supervisor: supervisor,
            requestQuit: { [weak self] in
                Task { @MainActor in
                    SandwalkRuntime.allowTerminate = true
                    await self?.supervisor?.stopAll()
                    NSApp.terminate(nil)
                }
            },
            openSettings: {
                // Server manager: Settings opens the Swift Server panes.
                SettingsWindowController.shared.show()
            }
        )

        // Prefer swallowing ⌘Q over canceling terminate — AppKit leaves the
        // status item dead after `.terminateCancel` unless we reinstall it.
        cmdQMonitor = NSEvent.addLocalMonitorForEvents(matching: .keyDown) { [weak self] event in
            guard let self, self.shouldInterceptCmdQ(event) else { return event }
            self.dismissToMenubarOnly()
            return nil
        }

        if config.autoStartOnLaunch {
            do {
                try supervisor.startAll()
            } catch {
                NSLog("Sandwalk: auto-start failed — \(error.localizedDescription)")
            }
        }

        let args = ProcessInfo.processInfo.arguments
        if args.contains("--open-settings")
            || ProcessInfo.processInfo.environment["SANDWALK_OPEN_SETTINGS"] == "1"
        {
            DispatchQueue.main.async {
                SettingsWindowController.shared.show()
            }
        }
    }

    public func application(_ application: NSApplication, open urls: [URL]) {
        for url in urls {
            handleDeepLink(url)
        }
    }

    public func applicationWillTerminate(_ notification: Notification) {
        if let cmdQMonitor {
            NSEvent.removeMonitor(cmdQMonitor)
            self.cmdQMonitor = nil
        }
        controlPlane?.stop()
        supervisor?.reapSync()
    }

    public func applicationShouldTerminate(_ sender: NSApplication) -> NSApplication.TerminateReply {
        if SandwalkRuntime.allowTerminate {
            return .terminateNow
        }
        if AppConfig.load().keepMenubarOnCmdQ {
            // App menu Quit / other terminate paths — cancel and repair the
            // status item (click handling often breaks after cancel).
            dismissToMenubarOnly()
            return .terminateCancel
        }
        return .terminateNow
    }

    private func shouldInterceptCmdQ(_ event: NSEvent) -> Bool {
        guard !SandwalkRuntime.allowTerminate else { return false }
        guard AppConfig.load().keepMenubarOnCmdQ else { return false }
        let flags = event.modifierFlags.intersection(.deviceIndependentFlagsMask)
        guard flags == .command else { return false }
        return event.charactersIgnoringModifiers?.lowercased() == "q"
    }

    /// Close Settings / hide UI and stay as a menu-bar accessory.
    private func dismissToMenubarOnly() {
        SettingsWindowController.shared.close()
        for window in NSApp.windows where window.isVisible {
            window.orderOut(nil)
        }
        // Defer policy flip + status-item repair so we are outside AppKit's
        // terminate/key handling critical section. Switching activation policy
        // (and canceling terminate) often leaves NSStatusItem unclickable.
        DispatchQueue.main.async { [weak self] in
            if NSApp.activationPolicy() != .accessory {
                NSApp.setActivationPolicy(.accessory)
            }
            self?.menubar?.reinstallStatusItem()
        }
    }

    public func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool {
        false
    }

    /// Dock / Launchpad click while already running → open Settings.
    public func applicationShouldHandleReopen(
        _ sender: NSApplication,
        hasVisibleWindows flag: Bool
    ) -> Bool {
        SettingsWindowController.shared.show()
        return true
    }

    /// `sandwalk://settings/security` → Settings → Security (and other sections).
    private func handleDeepLink(_ url: URL) {
        guard url.scheme?.lowercased() == "sandwalk" else { return }
        let section = SettingsSection.fromDeepLink(url)
        DispatchQueue.main.async {
            SettingsWindowController.shared.show(section: section)
        }
    }
}
