import AppKit
import SwiftUI

/// oMLX-style log viewer — tails Application Support server.log / web.log.
struct LogsSettingsView: View {
    @State private var selectedFile = "server.log"
    @State private var lineLimit = 100
    @State private var logText = ""
    @State private var search = ""
    @State private var totalLines = 0
    @State private var isLoading = false
    @State private var lastError: String?
    @State private var refreshTick = 0

    @Environment(\.sandwalkTheme) private var theme

    private let files: [(id: String, label: String)] = [
        ("server.log", "server.log (API)"),
        ("web.log", "web.log (dashboard)"),
    ]

    private var searchNeedle: String {
        search.trimmingCharacters(in: .whitespacesAndNewlines)
    }

    private var displayedText: String {
        let needle = searchNeedle
        guard !needle.isEmpty else { return logText }
        let lines = logText.split(separator: "\n", omittingEmptySubsequences: false)
        return lines
            .filter { $0.localizedCaseInsensitiveContains(needle) }
            .joined(separator: "\n")
    }

    private var matchCount: Int {
        guard !searchNeedle.isEmpty else { return 0 }
        return displayedText
            .split(separator: "\n", omittingEmptySubsequences: false)
            .filter { !$0.isEmpty }
            .count
    }

    private var headerSubtitle: String? {
        if !searchNeedle.isEmpty {
            return "\(matchCount) match\(matchCount == 1 ? "" : "es") · \(totalLines) lines"
        }
        return totalLines > 0 ? "\(totalLines) lines" : nil
    }

    private var lineOptions: [(Int, String)] {
        [
            (100, "Last 100"),
            (500, "Last 500"),
            (1000, "Last 1,000"),
            (5000, "Last 5,000"),
        ]
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            SettingsSectionHeader(
                "SERVER LOGS",
                subtitle: headerSubtitle
            )

            SettingsListGroup {
                SettingsRow(label: "Log file", isLast: true) {
                    Picker("", selection: $selectedFile) {
                        ForEach(files, id: \.id) { file in
                            Text(file.label).tag(file.id)
                        }
                    }
                    .labelsHidden()
                    .frame(width: 200)
                }
            }

            AgentSearchField(text: $search)

            LogPane(
                text: displayedText,
                isEmpty: displayedText.isEmpty,
                isLoading: isLoading,
                emptyLabel: searchNeedle.isEmpty
                    ? "No log entries."
                    : "No lines match “\(searchNeedle)”."
            )
                .padding(.horizontal, 14)
                .padding(.top, 4)
                .padding(.bottom, 8)
                .frame(maxWidth: .infinity, maxHeight: .infinity)

            HStack(spacing: 8) {
                Picker("", selection: $lineLimit) {
                    ForEach(lineOptions, id: \.0) { option in
                        Text(option.1).tag(option.0)
                    }
                }
                .labelsHidden()
                .frame(width: 120)

                Button {
                    refreshTick &+= 1
                } label: {
                    Image(systemName: "arrow.clockwise")
                }
                .buttonStyle(.sandwalk(.normal))
                .disabled(isLoading)

                Button("Copy") {
                    NSPasteboard.general.clearContents()
                    NSPasteboard.general.setString(displayedText, forType: .string)
                }
                .buttonStyle(.sandwalk(.normal))
                .disabled(displayedText.isEmpty)

                Button("Show in Finder") {
                    NSWorkspace.shared.activateFileViewerSelecting([logFileURL])
                }
                .buttonStyle(.sandwalk(.normal))

                Spacer()

                if let lastError {
                    Text(lastError)
                        .font(.sandwalk(11))
                        .foregroundStyle(theme.redDot)
                        .lineLimit(1)
                } else {
                    Text(logFileURL.path)
                        .font(.sandwalk(10.5))
                        .foregroundStyle(theme.textTertiary)
                        .lineLimit(1)
                        .truncationMode(.middle)
                }
            }
            .padding(.horizontal, 18)
            .padding(.bottom, 12)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .top)
        .task(id: "\(selectedFile)-\(lineLimit)-\(refreshTick)") {
            await pollLoop()
        }
    }

    private var logFileURL: URL {
        let config = SandwalkRuntime.config
        return selectedFile == "web.log" ? config.webLogURL : config.serverLogURL
    }

    @MainActor
    private func pollLoop() async {
        while !Task.isCancelled {
            await reload()
            try? await Task.sleep(for: .seconds(5))
        }
    }

    @MainActor
    private func reload() async {
        isLoading = true
        defer { isLoading = false }
        do {
            let result = try LogTailer.tail(url: logFileURL, maxLines: lineLimit)
            logText = result.text
            totalLines = result.lineCount
            lastError = nil
        } catch {
            lastError = error.localizedDescription
        }
    }
}

