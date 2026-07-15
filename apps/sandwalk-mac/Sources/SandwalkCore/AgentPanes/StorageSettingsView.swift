import SwiftUI

struct StorageSettingsView: View {
    @State private var report: StorageReportDTO?
    @State private var error: String?
    @State private var status: String?
    @State private var busy = false

    var body: some View {
        AgentAPIGate {
            VStack(alignment: .leading, spacing: 0) {
                SettingsSectionHeader(
                    "DISK USAGE",
                    subtitle: report.map {
                        "\(ByteFormat.string($0.totalBytes)) used"
                            + ($0.availableBytes.map { " · \(ByteFormat.string($0)) free" } ?? "")
                    } ?? "Loading…"
                )
                if let loc = report?.location {
                    SettingsListGroup {
                        SettingsRow(
                            label: loc.label ?? "Sandwalk data",
                            sublabel: loc.path,
                            isLast: true
                        ) {
                            EmptyView()
                        }
                    }
                }

                SettingsSectionHeader("CATEGORIES")
                SettingsListGroup {
                    let cats = report?.categories ?? []
                    if cats.isEmpty {
                        SettingsRow(label: busy ? "Loading…" : "No data", isLast: true) {
                            EmptyView()
                        }
                    } else {
                        ForEach(Array(cats.enumerated()), id: \.element.id) { index, cat in
                            SettingsRow(
                                label: cat.label,
                                sublabel: cat.path,
                                isLast: index == cats.count - 1
                            ) {
                                Text(ByteFormat.string(cat.bytes))
                                    .font(.sandwalkMono(12))
                                    .foregroundStyle(.secondary)
                            }
                        }
                    }
                }

                if let db = report?.database {
                    SettingsSectionHeader(
                        "AGENT DATABASE",
                        subtitle: db.exists
                            ? "SQLite store for sessions, messages, and MCP rows."
                            : "No agent-server.db yet — it is created on first serve."
                    )
                    SettingsListGroup {
                        SettingsRow(
                            label: "Path",
                            sublabel: db.path,
                            isLast: false
                        ) {
                            EmptyView()
                        }
                        SettingsRow(
                            label: "Disk usage",
                            sublabel: diskUsageSublabel(db),
                            isLast: false
                        ) {
                            Text(ByteFormat.string(db.bytes + db.walBytes + db.shmBytes))
                                .font(.sandwalkMono(12))
                                .foregroundStyle(.secondary)
                        }
                        SettingsRow(
                            label: "Integrity",
                            sublabel: integritySublabel(db),
                            isLast: false
                        ) {
                            Text(db.integrity == "ok" ? "OK" : "Check")
                                .font(.sandwalk(12, weight: .semibold))
                                .foregroundStyle(db.integrity == "ok" ? .green : .orange)
                        }
                        SettingsRow(
                            label: "Contents",
                            sublabel: contentsSublabel(db),
                            isLast: false
                        ) {
                            EmptyView()
                        }
                        SettingsRow(
                            label: "Backup",
                            sublabel: backupSublabel(db),
                            isLast: false
                        ) {
                            Text(db.backupIntegrity ?? "—")
                                .font(.sandwalkMono(11))
                                .foregroundStyle(.secondary)
                        }
                        SettingsRow(
                            label: "Auto-heal",
                            sublabel: db.autoHealEnabled
                                ? "On — corrupt DB is quarantined and restored on serve start."
                                : "Off — serve refuses to start if the DB is corrupt.",
                            isLast: true
                        ) {
                            Text(db.autoHealEnabled ? "On" : "Off")
                                .font(.sandwalk(12, weight: .medium))
                                .foregroundStyle(.secondary)
                        }
                    }
                }

                HStack(spacing: 8) {
                    Button("Clear cache") { Task { await clearCache() } }
                        .buttonStyle(.sandwalk(.destructive))
                        .disabled(busy)
                    Spacer()
                    Button(busy ? "Probing…" : "Refresh") { Task { await reload() } }
                        .buttonStyle(.sandwalk(.normal))
                        .disabled(busy)
                }
                .padding(.horizontal, 18)
                .padding(.top, 12)

                if let status {
                    Text(status)
                        .font(.sandwalk(11.5))
                        .foregroundStyle(.secondary)
                        .padding(.horizontal, 18)
                        .padding(.top, 6)
                }
                AgentPaneError(message: error)
            }
            .padding(.top, 4)
            .task { await reload() }
        }
    }

    private func diskUsageSublabel(_ db: StorageDatabaseProbeDTO) -> String {
        var parts = ["db \(ByteFormat.string(db.bytes))"]
        if db.walBytes > 0 { parts.append("wal \(ByteFormat.string(db.walBytes))") }
        if db.shmBytes > 0 { parts.append("shm \(ByteFormat.string(db.shmBytes))") }
        if let pages = db.pageCount, let size = db.pageSize {
            parts.append("\(pages) × \(size) B pages")
        }
        if let mode = db.journalMode {
            parts.append(mode)
        }
        return parts.joined(separator: " · ")
    }

    private func integritySublabel(_ db: StorageDatabaseProbeDTO) -> String {
        if db.integrity == "ok" {
            if db.quarantineCount > 0 {
                return "PRAGMA integrity_check passed · \(db.quarantineCount) old corrupt copies kept"
            }
            return "PRAGMA integrity_check passed"
        }
        return db.integrity
    }

    private func contentsSublabel(_ db: StorageDatabaseProbeDTO) -> String {
        let sessions = db.sessionCount.map(String.init) ?? "—"
        let messages = db.messageCount.map(String.init) ?? "—"
        var text = "\(sessions) sessions · \(messages) messages"
        if db.quarantineCount > 0 {
            text += " · \(db.quarantineCount) quarantined corrupt copies"
        }
        return text
    }

    private func backupSublabel(_ db: StorageDatabaseProbeDTO) -> String {
        if let path = db.backupPath {
            return "\(path) · \(ByteFormat.string(db.backupBytes))"
        }
        return "No ~/.sandwalk/agent-server.db.recovered backup yet"
    }

    @MainActor
    private func reload() async {
        busy = true
        error = nil
        defer { busy = false }
        do {
            report = try await SandwalkAPIClient.getStorage()
            if let db = report?.database {
                status = db.integrity == "ok"
                    ? "Database probe OK."
                    : "Database probe reported: \(db.integrity)"
            }
        } catch {
            self.error = error.localizedDescription
        }
    }

    @MainActor
    private func clearCache() async {
        busy = true
        defer { busy = false }
        do {
            try await SandwalkAPIClient.clearCache()
            status = "Runtime cache cleared."
            await reload()
        } catch {
            self.error = error.localizedDescription
        }
    }
}
