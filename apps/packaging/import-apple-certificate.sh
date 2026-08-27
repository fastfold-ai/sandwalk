#!/usr/bin/env bash
# Import a base64-encoded Developer ID .p12 into a temporary keychain (CI).
#
# Required env:
#   APPLE_CERTIFICATE            base64 of the .p12
#   APPLE_CERTIFICATE_PASSWORD   .p12 password
# Optional:
#   KEYCHAIN_PATH                default $RUNNER_TEMP/sandwalk-signing.keychain-db
set -euo pipefail

if [[ -z "${APPLE_CERTIFICATE:-}" ]]; then
  echo "APPLE_CERTIFICATE is empty — skip import (ad-hoc codesign)."
  exit 0
fi
: "${APPLE_CERTIFICATE_PASSWORD:?APPLE_CERTIFICATE_PASSWORD is required when APPLE_CERTIFICATE is set}"

TMP_DIR="${RUNNER_TEMP:-${TMPDIR:-/tmp}}"
KEYCHAIN_PATH="${KEYCHAIN_PATH:-${TMP_DIR}/sandwalk-signing.keychain-db}"
KEYCHAIN_PASSWORD="${KEYCHAIN_PASSWORD:-$(openssl rand -base64 24)}"
P12_PATH="${TMP_DIR}/sandwalk-developer-id.p12"

cleanup() {
  rm -f "${P12_PATH}"
}
trap cleanup EXIT

echo "${APPLE_CERTIFICATE}" | base64 --decode > "${P12_PATH}"

if [[ ! -f "${KEYCHAIN_PATH}" ]]; then
  security create-keychain -p "${KEYCHAIN_PASSWORD}" "${KEYCHAIN_PATH}"
fi
security set-keychain-settings -lut 21600 "${KEYCHAIN_PATH}"
security unlock-keychain -p "${KEYCHAIN_PASSWORD}" "${KEYCHAIN_PATH}"
security import "${P12_PATH}" \
  -k "${KEYCHAIN_PATH}" \
  -P "${APPLE_CERTIFICATE_PASSWORD}" \
  -T /usr/bin/codesign \
  -T /usr/bin/security \
  -T /usr/bin/productbuild
security set-key-partition-list -S apple-tool:,apple:,codesign: \
  -s -k "${KEYCHAIN_PASSWORD}" "${KEYCHAIN_PATH}" >/dev/null
security list-keychain -d user -s "${KEYCHAIN_PATH}" $(security list-keychain -d user | tr -d '"')

echo "Imported Developer ID certificate into ${KEYCHAIN_PATH}"
security find-identity -v -p codesigning "${KEYCHAIN_PATH}"
