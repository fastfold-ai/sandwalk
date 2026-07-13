#!/usr/bin/env bash
# package-app.sh — build Sandwalk.app and install to ~/Applications
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BUILD_DIR="${ROOT}/.build"
CONFIG="${CONFIG:-debug}"
BIN="${BUILD_DIR}/arm64-apple-macosx/${CONFIG}/Sandwalk"
APP_OUT="${BUILD_DIR}/Sandwalk.app"
INSTALL_DIR="${INSTALL_DIR:-${HOME}/Applications}"
INSTALLED="${INSTALL_DIR}/Sandwalk.app"

echo "==> Building Sandwalk (${CONFIG})..."
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

BUNDLE_SRC="$(dirname "${BIN}")/Sandwalk_Sandwalk.bundle"
if [[ -d "${BUNDLE_SRC}" ]]; then
  cp -R "${BUNDLE_SRC}" "${APP_OUT}/Contents/MacOS/"
fi

echo "==> Generating AppIcon.icns..."
MASTER="${ROOT}/Resources/AppIcon-1024.png"
MODULE_ICON="${ROOT}/Sources/Sandwalk/Resources/AppIcon-1024.png"
ICONSET="${BUILD_DIR}/AppIcon.iconset"
rm -rf "${ICONSET}"
mkdir -p "${ICONSET}" "${ROOT}/Resources" "$(dirname "${MODULE_ICON}")"

# Bright white full-bleed master (system masks to squircle — like ChatGPT/Ollama).
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

echo "==> Ad-hoc sign..."
codesign --force --deep --sign - "${APP_OUT}" 2>/dev/null || true
xattr -dr com.apple.quarantine "${APP_OUT}" 2>/dev/null || true

echo "==> Installing to ${INSTALLED}..."
mkdir -p "${INSTALL_DIR}"
pkill -x Sandwalk 2>/dev/null || true
sleep 0.4
rm -rf "${INSTALLED}"
cp -R "${APP_OUT}" "${INSTALLED}"
xattr -dr com.apple.quarantine "${INSTALLED}" 2>/dev/null || true

echo "OK: ${INSTALLED}"
echo "Open with: open \"${INSTALLED}\""
