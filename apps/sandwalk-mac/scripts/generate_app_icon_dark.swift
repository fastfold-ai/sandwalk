#!/usr/bin/env swift
import AppKit
import Foundation

/// Renders a dark Dock-icon variant: dark charcoal full-bleed background
/// (system masks to squircle) + light Aura bars. Same geometry as
/// generate_app_icon.swift, inverted palette — a "dark mode" dock icon
/// alternative, selectable from Appearance → Dock icon.
/// Usage: generate_app_icon_dark.swift <out.png> [size] [--squircle]
///
/// --squircle bakes in macOS's rounded-square icon shape (with transparent
/// corners) — needed for the Dock icon override path, see
/// generate_app_icon.swift for details.

let outPath = CommandLine.arguments.count > 1
    ? CommandLine.arguments[1]
    : "AppIcon-1024-dark.png"
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

// Dark wash with a soft radial highlight behind the mark (Cursor-style depth).
let gradient = NSGradient(colors: [
    NSColor(srgbRed: 0.11, green: 0.11, blue: 0.125, alpha: 1),
    NSColor(srgbRed: 0.055, green: 0.055, blue: 0.065, alpha: 1),
])!
gradient.draw(in: tile, angle: -90)
let halo = NSGradient(colors: [
    NSColor(srgbRed: 0.30, green: 0.31, blue: 0.36, alpha: 0.35),
    NSColor(srgbRed: 0.30, green: 0.31, blue: 0.36, alpha: 0.0),
])!
halo.draw(
    fromCenter: NSPoint(x: tile.midX, y: tile.midY + tile.width * 0.06),
    radius: 0,
    toCenter: NSPoint(x: tile.midX, y: tile.midY + tile.width * 0.06),
    radius: tile.width * 0.42,
    options: []
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

// ~26% glyph padding within the tile — Cursor/Ghostty-style breathing room.
let pad = tile.width * 0.26
let drawBox = tile.insetBy(dx: pad, dy: pad)
let scale = min(drawBox.width / contentW, drawBox.height / contentH)
let drawnW = contentW * scale
let drawnH = contentH * scale
let originX = drawBox.midX - drawnW / 2
let originY = drawBox.midY - drawnH / 2

// Top-lit metallic shading — bright caps fading to cool gray (3D read).
let barGrad = NSGradient(colorsAndLocations:
    (NSColor(srgbRed: 1, green: 1, blue: 1, alpha: 1), 0.0),
    (NSColor(srgbRed: 0.96, green: 0.96, blue: 0.98, alpha: 1), 0.30),
    (NSColor(srgbRed: 0.84, green: 0.85, blue: 0.90, alpha: 1), 0.72),
    (NSColor(srgbRed: 0.66, green: 0.67, blue: 0.74, alpha: 1), 1.0)
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
    // Tight glow via solid fill (NSGradient ignores NSShadow).
    NSGraphicsContext.saveGraphicsState()
    let shadow = NSShadow()
    shadow.shadowColor = NSColor(srgbRed: 1, green: 1, blue: 1, alpha: 0.30)
    shadow.shadowBlurRadius = CGFloat(size) * 0.025
    shadow.shadowOffset = NSSize(width: 0, height: 0)
    shadow.set()
    NSColor(srgbRed: 0.94, green: 0.94, blue: 0.96, alpha: 1).setFill()
    path.fill()
    NSGraphicsContext.restoreGraphicsState()
    barGrad.draw(in: path, angle: -90)
    // Specular glare on the top cap.
    NSGraphicsContext.saveGraphicsState()
    path.addClip()
    let glare = NSGradient(colors: [
        NSColor(srgbRed: 1, green: 1, blue: 1, alpha: 0.85),
        NSColor(srgbRed: 1, green: 1, blue: 1, alpha: 0.0),
    ])!
    let capCenter = NSPoint(x: x + w / 2, y: y + h - r)
    glare.draw(fromCenter: capCenter, radius: 0, toCenter: capCenter, radius: w * 1.1, options: [])
    NSGraphicsContext.restoreGraphicsState()
}

// Glossy bezel — gradient ring hugging the squircle edge, lit from the top
// (like Cursor's silver rim). Ring drawn via even-odd clip between two
// squircle paths so the stroke itself carries the gradient.
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
    (NSColor(srgbRed: 0.78, green: 0.79, blue: 0.84, alpha: 0.90), 0.0),
    (NSColor(srgbRed: 0.48, green: 0.49, blue: 0.54, alpha: 0.55), 0.35),
    (NSColor(srgbRed: 0.30, green: 0.30, blue: 0.34, alpha: 0.40), 0.75),
    (NSColor(srgbRed: 0.42, green: 0.42, blue: 0.47, alpha: 0.50), 1.0)
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
