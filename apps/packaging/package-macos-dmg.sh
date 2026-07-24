#!/usr/bin/env bash
# package-macos-dmg.sh - build Sandwalk.app (Tauri) + nested Sandwalk Server helper into a DMG
#
# Layout:
#   Sandwalk.app
#   └── Contents/Helpers/Sandwalk Server.app
#
# Usage:
#   ./apps/packaging/package-macos-dmg.sh
#
# Env:
#   CONFIG=release|debug   (default: release) - Swift helper build
#   SKIP_TAURI=1           skip pnpm tauri build (reuse existing bundle)
#   INSTALL=1              also copy assembled app to ~/Applications
#   OUT_DIR=...            output directory (default: apps/packaging/dist)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
LOCAL_WEB="${REPO_ROOT}/apps/local-web"
MAC_APP="${REPO_ROOT}/apps/sandwalk-mac"
CONFIG="${CONFIG:-release}"
OUT_DIR="${OUT_DIR:-${SCRIPT_DIR}/dist}"
STAGE="${OUT_DIR}/stage"
VERSION="$(
  node -p 'require(process.argv[1]).version' "${LOCAL_WEB}/package.json" 2>/dev/null || echo '0.0.1'
)"
DMG_NAME="Sandwalk-${VERSION}-macos-arm64.dmg"
DMG_PATH="${OUT_DIR}/${DMG_NAME}"

echo "==> Sandwalk macOS DMG package (v${VERSION})"
echo "    repo: ${REPO_ROOT}"

# --- 1. Tauri client ---------------------------------------------------------
TAURI_BUNDLE=""
if [[ "${SKIP_TAURI:-0}" != "1" ]]; then
  echo "==> Building Tauri client (Sandwalk.app)..."
  cd "${LOCAL_WEB}"
  pnpm exec tauri build
fi

CARGO_TARGET="${CARGO_TARGET_DIR:-${LOCAL_WEB}/src-tauri/target}"
for candidate in \
  "${CARGO_TARGET}/release/bundle/macos/Sandwalk.app" \
  "${LOCAL_WEB}/src-tauri/target/release/bundle/macos/Sandwalk.app" \
  "${CARGO_TARGET}/aarch64-apple-darwin/release/bundle/macos/Sandwalk.app" \
  "${LOCAL_WEB}/src-tauri/target/aarch64-apple-darwin/release/bundle/macos/Sandwalk.app" \
  "${CARGO_TARGET}/x86_64-apple-darwin/release/bundle/macos/Sandwalk.app" \
  "${LOCAL_WEB}/src-tauri/target/x86_64-apple-darwin/release/bundle/macos/Sandwalk.app"
do
  if [[ -d "${candidate}" ]]; then
    TAURI_BUNDLE="${candidate}"
    break
  fi
done

# Last resort: newest Sandwalk.app under known target roots.
if [[ -z "${TAURI_BUNDLE}" ]]; then
  TAURI_BUNDLE="$(
    find "${CARGO_TARGET}" "${LOCAL_WEB}/src-tauri/target" \
      -type d -name 'Sandwalk.app' -path '*/bundle/macos/*' 2>/dev/null \
      | head -n 1 || true
  )"
fi

if [[ -z "${TAURI_BUNDLE}" || ! -d "${TAURI_BUNDLE}" ]]; then
  echo "error: Sandwalk.app not found under cargo target bundle/macos/"
  echo "       CARGO_TARGET_DIR=${CARGO_TARGET}"
  echo "       Run without SKIP_TAURI, or: pnpm --filter @sandwalk/agent-local-web tauri:build"
  exit 1
fi
echo "    client: ${TAURI_BUNDLE}"

# --- 2. Menubar helper -------------------------------------------------------
echo "==> Building Sandwalk Server helper..."
cd "${MAC_APP}"
CONFIG="${CONFIG}" SKIP_INSTALL=1 APP_NAME="Sandwalk Server.app" \
  ./scripts/package-app.sh
HELPER_APP="${MAC_APP}/.build/Sandwalk Server.app"
if [[ ! -d "${HELPER_APP}" ]]; then
  echo "error: helper missing at ${HELPER_APP}"
  exit 1
fi

# --- 3. Assemble nested app --------------------------------------------------
echo "==> Assembling nested Sandwalk.app..."
rm -rf "${STAGE}"
mkdir -p "${STAGE}"
APP_STAGE="${STAGE}/Sandwalk.app"
cp -R "${TAURI_BUNDLE}" "${APP_STAGE}"
mkdir -p "${APP_STAGE}/Contents/Helpers"
rm -rf "${APP_STAGE}/Contents/Helpers/Sandwalk Server.app"
cp -R "${HELPER_APP}" "${APP_STAGE}/Contents/Helpers/Sandwalk Server.app"

echo "==> Ad-hoc codesign..."
codesign --force --deep --sign - "${APP_STAGE}/Contents/Helpers/Sandwalk Server.app" 2>/dev/null || true
codesign --force --deep --sign - "${APP_STAGE}" 2>/dev/null || true
xattr -dr com.apple.quarantine "${APP_STAGE}" 2>/dev/null || true

ln -sf /Applications "${STAGE}/Applications"

# --- 4. DMG ------------------------------------------------------------------
echo "==> Creating ${DMG_PATH}..."
mkdir -p "${OUT_DIR}"
rm -f "${DMG_PATH}"
hdiutil create \
  -volname "Sandwalk" \
  -srcfolder "${STAGE}" \
  -ov \
  -format UDZO \
  "${DMG_PATH}"

if [[ "${INSTALL:-0}" == "1" ]]; then
  DEST="${HOME}/Applications/Sandwalk.app"
  echo "==> Installing to ${DEST}..."
  osascript -e 'quit app "Sandwalk"' 2>/dev/null || true
  osascript -e 'quit app "Sandwalk Server"' 2>/dev/null || true
  pkill -x sandwalk-desktop 2>/dev/null || true
  pkill -x Sandwalk 2>/dev/null || true
  sleep 0.4
  rm -rf "${DEST}"
  mkdir -p "${HOME}/Applications"
  cp -R "${APP_STAGE}" "${DEST}"
  xattr -dr com.apple.quarantine "${DEST}" 2>/dev/null || true
  echo "    open \"${DEST}\""
fi

echo ""
echo "OK: ${DMG_PATH}"
echo "    nested helper: Sandwalk.app/Contents/Helpers/Sandwalk Server.app"
echo "    install locally: INSTALL=1 ${SCRIPT_DIR}/package-macos-dmg.sh"
echo "    or: open \"${DMG_PATH}\" and drag Sandwalk to Applications"
