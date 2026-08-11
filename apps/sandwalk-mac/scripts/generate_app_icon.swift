#!/usr/bin/env swift
import AppKit
import Foundation

/// Renders a bright Dock/App Store–style master icon:
/// full-bleed light background + Aura bars.
/// Usage: generate_app_icon.swift <out.png> [size] [--squircle]
///
/// --squircle bakes in macOS's rounded-square icon shape (with transparent
/// corners). Needed for images set at runtime via
/// NSApplication.applicationIconImage (the Dock icon picker in Appearance) —
/// that API shows the image as-is with no automatic masking, unlike the
/// bundle .icns pipeline. Omit it for the master bundle icon (Xcode/iconutil
/// masks that one automatically).

let outPath = CommandLine.arguments.count > 1
    ? CommandLine.arguments[1]
    : "AppIcon-1024.png"
let size = CommandLine.arguments.count > 2
    ? (Int(CommandLine.arguments[2]) ?? 1024)
    : 1024
let squircle = CommandLine.arguments.contains("--squircle")

/// (centerX, topY, bodyHeight) in 847×847 Aura viewBox.
let barGeometry: [(CGFloat, CGFloat, CGFloat)] = [
    (107, 458, 70),
    (213, 283, 176),
    (318, 177, 246),
    (422, 265, 246),
    (529, 353, 246),
    (634, 318, 178),
    (739, 248, 70),
]

guard let rep = NSBitmapImageRep(
    bitmapDataPlanes: nil,
    pixelsWide: size,
    pixelsHigh: size,
    bitsPerSample: 8,
    samplesPerPixel: 4,
    hasAlpha: true,
    isPlanar: false,
    colorSpaceName: .deviceRGB,
    bytesPerRow: 0,
    bitsPerPixel: 0
) else {
    fputs("error: bitmap alloc failed\n", stderr)
    exit(1)
}
rep.size = NSSize(width: size, height: size)

NSGraphicsContext.saveGraphicsState()
guard let ctx = NSGraphicsContext(bitmapImageRep: rep) else {
    fputs("error: graphics context failed\n", stderr)
    exit(1)
}
NSGraphicsContext.current = ctx

let bounds = NSRect(x: 0, y: 0, width: size, height: size)

// In --squircle mode, follow the macOS icon grid: the squircle occupies
// ~82.4% of the canvas with a transparent margin (like bundle .icns art).
// Full-bleed squircles render noticeably larger than other Dock icons.
let margin = squircle ? CGFloat(size) * 0.098 : 0
let tile = bounds.insetBy(dx: margin, dy: margin)
if squircle {
    // macOS Big Sur+ rounded-square icon shape — ~22.3% corner radius.
    let squircleRadius = tile.width * 0.2226
    NSBezierPath(
        roundedRect: tile,
        xRadius: squircleRadius,
        yRadius: squircleRadius
    ).addClip()
}

// Bright wash with a strong radial halo behind the mark and an ambient
// vignette toward the edges — higher contrast so the glow actually reads.
let gradient = NSGradient(colors: [
    NSColor(srgbRed: 0.985, green: 0.985, blue: 0.99, alpha: 1),
    NSColor(srgbRed: 0.88, green: 0.88, blue: 0.90, alpha: 1),
])!
gradient.draw(in: tile, angle: -90)
let haloCenter = NSPoint(x: tile.midX, y: tile.midY + tile.width * 0.06)
let halo = NSGradient(colorsAndLocations:
    (NSColor(srgbRed: 1, green: 1, blue: 1, alpha: 1.0), 0.0),
    (NSColor(srgbRed: 1, green: 1, blue: 1, alpha: 0.75), 0.45),
    (NSColor(srgbRed: 1, green: 1, blue: 1, alpha: 0.0), 1.0)
)!
halo.draw(
    fromCenter: haloCenter,
    radius: 0,
    toCenter: haloCenter,
    radius: tile.width * 0.42,
    options: []
)
// Vignette — soft cool shading creeping in from the corners.
let vignette = NSGradient(colorsAndLocations:
    (NSColor(srgbRed: 0.55, green: 0.56, blue: 0.60, alpha: 0.0), 0.0),
    (NSColor(srgbRed: 0.55, green: 0.56, blue: 0.60, alpha: 0.0), 0.62),
    (NSColor(srgbRed: 0.55, green: 0.56, blue: 0.60, alpha: 0.22), 1.0)
)!
vignette.draw(
    fromCenter: haloCenter,
    radius: 0,
    toCenter: haloCenter,
    radius: tile.width * 0.78,
    options: NSGradient.DrawingOptions.drawsAfterEndingLocation
)

let radius: CGFloat = 35
// Tight content box of the Aura bars (ignore empty SVG margins).
var contentMinX = CGFloat.greatestFiniteMagnitude
var contentMaxX = -CGFloat.greatestFiniteMagnitude
var contentMinY = CGFloat.greatestFiniteMagnitude
var contentMaxY = -CGFloat.greatestFiniteMagnitude
for (cx, top, body) in barGeometry {
    let height = body + radius * 2
    contentMinX = min(contentMinX, cx - radius)
    contentMaxX = max(contentMaxX, cx + radius)
    contentMinY = min(contentMinY, top)
    contentMaxY = max(contentMaxY, top + height)
}
let contentW = contentMaxX - contentMinX
let contentH = contentMaxY - contentMinY

