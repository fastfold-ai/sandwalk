import AppKit

@MainActor
final class AppDelegate: NSObject, NSApplicationDelegate {
    private var supervisor: SandwalkSupervisor?
    private var menubar: MenubarController?

    func applicationDidFinishLaunching(_ notification: Notification) {
        NSApp.setActivationPolicy(.accessory)

        let config = AppConfig.load()
        let supervisor = SandwalkSupervisor(config: config)
        self.supervisor = supervisor
        SandwalkRuntime.supervisor = supervisor
        self.menubar = MenubarController(
            supervisor: supervisor,
            requestQuit: { [weak self] in
                Task { @MainActor in
                    await self?.supervisor?.stopAll()
                    NSApp.terminate(nil)
                }
            },
            openSettings: {
                SettingsWindowController.shared.show()
            }
        )

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

    func applicationWillTerminate(_ notification: Notification) {
        supervisor?.reapSync()
    }

    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool {
        false
    }

    /// Dock / Launchpad click while already running → open Settings.
    func applicationShouldHandleReopen(
        _ sender: NSApplication,
        hasVisibleWindows flag: Bool
    ) -> Bool {
        SettingsWindowController.shared.show()
        return true
    }
}
