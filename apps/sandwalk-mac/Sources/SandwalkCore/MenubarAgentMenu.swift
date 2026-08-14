import AppKit

extension MenubarController {
    func reloadAgentsMenu() async {
        let sessions: [AgentSessionSummary]
        if case .running = supervisor.api.state {
            sessions = await SessionsAPI.fetchRecent(config: supervisor.config)
        } else {
            sessions = []
        }
        let pinned = sessions.filter { $0.organizeLabel == "pinned" }
        let recent = sessions.filter {
            $0.organizeLabel != "pinned" && $0.organizeLabel != "archive"
        }
        rebuildAgentsSection(pinned: pinned, recent: recent)
    }

    func rebuildAgentsSection(
        pinned: [AgentSessionSummary],
        recent: [AgentSessionSummary]
    ) {
        for item in agentsSectionItems {
            menu.removeItem(item)
        }
        agentsSectionItems.removeAll()

        // Insert after status + first separator (index 2).
        var index = 2
        var built: [NSMenuItem] = []

        if !pinned.isEmpty {
            let pinnedHeader = NSMenuItem(title: "Pinned Agents", action: nil, keyEquivalent: "")
            pinnedHeader.isEnabled = false
            menu.insertItem(pinnedHeader, at: index)
            built.append(pinnedHeader)
            index += 1

            for session in pinned {
                let item = sessionMenuItem(session, showPin: true)
                menu.insertItem(item, at: index)
                built.append(item)
                index += 1
            }
        }

        let recentHeader = NSMenuItem(title: "Recent Agents", action: nil, keyEquivalent: "")
        recentHeader.isEnabled = false
        menu.insertItem(recentHeader, at: index)
        built.append(recentHeader)
        index += 1

        let primary = Array(recent.prefix(SessionsAPI.listLimit))
        let overflow = Array(recent.dropFirst(SessionsAPI.listLimit).prefix(SessionsAPI.viewMoreLimit))

        if primary.isEmpty {
            let empty = NSMenuItem(
                title: supervisor.api.state.isLive
                    ? "No recent agents"
                    : "Start Sandwalk to see agents",
                action: nil,
                keyEquivalent: ""
            )
            empty.isEnabled = false
            menu.insertItem(empty, at: index)
            built.append(empty)
            index += 1
        } else {
            for session in primary {
                let item = sessionMenuItem(session, showPin: false)
                menu.insertItem(item, at: index)
                built.append(item)
                index += 1
            }
        }

        if !overflow.isEmpty {
            let viewMore = NSMenuItem(
                title: "View More (\(overflow.count))",
                action: nil,
                keyEquivalent: ""
            )
            viewMore.isEnabled = true
            let submenu = NSMenu(title: "View More")
            for session in overflow {
                submenu.addItem(sessionMenuItem(session, showPin: false))
            }
            viewMore.submenu = submenu
            menu.insertItem(viewMore, at: index)
            built.append(viewMore)
        }

        agentsSectionItems = built
    }

    func sessionMenuItem(
        _ session: AgentSessionSummary,
        showPin: Bool
    ) -> NSMenuItem {
        let item = NSMenuItem(
            title: truncatedAgentTitle(session.title),
            action: #selector(openRecentSession(_:)),
            keyEquivalent: ""
        )
        item.target = self
        item.representedObject = session.id
        item.toolTip = session.title
        item.image = showPin
            ? NSImage(systemSymbolName: "pin.fill", accessibilityDescription: "Pinned")
            : nil
        item.isEnabled = true
        return item
    }
}

/// Caps agent titles so the status menu stays ~35% narrower than unbounded names.
private enum MenubarAgentMenuMetrics {
    static let titleLimit = 40
}

private func truncatedAgentTitle(_ title: String) -> String {
    let trimmed = title.trimmingCharacters(in: .whitespacesAndNewlines)
    let limit = MenubarAgentMenuMetrics.titleLimit
    guard trimmed.count > limit else { return trimmed }
    return String(trimmed.prefix(limit - 1)).trimmingCharacters(in: .whitespaces) + "…"
}
