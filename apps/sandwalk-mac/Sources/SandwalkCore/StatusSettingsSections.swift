import SwiftUI

extension StatusSettingsView {
    @ViewBuilder
    func systemSection(
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

    @ViewBuilder
    func cacheSection(_ report: ServerStatusReportDTO) -> some View {
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

    func processLabel(_ report: ServerStatusReportDTO) -> String {
        if let host = report.host, let port = report.port {
            return "pid \(report.pid) · \(host):\(port)"
        }
        return "pid \(report.pid)"
    }

    func formatGpuLabel(chip: String?, cores: Int?) -> String? {
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

    func formatLoadAverage(_ values: [Double]?) -> String {
        guard let values, !values.isEmpty else { return "—" }
        return values.map { String(format: "%.2f", $0) }.joined(separator: " · ")
    }

    func formatUptime(_ seconds: Double) -> String {
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

    func formatBytes(_ bytes: Int64) -> String {
        let formatter = ByteCountFormatter()
        formatter.countStyle = .file
        formatter.allowedUnits = [.useKB, .useMB, .useGB, .useTB]
        return formatter.string(fromByteCount: max(0, bytes))
    }
}
