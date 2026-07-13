#!/usr/bin/env swift
import AppKit
import Foundation

/// Renders a bright Dock/App Store–style master icon:
/// full-bleed light background (system masks to squircle) + Aura bars.
/// Usage: generate_app_icon.swift <out.png> [size]

let outPath = CommandLine.arguments.count > 1
    ? CommandLine.arguments[1]
    : "AppIcon-1024.png"
let size = CommandLine.arguments.count > 2
    ? (Int(CommandLine.arguments[2]) ?? 1024)
    : 1024

let barColors: [NSColor] = Array(
    repeating: NSColor(srgbRed: 0.08, green: 0.08, blue: 0.09, alpha: 1),
    count: 7
)

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

// Bright full-bleed wash (ChatGPT / Ollama style — system applies squircle).
let gradient = NSGradient(colors: [
    NSColor(srgbRed: 1, green: 1, blue: 1, alpha: 1),
    NSColor(srgbRed: 0.96, green: 0.96, blue: 0.97, alpha: 1),
])!
gradient.draw(in: bounds, angle: -90)

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

// ~16% margin — mark sits smaller in the white tile (Dock-friendly padding).
let pad = CGFloat(size) * 0.16
let drawBox = bounds.insetBy(dx: pad, dy: pad)
let scale = min(drawBox.width / contentW, drawBox.height / contentH)
let drawnW = contentW * scale
let drawnH = contentH * scale
let originX = drawBox.midX - drawnW / 2
let originY = drawBox.midY - drawnH / 2

for (i, geo) in barGeometry.enumerated() {
    let (cx, top, body) = geo
    barColors[i].setFill()
    let width = radius * 2
    let height = body + radius * 2
    let x = originX + (cx - radius - contentMinX) * scale
    // SVG y grows down; AppKit y grows up — flip within content box.
    let y = originY + (contentMaxY - (top + height)) * scale
    let w = width * scale
    let h = height * scale
    let r = min(w, h) / 2
    NSBezierPath(
        roundedRect: NSRect(x: x, y: y, width: w, height: h),
        xRadius: r,
        yRadius: r
    ).fill()
}

NSGraphicsContext.restoreGraphicsState()

guard let png = rep.representation(using: .png, properties: [:]) else {
    fputs("error: png encode failed\n", stderr)
    exit(1)
}
try png.write(to: URL(fileURLWithPath: outPath))
print(outPath)
