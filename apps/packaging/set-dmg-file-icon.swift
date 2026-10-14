import AppKit
import Foundation

// Stamp a .dmg file so Finder shows the Sandwalk app icon instead of a
// generic disk. Usage: set-dmg-file-icon.swift icon.icns path.dmg

guard CommandLine.arguments.count > 2 else {
  fputs("usage: set-dmg-file-icon.swift <icon.icns> <file.dmg>\n", stderr)
  exit(1)
}

let iconURL = URL(fileURLWithPath: CommandLine.arguments[1])
let fileURL = URL(fileURLWithPath: CommandLine.arguments[2])
guard let image = NSImage(contentsOf: iconURL) else {
  fputs("error: could not read icon \(iconURL.path)\n", stderr)
  exit(1)
}
if !NSWorkspace.shared.setIcon(image, forFile: fileURL.path, options: []) {
  fputs("error: could not set icon on \(fileURL.path)\n", stderr)
  exit(1)
}
