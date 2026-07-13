import Foundation

/// Shared handle so Settings panes can restart the supervised processes.
@MainActor
enum SandwalkRuntime {
    static weak var supervisor: SandwalkSupervisor?

    static var config: AppConfig {
        supervisor?.config ?? AppConfig.load()
    }
}
