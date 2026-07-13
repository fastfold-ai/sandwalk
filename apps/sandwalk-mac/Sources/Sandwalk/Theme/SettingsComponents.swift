import SwiftUI

// MARK: - Section header

struct SettingsSectionHeader: View {
    let title: String
    let subtitle: String?

    @Environment(\.sandwalkTheme) private var theme

    init(_ title: String, subtitle: String? = nil) {
        self.title = title
        self.subtitle = subtitle
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 2) {
            Text(title)
                .font(.sandwalk(11, weight: .semibold))
                .foregroundStyle(theme.textSecondary)
                .textCase(.uppercase)
                .kerning(0.6)
            if let subtitle, !subtitle.isEmpty {
                Text(subtitle)
                    .font(.sandwalk(11))
                    .foregroundStyle(theme.textTertiary)
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(.horizontal, 14)
        .padding(.top, 14)
        .padding(.bottom, 6)
    }
}

// MARK: - List group (card)

struct SettingsListGroup<Content: View>: View {
    @Environment(\.sandwalkTheme) private var theme
    @ViewBuilder var content: () -> Content

    var body: some View {
        VStack(spacing: 0) {
            content()
        }
        .background(theme.groupBg)
        .clipShape(RoundedRectangle(cornerRadius: theme.cornerRadius, style: .continuous))
        .padding(.horizontal, 14)
        .padding(.bottom, 6)
    }
}

// MARK: - Row

struct SettingsRow<Trailing: View>: View {
    let label: String
    let sublabel: String?
    let isLast: Bool
    @ViewBuilder var trailing: () -> Trailing

    @Environment(\.sandwalkTheme) private var theme

    init(
        label: String,
        sublabel: String? = nil,
        isLast: Bool = false,
        @ViewBuilder trailing: @escaping () -> Trailing
    ) {
        self.label = label
        self.sublabel = sublabel
        self.isLast = isLast
        self.trailing = trailing
    }

    var body: some View {
        HStack(alignment: .center, spacing: 12) {
            VStack(alignment: .leading, spacing: 2) {
                Text(label)
                    .font(.sandwalk(13, weight: .medium))
                    .foregroundStyle(theme.text)
                if let sublabel, !sublabel.isEmpty {
                    Text(sublabel)
                        .font(.sandwalk(11.5))
                        .foregroundStyle(theme.textSecondary)
                        .fixedSize(horizontal: false, vertical: true)
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

// MARK: - Status pill

struct SettingsStatusPill: View {
    enum Status: Equatable {
        case running, starting, stopping, stopped, error, partial
    }

    let status: Status

    @Environment(\.sandwalkTheme) private var theme

    var body: some View {
        let cfg = config
        HStack(spacing: 5) {
            Circle()
                .fill(cfg.dot)
                .frame(width: 6, height: 6)
            Text(cfg.label)
                .font(.sandwalk(11, weight: .medium))
                .foregroundStyle(cfg.text)
        }
        .padding(.horizontal, 8)
        .padding(.vertical, 2.5)
        .background(Capsule().fill(cfg.bg))
    }

    private var config: (dot: Color, text: Color, bg: Color, label: String) {
        switch status {
        case .running:
            return (theme.greenDot, theme.successText, theme.successBg, "Running")
        case .starting:
            return (theme.blueDot, theme.blueDot, theme.accentSoft, "Starting")
        case .stopping:
            return (theme.amberDot, theme.warningText, theme.warningBg, "Stopping")
        case .stopped:
            return (theme.textTertiary, theme.textSecondary, theme.controlBg, "Stopped")
        case .error:
            return (theme.redDot, theme.redDot, theme.warningBg, "Error")
        case .partial:
            return (theme.amberDot, theme.warningText, theme.warningBg, "Partial")
        }
    }
}

// MARK: - Buttons

struct SettingsButtonStyle: ButtonStyle {
    enum Kind { case primary, destructive, normal }

    let kind: Kind
    @Environment(\.sandwalkTheme) private var theme
    @Environment(\.isEnabled) private var isEnabled

    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(.sandwalk(13, weight: .medium))
            .padding(.horizontal, 12)
            .padding(.vertical, 6)
            .foregroundStyle(foreground)
            .background(background)
            .clipShape(RoundedRectangle(cornerRadius: 6, style: .continuous))
            .overlay {
                if kind == .normal {
                    RoundedRectangle(cornerRadius: 6, style: .continuous)
                        .strokeBorder(theme.inputBorder, lineWidth: 0.5)
                }
            }
            .opacity(!isEnabled ? 0.45 : (configuration.isPressed ? 0.78 : 1))
    }

    private var foreground: Color {
        switch kind {
        case .primary, .destructive: return theme.accentText
        case .normal: return theme.text
        }
    }

    private var background: Color {
        switch kind {
        case .primary: return theme.accent
        case .destructive: return theme.redDot
        case .normal: return theme.controlBg
        }
    }
}

extension ButtonStyle where Self == SettingsButtonStyle {
    static func sandwalk(_ kind: SettingsButtonStyle.Kind) -> SettingsButtonStyle {
        SettingsButtonStyle(kind: kind)
    }
}

// MARK: - Compact port field

struct SettingsPortField: View {
    @Binding var value: Int
    @Environment(\.sandwalkTheme) private var theme

    var body: some View {
        TextField("", value: $value, format: .number.grouping(.never))
            .font(.sandwalkMono(13))
            .multilineTextAlignment(.trailing)
            .textFieldStyle(.plain)
            .padding(.horizontal, 8)
            .padding(.vertical, 5)
            .frame(width: 72)
            .background(theme.inputBg)
            .clipShape(RoundedRectangle(cornerRadius: 6, style: .continuous))
            .overlay(
                RoundedRectangle(cornerRadius: 6, style: .continuous)
                    .strokeBorder(theme.inputBorder, lineWidth: 0.5)
            )
    }
}
