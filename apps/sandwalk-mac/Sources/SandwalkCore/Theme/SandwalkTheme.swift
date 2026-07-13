import AppKit
import SwiftUI

/// Design tokens mirroring oMLX’s settings chrome (system-dynamic colors).
struct SandwalkTheme: Sendable {
    let isDark: Bool
    let windowBg: Color
    let groupBg: Color
    let rowSep: Color
    let text: Color
    let textSecondary: Color
    let textTertiary: Color
    let accent: Color
    let accentSoft: Color
    let accentText: Color
    let controlBg: Color
    let inputBg: Color
    let inputBorder: Color
    let greenDot: Color
    let amberDot: Color
    let redDot: Color
    let blueDot: Color
    let successBg: Color
    let successText: Color
    let warningBg: Color
    let warningText: Color
    let codeBg: Color
    let cornerRadius: CGFloat = 14

    static func current() -> SandwalkTheme {
        let dark = NSApp.effectiveAppearance.bestMatch(from: [.darkAqua, .aqua]) == .darkAqua
        return dark ? .dark : .light
    }

    static let light = SandwalkTheme(
        isDark: false,
        windowBg: Color(nsColor: .windowBackgroundColor),
        groupBg: Color(nsColor: .labelColor).opacity(0.035),
        rowSep: Color(nsColor: .separatorColor),
        text: Color(nsColor: .labelColor),
        textSecondary: Color(nsColor: .secondaryLabelColor),
        textTertiary: Color(nsColor: .tertiaryLabelColor),
        accent: Color(nsColor: .controlAccentColor),
        accentSoft: Color(nsColor: .controlAccentColor).opacity(0.16),
        accentText: Color(nsColor: .alternateSelectedControlTextColor),
        controlBg: Color(nsColor: .controlColor),
        inputBg: Color(nsColor: .textBackgroundColor),
        inputBorder: Color(nsColor: .separatorColor),
        greenDot: Color(nsColor: .systemGreen),
        amberDot: Color(nsColor: .systemOrange),
        redDot: Color(nsColor: .systemRed),
        blueDot: Color(nsColor: .controlAccentColor),
        successBg: Color(nsColor: .systemGreen).opacity(0.16),
        successText: Color(nsColor: .systemGreen),
        warningBg: Color(nsColor: .systemOrange).opacity(0.16),
        warningText: Color(nsColor: .systemOrange),
        codeBg: Color(nsColor: .labelColor).opacity(0.05)
    )

    static let dark = SandwalkTheme(
        isDark: true,
        windowBg: Color(nsColor: .underPageBackgroundColor),
        groupBg: Color(nsColor: .labelColor).opacity(0.03),
        rowSep: Color(nsColor: .separatorColor),
        text: Color(nsColor: .labelColor),
        textSecondary: Color(nsColor: .secondaryLabelColor),
        textTertiary: Color(nsColor: .tertiaryLabelColor),
        accent: Color(nsColor: .controlAccentColor),
        accentSoft: Color(nsColor: .controlAccentColor).opacity(0.22),
        accentText: Color(nsColor: .alternateSelectedControlTextColor),
        controlBg: Color(nsColor: .controlColor),
        inputBg: Color(nsColor: .textBackgroundColor),
        inputBorder: Color(nsColor: .separatorColor),
        greenDot: Color(nsColor: .systemGreen),
        amberDot: Color(nsColor: .systemOrange),
        redDot: Color(nsColor: .systemRed),
        blueDot: Color(nsColor: .controlAccentColor),
        successBg: Color(nsColor: .systemGreen).opacity(0.18),
        successText: Color(nsColor: .systemGreen),
        warningBg: Color(nsColor: .systemOrange).opacity(0.18),
        warningText: Color(nsColor: .systemOrange),
        codeBg: Color(nsColor: .labelColor).opacity(0.07)
    )
}

private struct SandwalkThemeKey: EnvironmentKey {
    static let defaultValue = SandwalkTheme.current()
}

extension EnvironmentValues {
    var sandwalkTheme: SandwalkTheme {
        get { self[SandwalkThemeKey.self] }
        set { self[SandwalkThemeKey.self] = newValue }
    }
}

extension View {
    func sandwalkThemed() -> some View {
        environment(\.sandwalkTheme, SandwalkTheme.current())
    }
}

extension Font {
    static func sandwalk(_ size: CGFloat, weight: Font.Weight = .regular) -> Font {
        .system(size: size, weight: weight, design: .default)
    }

    static func sandwalkMono(_ size: CGFloat, weight: Font.Weight = .regular) -> Font {
        .system(size: size, weight: weight, design: .monospaced)
    }
}
