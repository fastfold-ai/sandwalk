import AppKit

@MainActor
final class AppDelegate: NSObject, NSApplicationDelegate {
    private var server: ServerProcess?
    private var menubar: MenubarController?

    func applicationDidFinishLaunching(_ notification: Notification) {
        // Menubar-only: hide Dock icon.
        NSApp.setActivationPolicy(.accessory)

        let config = AppConfig.load()
        let server = ServerProcess(config: config)
        self.server = server
        self.menubar = MenubarController(
            server: server,
            config: config,
            requestQuit: { [weak self] in
                Task { @MainActor in
                    await self?.server?.stop()
                    NSApp.terminate(nil)
                }
            }
        )

        if config.autoStartOnLaunch {
            do {
                _ = try server.start()
            } catch {
                NSLog("Sandwalk: auto-start failed — \(error.localizedDescription)")
            }
        }
    }

    func applicationWillTerminate(_ notification: Notification) {
        // Best-effort sync stop; async stop already used on Quit menu.
        server?.reapSync(timeout: 5)
    }

    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool {
        false
    }
}
