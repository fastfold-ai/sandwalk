import AppKit
import Foundation

// Finder window content is 760×460 pt. The background is a 1520×920 px
// bitmap (2×) so it stays sharp on a Retina display. Plain white only.

let pointsW: CGFloat = 760
let pointsH: CGFloat = 460
let pixelsW = 1520
let pixelsH = 920

guard
  let rep = NSBitmapImageRep(
    bitmapDataPlanes: nil,
    pixelsWide: pixelsW,
    pixelsHigh: pixelsH,
    bitsPerSample: 8,
    samplesPerPixel: 4,
    hasAlpha: true,
    isPlanar: false,
    colorSpaceName: .deviceRGB,
    bytesPerRow: 0,
    bitsPerPixel: 0
  )
else {
  fputs("error: could not allocate DMG background\n", stderr)
  exit(1)
}
rep.size = NSSize(width: pointsW, height: pointsH)

NSGraphicsContext.saveGraphicsState()
NSGraphicsContext.current = NSGraphicsContext(bitmapImageRep: rep)
NSColor.white.setFill()
NSBezierPath(rect: NSRect(x: 0, y: 0, width: pointsW, height: pointsH)).fill()

// Between Sandwalk.app (center 210, 200) and Applications (center 550, 200).
// A short, light hint — clear of both 128 pt icons.
let y = pointsH - 200
let left: CGFloat = 348
let shaftW: CGFloat = 64
let shaftH: CGFloat = 2.5
let ink = NSColor(calibratedWhite: 0.78, alpha: 1)
ink.setFill()
let shaft = NSBezierPath(
  roundedRect: NSRect(x: left, y: y - shaftH / 2, width: shaftW, height: shaftH),
  xRadius: shaftH / 2,
  yRadius: shaftH / 2
)
shaft.fill()
let neck = left + shaftW - 2
let head = NSBezierPath()
head.move(to: NSPoint(x: neck, y: y - 7))
head.line(to: NSPoint(x: neck + 12, y: y))
head.line(to: NSPoint(x: neck, y: y + 7))
head.close()
head.fill()

NSGraphicsContext.restoreGraphicsState()

guard let png = rep.representation(using: .png, properties: [:]) else {
  fputs("error: could not render DMG background\n", stderr)
  exit(1)
}

let out = CommandLine.arguments.count > 1
  ? CommandLine.arguments[1]
  : "dmg-background.png"
try png.write(to: URL(fileURLWithPath: out))
