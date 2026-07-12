import SwiftUI

/// Menubar host for Sandwalk.
/// Owns Start/Stop for the agent API and web dashboard together.
@main
struct SandwalkApp: App {
    @NSApplicationDelegateAdaptor(AppDelegate.self) var appDelegate

    var body: some Scene {
        Settings {
            TabView {
                SecuritySettingsView()
                    .tabItem {
                        Label("Security", systemImage: "lock.fill")
                    }
            }
            .frame(minWidth: 560, minHeight: 360)
        }
    }
}
