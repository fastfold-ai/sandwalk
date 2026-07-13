import AppKit
import QuartzCore

/// Menubar Aura mark — vector bars matching web `AuraIconPulse`.
enum SandwalkIcon {
    static let pointSize: CGFloat = 22

    /// Showcase colors (same as `AuraIconPulse` / colorful aura).
    static let barColors: [NSColor] = [
        NSColor(srgbRed: 0xDB / 255, green: 0x00 / 255, blue: 0x96 / 255, alpha: 1),
        NSColor(srgbRed: 0xE5 / 255, green: 0x64 / 255, blue: 0x64 / 255, alpha: 1),
        NSColor(srgbRed: 0xFF / 255, green: 0xB1 / 255, blue: 0x2F / 255, alpha: 1),
        NSColor(srgbRed: 0x89 / 255, green: 0xCC / 255, blue: 0x67 / 255, alpha: 1),
        NSColor(srgbRed: 0x13 / 255, green: 0xD8 / 255, blue: 0xA3 / 255, alpha: 1),
        NSColor(srgbRed: 0x15 / 255, green: 0xA3 / 255, blue: 0xD0 / 255, alpha: 1),
        NSColor(srgbRed: 0x16 / 255, green: 0x78 / 255, blue: 0xF1 / 255, alpha: 1),
    ]

    /// (centerX, topY, bodyHeight) — `public/aura_icon.svg` viewBox 847×847.
    private static let barGeometry: [(CGFloat, CGFloat, CGFloat)] = [
        (107, 458, 70),
        (213, 283, 176),
        (318, 177, 246),
        (422, 265, 246),
        (529, 353, 246),
        (634, 318, 178),
        (739, 248, 70),
    ]

    /// Steady template mark (system-tinted).
    static func menubarMark(pointSize: CGFloat = pointSize) -> NSImage {
        let image = makeBitmapImage(pointSize: pointSize) { rect in
            drawAura(
                in: rect,
                colors: Array(repeating: .black, count: barGeometry.count),
                opacities: Array(repeating: 1, count: barGeometry.count)
            )
        }
        image.isTemplate = true
        return image
    }

    /// Colorful app / Settings hero mark (not a template).
    static func appLogo(pointSize: CGFloat = 52) -> NSImage {
        makeBitmapImage(pointSize: pointSize) { rect in
            drawAura(
                in: rect,
                colors: barColors,
                opacities: Array(repeating: 1, count: barGeometry.count)
            )
        }
    }

    /// Smooth traveling color wave for layer updates (no full blank frames).
    static func rasterCGImage(
        phase: TimeInterval,
        scale: CGFloat,
        pointSize: CGFloat = pointSize
    ) -> CGImage? {
        let period: TimeInterval = 1.4
        let t = phase / period
        let opacities = (0..<barGeometry.count).map { index -> CGFloat in
            let x = Double(index) / Double(max(barGeometry.count - 1, 1))
            // Soft cosine — always ≥ ~0.35 so the icon never disappears mid-cycle.
            let wave = 0.5 + 0.5 * cos((t - x) * 2 * Double.pi)
            return CGFloat(0.35 + 0.65 * wave * wave)
        }
        return makeCGImage(pointSize: pointSize, scale: scale) { rect in
            drawAura(in: rect, colors: barColors, opacities: opacities)
        }
    }

    private static func makeBitmapImage(
        pointSize: CGFloat,
        draw: (NSRect) -> Void
    ) -> NSImage {
        let scale = NSScreen.main?.backingScaleFactor ?? 2
        guard let cg = makeCGImage(pointSize: pointSize, scale: scale, draw: draw) else {
            return NSImage(size: NSSize(width: pointSize, height: pointSize))
        }
        let image = NSImage(cgImage: cg, size: NSSize(width: pointSize, height: pointSize))
        return image
    }

    private static func makeCGImage(
        pointSize: CGFloat,
        scale: CGFloat,
        draw: (NSRect) -> Void
    ) -> CGImage? {
        let px = max(1, Int((pointSize * scale).rounded()))
        guard let rep = NSBitmapImageRep(
            bitmapDataPlanes: nil,
            pixelsWide: px,
            pixelsHigh: px,
            bitsPerSample: 8,
            samplesPerPixel: 4,
            hasAlpha: true,
            isPlanar: false,
            colorSpaceName: .deviceRGB,
            bytesPerRow: 0,
            bitsPerPixel: 0
        ) else { return nil }
        rep.size = NSSize(width: pointSize, height: pointSize)
        NSGraphicsContext.saveGraphicsState()
        NSGraphicsContext.current = NSGraphicsContext(bitmapImageRep: rep)
        NSColor.clear.setFill()
        let bounds = NSRect(x: 0, y: 0, width: pointSize, height: pointSize)
        bounds.fill()
        let inset = pointSize * 0.02
        draw(bounds.insetBy(dx: inset, dy: inset))
        NSGraphicsContext.restoreGraphicsState()
        return rep.cgImage
    }

    private static func drawAura(
        in rect: NSRect,
        colors: [NSColor],
        opacities: [CGFloat]
    ) {
        let view: CGFloat = 847
        let radius: CGFloat = 35
        let sx = rect.width / view
        let sy = rect.height / view

        for (i, geo) in barGeometry.enumerated() {
            let (cx, top, body) = geo
            let opacity = i < opacities.count ? opacities[i] : 1
            guard opacity > 0.01 else { continue }
            let color = (i < colors.count ? colors[i] : .black).withAlphaComponent(opacity)
            color.setFill()

            let width = radius * 2
            let height = body + radius * 2
            let x = rect.minX + (cx - radius) * sx
            let svgBottom = top + height
            let y = rect.maxY - svgBottom * sy
            let w = width * sx
            let h = height * sy
            let r = min(w, h) / 2
            NSBezierPath(
                roundedRect: NSRect(x: x, y: y, width: w, height: h),
                xRadius: r,
                yRadius: r
            ).fill()
        }
    }
}