enum LogTailer {
    struct Result {
        var text: String
        var lineCount: Int
    }

    enum TailError: Error, LocalizedError {
        case unreadable(String)

        var errorDescription: String? {
            switch self {
            case .unreadable(let path): return "Could not read \(path)"
            }
        }
    }

    static func tail(url: URL, maxLines: Int) throws -> Result {
        let fm = FileManager.default
        if !fm.fileExists(atPath: url.path) {
            return Result(text: "", lineCount: 0)
        }
        guard let handle = try? FileHandle(forReadingFrom: url) else {
            throw TailError.unreadable(url.lastPathComponent)
        }
        defer { try? handle.close() }

        // Read last ~2 MB for large logs, then take last N lines.
        let fileSize = (try? url.resourceValues(forKeys: [.fileSizeKey]).fileSize) ?? 0
        let window = min(fileSize, 2 * 1024 * 1024)
        if fileSize > window {
            try handle.seek(toOffset: UInt64(fileSize - window))
        }
        let data = handle.readDataToEndOfFile()
        guard let raw = String(data: data, encoding: .utf8)
            ?? String(data: data, encoding: .isoLatin1)
        else {
            return Result(text: "", lineCount: 0)
        }

        var lines = raw.split(separator: "\n", omittingEmptySubsequences: false).map(String.init)
        if fileSize > window, let first = lines.first, !first.isEmpty {
            // Drop partial first line from mid-file seek.
            lines.removeFirst()
        }
        if lines.last == "" {
            lines.removeLast()
        }
        let clipped = Array(lines.suffix(max(1, maxLines)))
        return Result(text: clipped.joined(separator: "\n"), lineCount: clipped.count)
    }
}

private struct LogPane: View {
    let text: String
    let isEmpty: Bool
    let isLoading: Bool
    var emptyLabel: String = "No log entries."

    @Environment(\.sandwalkTheme) private var theme

    var body: some View {
        ZStack {
            LogTextView(
                text: text,
                fgColor: NSColor(theme.text),
                bgColor: NSColor(theme.codeBg)
            )
            if isEmpty && !isLoading {
                Text(emptyLabel)
                    .font(.sandwalk(12))
                    .foregroundStyle(theme.textTertiary)
            }
        }
        .frame(minHeight: 360, idealHeight: 480, maxHeight: .infinity)
        .background(theme.codeBg)
        .clipShape(RoundedRectangle(cornerRadius: theme.cornerRadius, style: .continuous))
        .overlay(
            RoundedRectangle(cornerRadius: theme.cornerRadius, style: .continuous)
                .strokeBorder(theme.inputBorder, lineWidth: 0.5)
        )
    }
}

private struct LogTextView: NSViewRepresentable {
    let text: String
    let fgColor: NSColor
    let bgColor: NSColor

    func makeNSView(context: Context) -> NSScrollView {
        let scroll = NSTextView.scrollableTextView()
        scroll.hasVerticalScroller = true
        scroll.hasHorizontalScroller = false
        scroll.autohidesScrollers = true
        scroll.borderType = .noBorder
        scroll.drawsBackground = false

        guard let textView = scroll.documentView as? NSTextView else { return scroll }
        textView.isEditable = false
        textView.isSelectable = true
        textView.isRichText = false
        textView.allowsUndo = false
        textView.usesFindBar = true
        textView.drawsBackground = true
        textView.backgroundColor = bgColor
        textView.textContainerInset = NSSize(width: 12, height: 10)
        textView.font = NSFont.monospacedSystemFont(ofSize: 11.5, weight: .regular)
        textView.textColor = fgColor
        textView.isAutomaticQuoteSubstitutionEnabled = false
        textView.isAutomaticDashSubstitutionEnabled = false
        if let container = textView.textContainer {
            container.widthTracksTextView = true
            container.lineFragmentPadding = 0
        }
        textView.string = text
        return scroll
    }

    func updateNSView(_ scroll: NSScrollView, context: Context) {
        guard let textView = scroll.documentView as? NSTextView else { return }
        textView.backgroundColor = bgColor
        textView.textColor = fgColor
        if textView.string == text { return }

        let wasPinned: Bool = {
            let clip = scroll.contentView
            return clip.documentRect.maxY - clip.documentVisibleRect.maxY < 40
        }()

        textView.string = text
        if wasPinned {
            DispatchQueue.main.async {
                textView.scrollToEndOfDocument(nil)
            }
        }
    }
}
