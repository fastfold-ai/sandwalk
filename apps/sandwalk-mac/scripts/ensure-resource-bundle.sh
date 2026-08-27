#!/usr/bin/env bash
# Turn a flat SwiftPM *.bundle directory into a codesign-valid resource bundle.
set -euo pipefail

BUNDLE="${1:-}"
IDENTIFIER="${2:-ai.fastfold.sandwalk-server.resource}"
if [[ -z "${BUNDLE}" || ! -d "${BUNDLE}" ]]; then
  echo "usage: $0 /path/to/Name.bundle [bundle-id]" >&2
  exit 1
fi

if [[ -f "${BUNDLE}/Contents/Info.plist" ]]; then
  exit 0
fi

TMP="$(mktemp -d)"
# Move existing payload aside (do not copy Contents if we just created nothing).
shopt -s dotglob nullglob
for item in "${BUNDLE}"/*; do
  mv "${item}" "${TMP}/"
done
shopt -u dotglob nullglob

mkdir -p "${BUNDLE}/Contents/Resources"
if [[ -n "$(ls -A "${TMP}" 2>/dev/null)" ]]; then
  mv "${TMP}"/* "${BUNDLE}/Contents/Resources/"
fi
rmdir "${TMP}" 2>/dev/null || rm -rf "${TMP}"

NAME="$(basename "${BUNDLE}" .bundle)"
cat > "${BUNDLE}/Contents/Info.plist" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleDevelopmentRegion</key>
  <string>en</string>
  <key>CFBundleIdentifier</key>
  <string>${IDENTIFIER}</string>
  <key>CFBundleInfoDictionaryVersion</key>
  <string>6.0</string>
  <key>CFBundleName</key>
  <string>${NAME}</string>
  <key>CFBundlePackageType</key>
  <string>BNDL</string>
  <key>CFBundleShortVersionString</key>
  <string>1.0</string>
  <key>CFBundleVersion</key>
  <string>1</string>
</dict>
</plist>
EOF
