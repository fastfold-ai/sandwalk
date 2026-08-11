import SwiftUI

struct StatusMetricRow<Trailing: View>: View {
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

struct MemoryUsageBar: View {
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
