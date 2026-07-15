import AppKit
import QuartzCore

extension MenubarController {
    func updateStatusIcon(for overall: SandwalkSupervisor.OverallState) {
        switch overall {
        case .starting, .stopping:
            startPulse()
            applyPulseFrame()
        default:
            stopPulse()
            showTemplateIcon()
        }
    }

    func showTemplateIcon() {
        guard let button = statusItem.button else { return }
        iconLayer?.isHidden = true
        iconLayer?.contents = nil
        button.image = SandwalkIcon.menubarMark()
    }

    func startPulse() {
        guard !isPulsing else { return }
        isPulsing = true
        pulseStartedAt = Date()

        if let button = statusItem.button {
            button.image = nil
            iconLayer?.isHidden = false
        }

        let timer = Timer(timeInterval: 1.0 / 60.0, repeats: true) { [weak self] _ in
            Task { @MainActor in
                self?.applyPulseFrame()
            }
        }
        RunLoop.main.add(timer, forMode: .common)
        pulseTimer = timer
    }

    func stopPulse() {
        pulseTimer?.invalidate()
        pulseTimer = nil
        pulseStartedAt = nil
        isPulsing = false
    }

    func applyPulseFrame() {
        guard isPulsing, let started = pulseStartedAt, let layer = iconLayer else { return }
        let phase = Date().timeIntervalSince(started)
        let scale = statusItem.button?.window?.backingScaleFactor
            ?? NSScreen.main?.backingScaleFactor
            ?? 2
        guard let cg = SandwalkIcon.rasterCGImage(phase: phase, scale: scale) else { return }
        CATransaction.begin()
        CATransaction.setDisableActions(true)
        layer.contents = cg
        layer.contentsScale = scale
        CATransaction.commit()
    }

    func statusPresentation(
        for overall: SandwalkSupervisor.OverallState
    ) -> (String, NSColor) {
        switch overall {
        case .stopped:
            return ("Sandwalk is stopped", .secondaryLabelColor)
        case .starting:
            return ("Sandwalk is starting…", .systemOrange)
        case .running:
            return ("Sandwalk is running", .systemGreen)
        case .partial:
            return ("Sandwalk is partially running", .systemOrange)
        case .stopping:
            return ("Sandwalk is stopping…", .systemOrange)
        case .failed:
            return ("Sandwalk failed to start", .systemRed)
        }
    }

    static func statusDot(color: NSColor, diameter: CGFloat = 8) -> NSImage {
        let size = NSSize(width: diameter + 4, height: diameter + 4)
        let image = NSImage(size: size, flipped: false) { rect in
            let inset = (rect.width - diameter) / 2
            let circle = NSRect(
                x: inset,
                y: inset,
                width: diameter,
                height: diameter
            )
            color.setFill()
            NSBezierPath(ovalIn: circle).fill()
            return true
        }
        image.isTemplate = false
        return image
    }
}
