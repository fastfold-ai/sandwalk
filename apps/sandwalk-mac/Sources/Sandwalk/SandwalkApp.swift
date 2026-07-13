import SwiftUI

/// Menubar host for Sandwalk.
/// Owns Start/Stop for the agent API and web dashboard together.
@main
struct SandwalkApp: App {
    @NSApplicationDelegateAdaptor(AppDelegate.self) var appDelegate

    var body: some Scene {
        // Settings live in SettingsWindowController (NSWindow) — SwiftUI's
        // Settings scene + showSettingsWindow: is a no-op for accessory apps.
        Settings {
            EmptyView()
        }
    }
}
