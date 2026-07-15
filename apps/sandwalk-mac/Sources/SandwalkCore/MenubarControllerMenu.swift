import AppKit

extension MenubarController {
    func sendImage() -> NSImage? {
        NSImage(systemSymbolName: Self.sendIconName, accessibilityDescription: "Send")
    }

    func buildMenu() {
        statusHeader = NSMenuItem(title: "Sandwalk is stopped", action: nil, keyEquivalent: "")
        statusHeader.isEnabled = false
        menu.addItem(statusHeader)

        menu.addItem(.separator())

        // Placeholder — replaced in rebuildAgentsSection().
        let recentAnchor = NSMenuItem(title: "Recent Agents", action: nil, keyEquivalent: "")
        recentAnchor.isEnabled = false
        menu.addItem(recentAnchor)
        agentsSectionItems = [recentAnchor]

        menu.addItem(.separator())

        newAgentItem = NSMenuItem(
            title: "New Agent",
            action: #selector(newAgent),
            keyEquivalent: "n"
        )
        newAgentItem.keyEquivalentModifierMask = [.command]
        newAgentItem.target = self
        newAgentItem.image = sendImage()
        menu.addItem(newAgentItem)

        dashboardItem = NSMenuItem(
            title: "Open Web Dashboard",
            action: #selector(openDashboard),
            keyEquivalent: "o"
        )
        dashboardItem.keyEquivalentModifierMask = [.command]
        dashboardItem.target = self
        dashboardItem.image = NSImage(
            systemSymbolName: "rectangle.split.2x2",
            accessibilityDescription: "Dashboard"
        )
        menu.addItem(dashboardItem)

        let settingsItem = NSMenuItem(
            title: "Settings…",
            action: #selector(openSettings),
            keyEquivalent: ","
        )
        settingsItem.keyEquivalentModifierMask = [.command]
        settingsItem.target = self
        settingsItem.image = NSImage(systemSymbolName: "gearshape", accessibilityDescription: nil)
        menu.addItem(settingsItem)

        menu.addItem(.separator())

        startItem = NSMenuItem(
            title: "Start",
            action: #selector(startAll),
            keyEquivalent: ""
        )
        startItem.target = self
        startItem.image = NSImage(systemSymbolName: "play.fill", accessibilityDescription: nil)
        menu.addItem(startItem)

        stopItem = NSMenuItem(
            title: "Stop",
            action: #selector(stopAll),
            keyEquivalent: ""
        )
        stopItem.target = self
        stopItem.image = NSImage(systemSymbolName: "pause.fill", accessibilityDescription: nil)
        menu.addItem(stopItem)

        restartItem = NSMenuItem(
            title: "Restart",
            action: #selector(restartAll),
            keyEquivalent: "r"
        )
        restartItem.keyEquivalentModifierMask = [.command]
        restartItem.target = self
        restartItem.image = NSImage(systemSymbolName: "arrow.clockwise", accessibilityDescription: nil)
        menu.addItem(restartItem)

        menu.addItem(.separator())

        let quit = NSMenuItem(
            title: "Quit Sandwalk",
            action: #selector(quitApp),
            keyEquivalent: "q"
        )
        quit.keyEquivalentModifierMask = [.command]
        quit.target = self
        quit.image = NSImage(systemSymbolName: "power", accessibilityDescription: nil)
        menu.addItem(quit)
    }

    func refreshMenuState() {
        let overall = supervisor.overall
        let (text, color) = statusPresentation(for: overall)
        statusHeader.title = text
        statusHeader.image = Self.statusDot(color: color)

        let live = overall.isLive
        let canStart: Bool
        let canStop: Bool
        let canRestart: Bool
        switch overall {
        case .stopped, .failed:
            canStart = true
            canStop = false
            canRestart = false
        case .running, .partial:
            canStart = false
            canStop = true
            canRestart = true
        case .starting, .stopping:
            canStart = false
            canStop = false
            canRestart = false
        }

        startItem.isHidden = !canStart
        startItem.isEnabled = canStart
        stopItem.isHidden = !canStop
        stopItem.isEnabled = canStop
        restartItem.isEnabled = canRestart

        let apiUp: Bool = {
            if case .running = supervisor.api.state { return true }
            return false
        }()
        let dashOk: Bool = {
            if supervisor.config.usesBundledDashboard {
                return apiUp || live
            }
            if case .running = supervisor.web.state { return true }
            return live
        }()
        dashboardItem.isEnabled = dashOk
        newAgentItem.isEnabled = apiUp && dashOk

        statusItem.button?.toolTip = text
        updateStatusIcon(for: overall)
    }
}
