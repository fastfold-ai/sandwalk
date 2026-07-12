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
        self.menubar = MenubarController(
            supervisor: supervisor,
            requestQuit: { [weak self] in
                Task { @MainActor in
                    await self?.supervisor?.stopAll()
                    NSApp.terminate(nil)
                }
            }
        )

        if config.autoStartOnLaunch {
            do {
                try supervisor.startAll()
            } catch {
                NSLog("Sandwalk: auto-start failed — \(error.localizedDescription)")
            }
        }
    }

    func applicationWillTerminate(_ notification: Notification) {
        supervisor?.reapSync()
    }

    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool {
        false
    }
}
