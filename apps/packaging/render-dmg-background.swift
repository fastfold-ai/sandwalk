import AppKit
import Foundation

// Retina background for the DMG install window (660×380 pt → 1320×760 px).
// Icons sit on the left and right; this only paints the canvas and the arrow.

let width = 1320
let height = 760
let image = NSImage(size: NSSize(width: width, height: height))
image.lockFocus()

NSColor(calibratedRed: 0.965, green: 0.965, blue: 0.97, alpha: 1).setFill()
NSBezierPath(rect: NSRect(x: 0, y: 0, width: width, height: height)).fill()

let arrow = NSBezierPath()
arrow.move(to: NSPoint(x: 520, y: 390))
arrow.line(to: NSPoint(x: 760, y: 390))
arrow.lineWidth = 6
arrow.lineCapStyle = .round
NSColor(calibratedWhite: 0.72, alpha: 1).setStroke()
arrow.stroke()

let head = NSBezierPath()
head.move(to: NSPoint(x: 760, y: 390))
head.line(to: NSPoint(x: 728, y: 414))
head.line(to: NSPoint(x: 728, y: 366))
head.close()
NSColor(calibratedWhite: 0.72, alpha: 1).setFill()
head.fill()

let caption = "Drag Sandwalk to Applications" as NSString
let font = NSFont.systemFont(ofSize: 28, weight: .medium)
let attrs: [NSAttributedString.Key: Any] = [
  .font: font,
  .foregroundColor: NSColor(calibratedWhite: 0.45, alpha: 1)
]
let captionSize = caption.size(withAttributes: attrs)
caption.draw(
  at: NSPoint(x: (CGFloat(width) - captionSize.width) / 2, y: 92),
  withAttributes: attrs
)

image.unlockFocus()

guard
  let tiff = image.tiffRepresentation,
  let rep = NSBitmapImageRep(data: tiff),
  let png = rep.representation(using: .png, properties: [:])
else {
  fputs("error: could not render DMG background\n", stderr)
  exit(1)
}

let out = CommandLine.arguments.count > 1
  ? CommandLine.arguments[1]
  : "dmg-background.png"
try png.write(to: URL(fileURLWithPath: out))
