#!/usr/bin/env bash
# package-app.sh — build Sandwalk Server.app (menubar supervisor)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BUILD_DIR="${ROOT}/.build"
CONFIG="${CONFIG:-debug}"
BIN="${BUILD_DIR}/arm64-apple-macosx/${CONFIG}/Sandwalk"
APP_NAME="${APP_NAME:-Sandwalk Server.app}"
APP_OUT="${BUILD_DIR}/${APP_NAME}"
INSTALL_DIR="${INSTALL_DIR:-${HOME}/Applications}"
INSTALLED="${INSTALL_DIR}/${APP_NAME}"
SKIP_INSTALL="${SKIP_INSTALL:-0}"

echo "==> Building Sandwalk Server (${CONFIG})..."
cd "${ROOT}"
if [[ "${CONFIG}" == "release" ]]; then
  swift build -c release
else
  swift build
fi

if [[ ! -x "${BIN}" ]]; then
  BIN="$(swift build ${CONFIG:+-c ${CONFIG}} --show-bin-path)/Sandwalk"
fi
[[ -x "${BIN}" ]] || { echo "error: Sandwalk binary not found at ${BIN}"; exit 1; }

echo "==> Staging ${APP_OUT}..."
rm -rf "${APP_OUT}"
mkdir -p "${APP_OUT}/Contents/MacOS" "${APP_OUT}/Contents/Resources"

cp "${BIN}" "${APP_OUT}/Contents/MacOS/Sandwalk"
chmod +x "${APP_OUT}/Contents/MacOS/Sandwalk"
cp "${ROOT}/Resources/Info.plist" "${APP_OUT}/Contents/Info.plist"

BUNDLE_SRC="$(dirname "${BIN}")/Sandwalk_SandwalkCore.bundle"
if [[ -d "${BUNDLE_SRC}" ]]; then
  cp -R "${BUNDLE_SRC}" "${APP_OUT}/Contents/MacOS/"
  # SwiftPM dumps a flat *.bundle (pngs only). Developer ID requires a real bundle.
  bash "${ROOT}/scripts/ensure-resource-bundle.sh" \
    "${APP_OUT}/Contents/MacOS/Sandwalk_SandwalkCore.bundle" \
    "ai.fastfold.sandwalk-server.SandwalkCore"
fi

echo "==> Generating AppIcon.icns..."
MASTER="${ROOT}/Resources/AppIcon-1024.png"
MODULE_ICON="${ROOT}/Sources/SandwalkCore/Resources/AppIcon-1024.png"
ICONSET="${BUILD_DIR}/AppIcon.iconset"
rm -rf "${ICONSET}"
mkdir -p "${ICONSET}" "${ROOT}/Resources" "$(dirname "${MODULE_ICON}")"

# Bright white full-bleed master (system masks it to the squircle shape).
swift "${ROOT}/scripts/generate_app_icon.swift" "${MASTER}" 1024 >/dev/null
cp "${MASTER}" "${MODULE_ICON}"

for size in 16 32 128 256 512; do
  sips -z "${size}" "${size}" "${MASTER}" --out "${ICONSET}/icon_${size}x${size}.png" >/dev/null
  dbl=$((size * 2))
  sips -z "${dbl}" "${dbl}" "${MASTER}" --out "${ICONSET}/icon_${size}x${size}@2x.png" >/dev/null
done
iconutil -c icns "${ICONSET}" -o "${APP_OUT}/Contents/Resources/AppIcon.icns"
rm -rf "${ICONSET}"

printf 'APPL????' > "${APP_OUT}/Contents/PkgInfo"

IDENTITY="${CODESIGN_IDENTITY:-${APPLE_SIGNING_IDENTITY:--}}"
ENTITLEMENTS="${ROOT}/Resources/entitlements.plist"
echo "==> Codesign helper (identity: ${IDENTITY})..."
SIGN_ARGS=(--force --sign "${IDENTITY}")
if [[ "${IDENTITY}" != "-" ]]; then
  SIGN_ARGS+=(--options runtime --timestamp)
  if [[ -f "${ENTITLEMENTS}" ]]; then
    SIGN_ARGS+=(--entitlements "${ENTITLEMENTS}")
  fi
fi
# Sign nested SwiftPM resource bundles before the .app (Developer ID rejects unsigned children).
shopt -s nullglob
for nested in "${APP_OUT}/Contents/MacOS/"*.bundle "${APP_OUT}/Contents/Frameworks/"*.framework; do
  codesign "${SIGN_ARGS[@]}" "${nested}"
done
shopt -u nullglob
codesign "${SIGN_ARGS[@]}" "${APP_OUT}"
xattr -dr com.apple.quarantine "${APP_OUT}" 2>/dev/null || true

if [[ "${SKIP_INSTALL}" == "1" ]]; then
  echo "OK (skip install): ${APP_OUT}"
  exit 0
fi

echo "==> Installing to ${INSTALLED}..."
mkdir -p "${INSTALL_DIR}"
# Prefer quitting by bundle id so we don't collide with the Tauri client binary name.
osascript -e 'quit app "Sandwalk Server"' 2>/dev/null || true
pkill -x Sandwalk 2>/dev/null || true
sleep 0.4
rm -rf "${INSTALLED}"
cp -R "${APP_OUT}" "${INSTALLED}"
xattr -dr com.apple.quarantine "${INSTALLED}" 2>/dev/null || true

echo "OK: ${INSTALLED}"
echo "Open with: open \"${INSTALLED}\""
