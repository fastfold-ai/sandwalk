#!/usr/bin/env bash
# Submit a DMG to Apple notarization and staple the ticket.
#
# Required env:
#   APPLE_ID                      Apple ID email
#   APPLE_APP_SPECIFIC_PASSWORD   App-specific password (appleid.apple.com)
#   APPLE_TEAM_ID                 10-character Team ID
set -euo pipefail

DMG_PATH="${1:-}"
if [[ -z "${DMG_PATH}" || ! -f "${DMG_PATH}" ]]; then
  echo "usage: $0 /path/to/Sandwalk-*-macos-arm64.dmg" >&2
  exit 1
fi
: "${APPLE_ID:?APPLE_ID is required}"
: "${APPLE_APP_SPECIFIC_PASSWORD:?APPLE_APP_SPECIFIC_PASSWORD is required}"
: "${APPLE_TEAM_ID:?APPLE_TEAM_ID is required}"

if [[ -n "${CODESIGN_IDENTITY:-}" && "${CODESIGN_IDENTITY}" != "-" ]]; then
  echo "==> Codesign DMG (identity: ${CODESIGN_IDENTITY})..."
  codesign --force --sign "${CODESIGN_IDENTITY}" --timestamp "${DMG_PATH}"
fi

echo "==> Notarizing ${DMG_PATH}..."
xcrun notarytool submit "${DMG_PATH}" \
  --apple-id "${APPLE_ID}" \
  --password "${APPLE_APP_SPECIFIC_PASSWORD}" \
  --team-id "${APPLE_TEAM_ID}" \
  --wait

echo "==> Stapling notarization ticket..."
xcrun stapler staple "${DMG_PATH}"
xcrun stapler validate "${DMG_PATH}"
echo "OK: notarized and stapled ${DMG_PATH}"
