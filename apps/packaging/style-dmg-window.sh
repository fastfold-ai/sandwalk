#!/usr/bin/env bash
# Lay out the Finder window people see when they open the DMG:
# Sandwalk.app on the left, Applications on the right, a short caption.
#
# Usage: style-dmg-window.sh /path/to/read-write.dmg
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
RW_DMG="${1:-}"
if [[ -z "${RW_DMG}" || ! -f "${RW_DMG}" ]]; then
  echo "usage: $0 /path/to/read-write.dmg" >&2
  exit 1
fi

BG_PNG="${SCRIPT_DIR}/dist/dmg-background.png"
mkdir -p "${SCRIPT_DIR}/dist"
swift "${SCRIPT_DIR}/render-dmg-background.swift" "${BG_PNG}"

# Finder's "disk" name is the /Volumes entry, which matches the volume name
# only when we mount in /Volumes.
MOUNT="/Volumes/Sandwalk"
if mount | grep -q " on ${MOUNT} "; then
  hdiutil detach "${MOUNT}" >/dev/null 2>&1 || true
fi
cleanup() {
  hdiutil detach "${MOUNT}" >/dev/null 2>&1 || true
}
trap cleanup EXIT

echo "==> Styling DMG install window..."
# Finder must see the volume. -nobrowse hides it and AppleScript cannot find the disk.
hdiutil attach "${RW_DMG}" -mountpoint "${MOUNT}" >/dev/null

mkdir -p "${MOUNT}/.background"
cp -f "${BG_PNG}" "${MOUNT}/.background/background.png"
chflags hidden "${MOUNT}/.background" || true

# Finder addresses the volume by its name, not the mount path.
osascript <<'APPLESCRIPT'
tell application "Finder"
  tell disk "Sandwalk"
    open
    set current view of container window to icon view
    set toolbar visible of container window to false
    set statusbar visible of container window to false
    set the bounds of container window to {140, 120, 800, 500}
    set viewOptions to the icon view options of container window
    set arrangement of viewOptions to not arranged
    set icon size of viewOptions to 112
    set text size of viewOptions to 13
    set background picture of viewOptions to file ".background:background.png"
    delay 1
    set position of item "Sandwalk.app" of container window to {180, 175}
    set position of item "Applications" of container window to {480, 175}
    update without registering applications
    delay 1
    close
  end tell
end tell
APPLESCRIPT

sync
hdiutil detach "${MOUNT}" >/dev/null
trap - EXIT
echo "    install window laid out"
