import AppKit
import SwiftUI

/// Status pane — control hero + live `/v1/status` system & cache (matches web Status).
struct StatusSettingsView: View {
    @State private var overall: SandwalkSupervisor.OverallState = .stopped
    @State private var config = AppConfig.load()
    @State private var report: ServerStatusReportDTO?
    @State private var hardware = MacHardwareInfo.current()
    @State private var busy = false
    @State private var clearing = false
    @State private var confirmClear = false
    @State private var errorMessage: String?
    @State private var statusMessage: String?
    @State private var hardwareTimer: Timer?

    @Environment(\.sandwalkTheme) private var theme

    private var apiLikelyUp: Bool {
        switch overall {
        case .running, .partial: return true
        default: return false
        }
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            heroCard

            systemSection(report: report, hardware: hardware)

            if let report {
                cacheSection(report)
            } else if apiLikelyUp {
                SettingsSectionHeader("RUNTIME CACHE", subtitle: "Loading…")
                SettingsListGroup {
                    SettingsRow(label: "Fetching /v1/status…", isLast: true) {
                        ProgressView()
                            .controlSize(.small)
                    }
                }
            }

            SettingsSectionHeader("ENDPOINTS", subtitle: "Local URLs for the supervised API and dashboard.")
            SettingsListGroup {
                SettingsRow(
                    label: "Agent API",
                    sublabel: config.apiBaseURL.absoluteString
                ) {
                    Button {
                        NSWorkspace.shared.open(config.healthURL)
                    } label: {
                        Image(systemName: "arrow.up.right.square")
                    }
                    .buttonStyle(.sandwalk(.normal))
                }
                SettingsRow(
                    label: "Web dashboard",
                    sublabel: config.dashboardHomeURL.absoluteString,
                    isLast: true
                ) {
                    Button {
                        NSWorkspace.shared.open(config.dashboardHomeURL)
                    } label: {
                        Image(systemName: "arrow.up.right.square")
                    }
                    .buttonStyle(.sandwalk(.normal))
                }
            }

            if let statusMessage {
                Text(statusMessage)
                    .font(.sandwalk(11.5))
                    .foregroundStyle(theme.textSecondary)
                    .padding(.horizontal, 18)
                    .padding(.top, 8)
            }

            if let errorMessage {
                Text(errorMessage)
                    .font(.sandwalk(11.5))
                    .foregroundStyle(theme.redDot)
                    .padding(.horizontal, 18)
                    .padding(.top, 8)
            }
        }
        .padding(.top, 8)
        .onAppear {
            refresh()
            hardware = MacHardwareInfo.current()
            startHardwarePolling()
            Task { await loadReport() }
        }
        .onDisappear {
            hardwareTimer?.invalidate()
            hardwareTimer = nil
        }
        .onReceive(NotificationCenter.default.publisher(for: SandwalkSupervisor.stateDidChangeNotification)) { _ in
            refresh()
            Task { await loadReport() }
        }
        .onReceive(NotificationCenter.default.publisher(for: SandwalkSupervisor.configDidChangeNotification)) { _ in
            refresh()
            Task { await loadReport() }
        }
        .confirmationDialog(
            "Clear runtime cache?",
            isPresented: $confirmClear,
            titleVisibility: .visible
        ) {
            Button("Clear cache", role: .destructive) {
                Task { await clearCache() }
            }
            Button("Cancel", role: .cancel) {}
        } message: {
            Text("Clears temporary runtime cache files. Datasets and sessions are not deleted.")
        }
    }

    private var heroCard: some View {
        HStack(spacing: 16) {
            Image(nsImage: SandwalkIcon.menubarMark(pointSize: 52))
                .resizable()
                .interpolation(.high)
                .renderingMode(.template)
                .foregroundStyle(theme.text)
                .frame(width: 52, height: 52)

            VStack(alignment: .leading, spacing: 4) {
                HStack(spacing: 10) {
                    Text(heroTitle)
                        .font(.sandwalk(18, weight: .semibold))
                        .foregroundStyle(theme.text)
                    SettingsStatusPill(status: pillStatus)
                }
                Text(subtitle)
                    .font(.sandwalk(11.5))
                    .foregroundStyle(theme.textSecondary)
            }

            Spacer(minLength: 12)
            actionButtons
        }
        .padding(18)
        .background(theme.groupBg)
        .clipShape(RoundedRectangle(cornerRadius: 12, style: .continuous))
        .padding(.horizontal, 14)
        .padding(.bottom, 14)
    }

    private var heroTitle: String {
        if let version = report?.version, !version.isEmpty {
            return "Sandwalk \(version)"
        }
        return "Sandwalk"
    }

    @ViewBuilder
    private func systemSection(
        report: ServerStatusReportDTO?,
        hardware: MacHardwareInfo.Snapshot
    ) -> some View {
        let chip = hardware.chipName ?? report?.system.chipName
        let cores = hardware.gpuCores ?? report?.system.gpuCores
        let gpuLabel = formatGpuLabel(chip: chip, cores: cores)
        let subtitle = hardware.systemSubtitle

        SettingsSectionHeader("SYSTEM", subtitle: subtitle)
        SettingsListGroup {
            if let gpuLabel {
                StatusMetricRow(label: "GPU", isLast: false) {
                    Text(gpuLabel)
                        .font(.sandwalk(12.5))
                        .foregroundStyle(theme.textSecondary)
                        .multilineTextAlignment(.trailing)
                }
            }

            if let report {
                StatusMetricRow(label: "System RAM", isLast: false) {
                    MemoryUsageBar(
                        used: report.system.ramUsedBytes,
                        total: report.system.ramTotalBytes
                    )
                }
                StatusMetricRow(
                    label: "Load average",
                    hint: "1 · 5 · 15 minute averages",
                    isLast: false
                ) {
                    Text(formatLoadAverage(report.system.loadAverage))
                        .font(.sandwalkMono(12.5))
                        .foregroundStyle(theme.textSecondary)
                        .multilineTextAlignment(.trailing)
                }
                StatusMetricRow(label: "Thermal state", isLast: false) {
                    if let thermal = report.system.thermalState, !thermal.isEmpty {
                        HStack(spacing: 6) {
                            Circle()
                                .fill(thermal == "Nominal" ? theme.greenDot : theme.amberDot)
                                .frame(width: 6, height: 6)
                            Text(thermal)
                                .font(.sandwalk(12.5))
                                .foregroundStyle(theme.text)
                        }
                    } else {
                        Text("—")
                            .font(.sandwalk(12.5))
                            .foregroundStyle(theme.textTertiary)
                    }
                }
                StatusMetricRow(label: "Server uptime", isLast: false) {
                    Text(formatUptime(report.uptimeSeconds))
                        .font(.sandwalkMono(12.5))
                        .foregroundStyle(theme.textSecondary)
                }
                StatusMetricRow(label: "Process", isLast: false) {
                    Text(processLabel(report))
                        .font(.sandwalkMono(12.5))
                        .foregroundStyle(theme.textSecondary)
                        .multilineTextAlignment(.trailing)
                }
                StatusMetricRow(label: "Agent version", isLast: true) {
                    Text("\(report.version) · Python \(report.system.pythonVersion)")
                        .font(.sandwalkMono(12.5))
                        .foregroundStyle(theme.textSecondary)
                        .multilineTextAlignment(.trailing)
                }
            } else {
                StatusMetricRow(
                    label: "Agent metrics",
                    hint: apiLikelyUp ? "Waiting for /v1/status…" : "Start Sandwalk to load server metrics",
                    isLast: true
                ) {
                    EmptyView()
                }
            }
        }
    }

    private func startHardwarePolling() {
        hardwareTimer?.invalidate()
        hardwareTimer = Timer.scheduledTimer(withTimeInterval: 2.0, repeats: true) { _ in
            Task { @MainActor in
                hardware = MacHardwareInfo.current()
            }
        }
    }

    @ViewBuilder
    private func cacheSection(_ report: ServerStatusReportDTO) -> some View {
        SettingsSectionHeader("RUNTIME CACHE")
        SettingsListGroup {
            StatusMetricRow(label: "Cache files", isLast: false) {
                Text("\(report.cache.fileCount) \(report.cache.fileCount == 1 ? "file" : "files")")
                    .font(.sandwalk(12.5))
                    .foregroundStyle(theme.textSecondary)
            }
            StatusMetricRow(label: "Total size", isLast: false) {
                Text(formatBytes(report.cache.totalBytes))
                    .font(.sandwalkMono(12.5))
                    .foregroundStyle(theme.textSecondary)
            }
            StatusMetricRow(label: "Location", isLast: false) {
                Text(report.cache.path)
                    .font(.sandwalkMono(11))
                    .foregroundStyle(theme.textTertiary)
                    .lineLimit(2)
                    .multilineTextAlignment(.trailing)
            }
            HStack {
                Spacer()
                Button(clearing ? "Clearing…" : "Clear cache") {
                    confirmClear = true
                }
                .buttonStyle(.sandwalk(.destructive))
                .disabled(clearing || busy)
            }
            .padding(.horizontal, 14)
            .padding(.vertical, 10)
        }
    }

    @ViewBuilder
    private var actionButtons: some View {
        switch overall {
        case .running, .partial:
            HStack(spacing: 6) {
                Button {
                    Task { await restart() }
                } label: {
                    Label("Restart", systemImage: "arrow.clockwise")
                        .labelStyle(.titleAndIcon)
                }
                .buttonStyle(.sandwalk(.normal))
                .disabled(busy)

                Button {
                    Task { await stop() }
                } label: {
                    Label("Stop", systemImage: "stop.fill")
                        .labelStyle(.titleAndIcon)
                }
                .buttonStyle(.sandwalk(.destructive))
                .disabled(busy)
            }

        case .starting, .stopping:
            Button("Working…") {}
                .buttonStyle(.sandwalk(.normal))
                .disabled(true)

        case .stopped, .failed:
            Button {
                Task { await start() }
            } label: {
                Label("Start Sandwalk", systemImage: "play.fill")
                    .labelStyle(.titleAndIcon)
            }
            .buttonStyle(.sandwalk(.primary))
            .disabled(busy)
        }
    }

    private var pillStatus: SettingsStatusPill.Status {
        switch overall {
        case .running: return .running
        case .starting: return .starting
        case .stopping: return .stopping
        case .stopped: return .stopped
        case .failed: return .error
        case .partial: return .partial
        }
    }

    private var subtitle: String {
        if let report, apiLikelyUp {
            if let message = report.message, !message.isEmpty {
                return message
            }
            if let host = report.host, let port = report.port {
                return "Listening on \(host):\(port)"
            }
        }
        switch overall {
        case .running:
            return "API \(config.connectableHost):\(config.port) · UI :\(config.dashboardPort)"
        case .partial(let api, let web):
            return "API \(api ? "up" : "down") · Web \(web ? "up" : "down")"
        case .failed(let message):
            return message
        case .starting:
            return "Starting API and dashboard…"
        case .stopping:
            return "Stopping…"
        case .stopped:
            return "Stopped — start from here or the menu bar"
        }
    }

    private func refresh() {
        overall = SandwalkRuntime.supervisor?.overall ?? .stopped
        config = SandwalkRuntime.config
        if !apiLikelyUp {
            report = nil
        }
    }

    @MainActor
    private func loadReport() async {
        guard apiLikelyUp else {
            report = nil
            return
        }
        do {
            report = try await SandwalkAPIClient.serverStatus()
            if errorMessage?.contains("/v1/status") == true || errorMessage?.hasPrefix("HTTP") == true {
                errorMessage = nil
            }
        } catch {
            // Keep control surface usable even if metrics fail.
            if report == nil {
                errorMessage = error.localizedDescription
            }
        }
    }

    @MainActor
    private func clearCache() async {
        clearing = true
        statusMessage = nil
        defer { clearing = false }
        do {
            _ = try await SandwalkAPIClient.clearRuntimeCache()
            await loadReport()
            statusMessage = "Runtime cache cleared."
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    @MainActor
    private func start() async {
        guard let supervisor = SandwalkRuntime.supervisor else {
            errorMessage = "Supervisor unavailable."
            return
        }
        busy = true
        errorMessage = nil
        defer { busy = false }
        do {
            try supervisor.startAll()
        } catch {
            errorMessage = error.localizedDescription
        }
        refresh()
        // Give serve a moment before polling status.
        try? await Task.sleep(nanoseconds: 800_000_000)
        await loadReport()
    }

    @MainActor
    private func stop() async {
        busy = true
        defer { busy = false }
        await SandwalkRuntime.supervisor?.stopAll()
        refresh()
        report = nil
    }

    @MainActor
    private func restart() async {
        guard let supervisor = SandwalkRuntime.supervisor else { return }
        busy = true
        errorMessage = nil
        defer { busy = false }
        do {
            try await supervisor.restartAll()
        } catch {
            errorMessage = error.localizedDescription
        }
        refresh()
        try? await Task.sleep(nanoseconds: 800_000_000)
        await loadReport()
    }

    private func processLabel(_ report: ServerStatusReportDTO) -> String {
        if let host = report.host, let port = report.port {
            return "pid \(report.pid) · \(host):\(port)"
        }
        return "pid \(report.pid)"
    }

    private func formatGpuLabel(chip: String?, cores: Int?) -> String? {
        let name = chip?.trimmingCharacters(in: .whitespacesAndNewlines)
        let hasChip = name.map { !$0.isEmpty } ?? false
        let hasCores = (cores ?? 0) > 0
        switch (hasChip, hasCores) {
        case (true, true):
            return "\(name!) · \(cores!) cores"
        case (true, false):
            return name
        case (false, true):
            return "\(cores!) cores"
        case (false, false):
            return nil
        }
    }

    private func formatLoadAverage(_ values: [Double]?) -> String {
        guard let values, !values.isEmpty else { return "—" }
        return values.map { String(format: "%.2f", $0) }.joined(separator: " · ")
    }

    private func formatUptime(_ seconds: Double) -> String {
        let total = max(0, Int(seconds.rounded(.down)))
        let days = total / 86_400
        let hours = (total % 86_400) / 3_600
        let minutes = (total % 3_600) / 60
        let secs = total % 60
        if days > 0 { return "\(days)d \(hours)h \(minutes)m" }
        if hours > 0 { return "\(hours)h \(minutes)m" }
        if minutes > 0 { return "\(minutes)m \(secs)s" }
        return "\(secs)s"
    }

    private func formatBytes(_ bytes: Int64) -> String {
        let formatter = ByteCountFormatter()
        formatter.countStyle = .file
        formatter.allowedUnits = [.useKB, .useMB, .useGB, .useTB]
        return formatter.string(fromByteCount: max(0, bytes))
    }
}

private struct StatusMetricRow<Trailing: View>: View {
    let label: String
    var hint: String? = nil
    var isLast: Bool = false
    @ViewBuilder var trailing: () -> Trailing

    @Environment(\.sandwalkTheme) private var theme

    var body: some View {
        HStack(alignment: .center, spacing: 12) {
            VStack(alignment: .leading, spacing: 2) {
                Text(label)
                    .font(.sandwalk(13, weight: .medium))
                    .foregroundStyle(theme.text)
                if let hint, !hint.isEmpty {
                    Text(hint)
                        .font(.sandwalk(11))
                        .foregroundStyle(theme.textTertiary)
                }
            }
            Spacer(minLength: 12)
            trailing()
        }
        .padding(.horizontal, 14)
        .padding(.vertical, 10)
        .frame(minHeight: 36)
        .overlay(alignment: .bottom) {
            if !isLast {
                Rectangle()
                    .fill(theme.rowSep)
                    .frame(height: 0.5)
                    .padding(.horizontal, 14)
            }
        }
    }
}

private struct MemoryUsageBar: View {
    let used: Int64
    let total: Int64

    @Environment(\.sandwalkTheme) private var theme

    private var fraction: CGFloat {
        guard total > 0 else { return 0 }
        return CGFloat(min(1, Double(used) / Double(total)))
    }

    var body: some View {
        HStack(spacing: 10) {
            GeometryReader { geo in
                ZStack(alignment: .leading) {
                    Capsule().fill(theme.controlBg)
                    Capsule()
                        .fill(theme.text.opacity(0.7))
                        .frame(width: max(geo.size.width * fraction, fraction > 0 ? 2 : 0))
                }
            }
            .frame(width: 110, height: 6)

            Text("\(format(used)) / \(format(total))")
                .font(.sandwalkMono(11.5))
                .foregroundStyle(theme.textSecondary)
                .fixedSize()
        }
    }

    private func format(_ bytes: Int64) -> String {
        let formatter = ByteCountFormatter()
        formatter.countStyle = .memory
        formatter.allowedUnits = [.useGB]
        formatter.includesUnit = true
        return formatter.string(fromByteCount: max(0, bytes))
    }
}
