import AppKit
import SwiftUI

/// oMLX-style About — hero, project links, license, credits.
struct AboutSettingsView: View {
    @Environment(\.sandwalkTheme) private var theme

    private var version: String {
        Bundle.main.infoDictionary?["CFBundleShortVersionString"] as? String ?? "0.1.0"
    }

    private var build: String {
        Bundle.main.infoDictionary?["CFBundleVersion"] as? String ?? "1"
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            heroCard

            SettingsSectionHeader("PROJECT")
            SettingsListGroup {
                AboutLinkRow(
                    label: "GitHub Repository",
                    sublabel: "Source, issues, and roadmap",
                    icon: "chevron.left.forwardslash.chevron.right",
                    url: URL(string: "https://github.com/fastfold-ai/sandwalk")!
                )
                AboutLinkRow(
                    label: "Releases",
                    sublabel: "Download the latest CLI and macOS app",
                    icon: "shippingbox",
                    url: URL(string: "https://github.com/fastfold-ai/sandwalk/releases")!
                )
                AboutLinkRow(
                    label: "Documentation",
                    sublabel: "Setup, serve, and dashboard",
                    icon: "book.closed",
                    url: URL(string: "https://github.com/fastfold-ai/sandwalk#readme")!
                )
                AboutLinkRow(
                    label: "Report an Issue",
                    sublabel: "Bugs and feature requests on GitHub",
                    icon: "exclamationmark.bubble",
                    url: URL(string: "https://github.com/fastfold-ai/sandwalk/issues/new")!,
                    isLast: true
                )
            }

            SettingsSectionHeader("LICENSE")
            SettingsListGroup {
                FreeAboutRow(isLast: true) {
                    VStack(alignment: .leading, spacing: 6) {
                        HStack(spacing: 6) {
                            Image(systemName: "scale.3d")
                                .font(.system(size: 13))
                                .foregroundStyle(theme.textSecondary)
                            Text("MIT License")
                                .font(.sandwalk(13, weight: .medium))
                                .foregroundStyle(theme.text)
                        }
                        Text("Copyright © 2026 CellType Inc. Licensed under the MIT License. See the LICENSE file in the repository for the full text.")
                            .font(.sandwalk(11.5))
                            .foregroundStyle(theme.textSecondary)
                            .fixedSize(horizontal: false, vertical: true)
                    }
                }
            }

            SettingsSectionHeader("BUILT ON")
            SettingsListGroup {
                AboutLinkRow(
                    label: "FastAPI",
                    sublabel: "Agent API — /v1 sessions, auth, and health",
                    icon: "server.rack",
                    url: URL(string: "https://fastapi.tiangolo.com")!
                )
                AboutLinkRow(
                    label: "Vite + React",
                    sublabel: "Local web dashboard supervised by the menubar",
                    icon: "globe",
                    url: URL(string: "https://vite.dev")!
                )
                AboutLinkRow(
                    label: "assistant-ui",
                    sublabel: "Chat primitives for the agent dashboard",
                    icon: "bubble.left.and.bubble.right",
                    url: URL(string: "https://www.assistant-ui.com")!
                )
                AboutLinkRow(
                    label: "LangGraph",
                    sublabel: "Agentic research loop and tool orchestration",
                    icon: "point.3.connected.trianglepath.dotted",
                    url: URL(string: "https://langchain-ai.github.io/langgraph/")!
                )
                AboutLinkRow(
                    label: "SwiftUI",
                    sublabel: "macOS menubar supervisor and Settings",
                    icon: "apple.logo",
                    url: URL(string: "https://developer.apple.com/xcode/swiftui/")!,
                    isLast: true
                )
            }
        }
        .padding(.top, 4)
    }

    private var heroCard: some View {
        HStack(spacing: 16) {
            aboutLogo
                .frame(width: 60, height: 60)
                .clipShape(RoundedRectangle(cornerRadius: 14, style: .continuous))
                .overlay(
                    RoundedRectangle(cornerRadius: 14, style: .continuous)
                        .strokeBorder(theme.inputBorder, lineWidth: 0.5)
                )

            VStack(alignment: .leading, spacing: 4) {
                Text("Sandwalk")
                    .font(.sandwalk(22, weight: .semibold))
                    .foregroundStyle(theme.text)
                Text("A thinking path for open science.")
                    .font(.sandwalk(12))
                    .foregroundStyle(theme.textSecondary)
                Text("Version \(version) · build \(build)")
                    .font(.sandwalkMono(11))
                    .foregroundStyle(theme.textTertiary)
            }
            Spacer(minLength: 8)
        }
        .padding(18)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(theme.groupBg)
        .clipShape(RoundedRectangle(cornerRadius: 12, style: .continuous))
        .overlay(
            RoundedRectangle(cornerRadius: 12, style: .continuous)
                .strokeBorder(theme.inputBorder, lineWidth: 0.5)
        )
        .padding(.horizontal, 14)
        .padding(.bottom, 14)
    }

    @ViewBuilder
    private var aboutLogo: some View {
        if let url = Bundle.module.url(forResource: "AppIcon-1024", withExtension: "png"),
           let image = NSImage(contentsOf: url)
        {
            Image(nsImage: image)
                .resizable()
                .interpolation(.high)
                .aspectRatio(contentMode: .fill)
        } else {
            Image(nsImage: SandwalkIcon.appLogo(pointSize: 60))
                .resizable()
                .interpolation(.high)
                .aspectRatio(contentMode: .fit)
                .padding(8)
                .background(Color.white)
        }
    }
}

private struct AboutLinkRow: View {
    let label: String
    let sublabel: String
    let icon: String
    let url: URL
    var isLast: Bool = false

    @Environment(\.sandwalkTheme) private var theme

    var body: some View {
        FreeAboutRow(isLast: isLast) {
            HStack(spacing: 10) {
                Image(systemName: icon)
                    .font(.system(size: 14))
                    .foregroundStyle(theme.textSecondary)
                    .frame(width: 18, alignment: .center)

                VStack(alignment: .leading, spacing: 2) {
                    Text(label)
                        .font(.sandwalk(13, weight: .medium))
                        .foregroundStyle(theme.text)
                    Text(sublabel)
                        .font(.sandwalk(11))
                        .foregroundStyle(theme.textSecondary)
                        .lineLimit(2)
                }

                Spacer(minLength: 8)

                Button {
                    NSWorkspace.shared.open(url)
                } label: {
                    Label("Open", systemImage: "arrow.up.right.square")
                        .labelStyle(.titleAndIcon)
                }
                .buttonStyle(.sandwalk(.normal))
            }
        }
    }
}

private struct FreeAboutRow<Content: View>: View {
    var isLast: Bool = true
    @ViewBuilder var content: () -> Content
    @Environment(\.sandwalkTheme) private var theme

    var body: some View {
        content()
            .padding(.horizontal, 14)
            .padding(.vertical, 10)
            .frame(maxWidth: .infinity, alignment: .leading)
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
