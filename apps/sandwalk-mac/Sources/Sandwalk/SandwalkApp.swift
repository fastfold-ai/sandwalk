import SwiftUI

/// Menubar host for Sandwalk.
/// Native settings window comes later; this app owns Start/Stop of `fastfold serve`.
@main
struct SandwalkApp: App {
    @NSApplicationDelegateAdaptor(AppDelegate.self) var appDelegate

    var body: some Scene {
        // No primary window yet — menubar is the product surface for v1.
        Settings {
            EmptyView()
        }
    }
}
