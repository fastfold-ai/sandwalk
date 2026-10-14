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

echo "==> Notarizing ${DMG_PATH}..."
NOTARY_LOG="$(mktemp)"
set +e
xcrun notarytool submit "${DMG_PATH}" \
  --apple-id "${APPLE_ID}" \
  --password "${APPLE_APP_SPECIFIC_PASSWORD}" \
  --team-id "${APPLE_TEAM_ID}" \
  --wait | tee "${NOTARY_LOG}"
NOTARY_RC="${PIPESTATUS[0]}"
set -e
SUBMISSION_ID="$(sed -n 's/^  id: //p' "${NOTARY_LOG}" | head -1)"
if [[ "${NOTARY_RC}" -ne 0 ]] || ! grep -q "status: Accepted" "${NOTARY_LOG}"; then
  echo "error: notarization was not accepted" >&2
  if [[ -n "${SUBMISSION_ID}" ]]; then
    xcrun notarytool log "${SUBMISSION_ID}" \
      --apple-id "${APPLE_ID}" \
      --password "${APPLE_APP_SPECIFIC_PASSWORD}" \
      --team-id "${APPLE_TEAM_ID}" >&2 || true
  fi
  rm -f "${NOTARY_LOG}"
  exit 1
fi
rm -f "${NOTARY_LOG}"

echo "==> Stapling notarization ticket..."
xcrun stapler staple "${DMG_PATH}"
xcrun stapler validate "${DMG_PATH}"
echo "OK: notarized and stapled ${DMG_PATH}"
