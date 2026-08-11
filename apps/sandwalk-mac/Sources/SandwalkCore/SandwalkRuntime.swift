import Foundation

/// Shared handle so Settings panes can restart the supervised processes.
@MainActor
enum SandwalkRuntime {
    static weak var supervisor: SandwalkSupervisor?
    /// Set before `NSApp.terminate` from Quit Sandwalk so ⌘Q keep-alive does not cancel.
    static var allowTerminate = false

    static var config: AppConfig {
        supervisor?.config ?? AppConfig.load()
    }
}