// ~21% glyph padding within the tile.
let pad = tile.width * 0.21
let drawBox = tile.insetBy(dx: pad, dy: pad)
let scale = min(drawBox.width / contentW, drawBox.height / contentH)
let drawnW = contentW * scale
let drawnH = contentH * scale
let originX = drawBox.midX - drawnW / 2
let originY = drawBox.midY - drawnH / 2

// Top-lit shading — softer charcoal at the top reads as a lit face.
let barGrad = NSGradient(colorsAndLocations:
    (NSColor(srgbRed: 0.32, green: 0.32, blue: 0.36, alpha: 1), 0.0),
    (NSColor(srgbRed: 0.16, green: 0.16, blue: 0.18, alpha: 1), 0.35),
    (NSColor(srgbRed: 0.07, green: 0.07, blue: 0.08, alpha: 1), 0.8),
    (NSColor(srgbRed: 0.03, green: 0.03, blue: 0.04, alpha: 1), 1.0)
)!

for geo in barGeometry {
    let (cx, top, body) = geo
    let width = radius * 2
    let height = body + radius * 2
    let x = originX + (cx - radius - contentMinX) * scale
    // SVG y grows down; AppKit y grows up — flip within content box.
    let y = originY + (contentMaxY - (top + height)) * scale
    let w = width * scale
    let h = height * scale
    let r = min(w, h) / 2
    let path = NSBezierPath(
        roundedRect: NSRect(x: x, y: y, width: w, height: h),
        xRadius: r,
        yRadius: r
    )
    // Deep drop shadow via solid fill (NSGradient ignores NSShadow).
    NSGraphicsContext.saveGraphicsState()
    let shadow = NSShadow()
    shadow.shadowColor = NSColor(srgbRed: 0.08, green: 0.09, blue: 0.12, alpha: 0.45)
    shadow.shadowBlurRadius = CGFloat(size) * 0.042
    shadow.shadowOffset = NSSize(width: 0, height: -CGFloat(size) * 0.014)
    shadow.set()
    NSColor(srgbRed: 0.08, green: 0.08, blue: 0.09, alpha: 1).setFill()
    path.fill()
    NSGraphicsContext.restoreGraphicsState()
    // Tight contact shadow hugging the bar for extra lift.
    NSGraphicsContext.saveGraphicsState()
    let contact = NSShadow()
    contact.shadowColor = NSColor(srgbRed: 0, green: 0, blue: 0, alpha: 0.30)
    contact.shadowBlurRadius = CGFloat(size) * 0.012
    contact.shadowOffset = NSSize(width: 0, height: -CGFloat(size) * 0.004)
    contact.set()
    NSColor(srgbRed: 0.08, green: 0.08, blue: 0.09, alpha: 1).setFill()
    path.fill()
    NSGraphicsContext.restoreGraphicsState()
    barGrad.draw(in: path, angle: -90)
    // Specular glare on the top cap.
    NSGraphicsContext.saveGraphicsState()
    path.addClip()
    let glare = NSGradient(colors: [
        NSColor(srgbRed: 1, green: 1, blue: 1, alpha: 0.50),
        NSColor(srgbRed: 1, green: 1, blue: 1, alpha: 0.0),
    ])!
    let capCenter = NSPoint(x: x + w / 2, y: y + h - r)
    glare.draw(fromCenter: capCenter, radius: 0, toCenter: capCenter, radius: w * 1.1, options: [])
    NSGraphicsContext.restoreGraphicsState()
}

// Glossy bezel — gradient ring hugging the squircle edge, lit from the top.
// Ring drawn via even-odd clip between two squircle paths so the stroke
// itself carries the gradient.
let rimRadius = tile.width * 0.2226
let ringWidth = tile.width * 0.014
let ring = NSBezierPath(
    roundedRect: tile,
    xRadius: rimRadius,
    yRadius: rimRadius
)
let innerRect = tile.insetBy(dx: ringWidth, dy: ringWidth)
ring.append(NSBezierPath(
    roundedRect: innerRect,
    xRadius: max(0, rimRadius - ringWidth),
    yRadius: max(0, rimRadius - ringWidth)
))
ring.windingRule = .evenOdd
NSGraphicsContext.saveGraphicsState()
ring.addClip()
let rimGrad = NSGradient(colorsAndLocations:
    (NSColor(srgbRed: 0.88, green: 0.89, blue: 0.91, alpha: 1.0), 0.0),
    (NSColor(srgbRed: 0.66, green: 0.67, blue: 0.71, alpha: 0.95), 0.35),
    (NSColor(srgbRed: 0.52, green: 0.53, blue: 0.57, alpha: 0.90), 0.75),
    (NSColor(srgbRed: 0.62, green: 0.63, blue: 0.67, alpha: 0.95), 1.0)
)!
rimGrad.draw(in: tile, angle: -90)
NSGraphicsContext.restoreGraphicsState()

NSGraphicsContext.restoreGraphicsState()

guard let png = rep.representation(using: .png, properties: [:]) else {
    fputs("error: png encode failed\n", stderr)
    exit(1)
}
try png.write(to: URL(fileURLWithPath: outPath))
print(outPath)
