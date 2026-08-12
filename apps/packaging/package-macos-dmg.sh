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
#   SKIP_AGENT_RUNTIME=1   skip embedding CPython + sandwalk into the helper
#   INSTALL=1              also copy assembled app to ~/Applications
#   OUT_DIR=...            output directory (default: apps/packaging/dist)
#   CODESIGN_IDENTITY=-    codesign identity (default `-` = ad-hoc / self-sign).
#                          Later: "Developer ID Application: …" from Keychain.
#   TAURI_SIGNING_PRIVATE_KEY / _PATH / _PASSWORD — minisign key for updater
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
# Stable name for README /releases/latest/download/Sandwalk-macos-arm64.dmg
DMG_LATEST_NAME="Sandwalk-macos-arm64.dmg"
DMG_LATEST_PATH="${OUT_DIR}/${DMG_LATEST_NAME}"

echo "==> Sandwalk macOS DMG package (v${VERSION})"
echo "    repo: ${REPO_ROOT}"

# --- 1. Tauri client ---------------------------------------------------------
# createUpdaterArtifacts needs a signing key when plugins.updater.pubkey is set.
KEY_PATH="${TAURI_SIGNING_PRIVATE_KEY_PATH:-${LOCAL_WEB}/src-tauri/.updater-key}"
if [[ -z "${TAURI_SIGNING_PRIVATE_KEY:-}" && -f "${KEY_PATH}" ]]; then
  export TAURI_SIGNING_PRIVATE_KEY_PATH="${KEY_PATH}"
fi

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

# --- 2b. Agent Server runtime + UI dist into helper Resources ---------------
HELPER_RESOURCES="${HELPER_APP}/Contents/Resources"
mkdir -p "${HELPER_RESOURCES}"

if [[ "${SKIP_AGENT_RUNTIME:-0}" != "1" ]]; then
  RUNTIME_STAGE="${OUT_DIR}/agent-runtime"
  mkdir -p "${OUT_DIR}"
  bash "${SCRIPT_DIR}/bundle-agent-runtime.sh" "${RUNTIME_STAGE}"
  rm -rf "${HELPER_RESOURCES}/agent-runtime"
  cp -a "${RUNTIME_STAGE}" "${HELPER_RESOURCES}/agent-runtime"
else
  echo "==> Skipping agent runtime (SKIP_AGENT_RUNTIME=1)"
fi

UI_DIST="${LOCAL_WEB}/dist"
if [[ ! -f "${UI_DIST}/index.html" ]]; then
  echo "==> Building local-web dist for packaged dashboard…"
  cd "${LOCAL_WEB}"
  pnpm run build
fi
if [[ -f "${UI_DIST}/index.html" ]]; then
  rm -rf "${HELPER_RESOURCES}/ui-dist"
  cp -a "${UI_DIST}" "${HELPER_RESOURCES}/ui-dist"
  echo "    ui-dist → ${HELPER_RESOURCES}/ui-dist"
else
  echo "warning: ${UI_DIST}/index.html missing — production dashboard may not load" >&2
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

CODESIGN_IDENTITY="${CODESIGN_IDENTITY:--}"
echo "==> Codesign (identity: ${CODESIGN_IDENTITY})..."
# Ad-hoc (`-`) is the default until Apple Developer ID + notarization are wired.
# With a Developer ID identity, also pass hardened runtime when ready for notary.
CODESIGN_EXTRA=()
if [[ "${CODESIGN_IDENTITY}" != "-" ]]; then
  CODESIGN_EXTRA+=(--options runtime --timestamp)
fi
# Bash 3.2 + `set -u` treats an empty array as unbound (`CODESIGN_EXTRA[@]`).
codesign --force --deep --sign "${CODESIGN_IDENTITY}" \
  ${CODESIGN_EXTRA[@]+"${CODESIGN_EXTRA[@]}"} \
  "${APP_STAGE}/Contents/Helpers/Sandwalk Server.app" 2>/dev/null || true
codesign --force --deep --sign "${CODESIGN_IDENTITY}" \
  ${CODESIGN_EXTRA[@]+"${CODESIGN_EXTRA[@]}"} \
  "${APP_STAGE}" 2>/dev/null || true
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

cp -f "${DMG_PATH}" "${DMG_LATEST_PATH}"

# --- 5. Updater archive (nested app = UI + helper + agent-runtime) ----------
UPDATER_TAR="${OUT_DIR}/Sandwalk.app.tar.gz"
echo "==> Creating updater archive ${UPDATER_TAR}..."
rm -f "${UPDATER_TAR}" "${UPDATER_TAR}.sig"
tar -C "${STAGE}" -czf "${UPDATER_TAR}" Sandwalk.app

SIG_B64=""
if [[ -z "${TAURI_SIGNING_PRIVATE_KEY:-}" && -f "${KEY_PATH}" ]]; then
  # Prefer key *contents* in env — PATH + empty password fails in non-TTY CI
  # with "Device not configured" when the CLI tries to prompt.
  TAURI_SIGNING_PRIVATE_KEY="$(cat "${KEY_PATH}")"
  export TAURI_SIGNING_PRIVATE_KEY
fi
if [[ -n "${TAURI_SIGNING_PRIVATE_KEY:-}" ]]; then
  echo "==> Signing nested updater archive (minisign)…"
  # Contents + PATH together make `tauri signer` pass both --private-key and
  # --private-key-path (fatal). Prefer the in-memory key.
  unset TAURI_SIGNING_PRIVATE_KEY_PATH
  export TAURI_SIGNING_PRIVATE_KEY_PASSWORD="${TAURI_SIGNING_PRIVATE_KEY_PASSWORD:-}"
  if (
    cd "${LOCAL_WEB}"
    pnpm exec tauri signer sign "${UPDATER_TAR}"
  ); then
    if [[ -f "${UPDATER_TAR}.sig" ]]; then
      SIG_B64="$(tr -d '\n' < "${UPDATER_TAR}.sig")"
    fi
  else
    echo "    warning: signer failed — DMG is still usable; fix key/password for updater artifacts" >&2
  fi
else
  echo "    skip updater sign (no TAURI_SIGNING_PRIVATE_KEY / ${KEY_PATH})"
fi

PUB_DATE="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
LATEST_JSON="${OUT_DIR}/latest.json"
# URL used inside latest.json — override when tagging a release.
DOWNLOAD_URL="${UPDATER_DOWNLOAD_URL:-https://github.com/fastfold-ai/sandwalk/releases/download/v${VERSION}/Sandwalk.app.tar.gz}"
python3 - "$LATEST_JSON" "$VERSION" "$PUB_DATE" "$DOWNLOAD_URL" "$SIG_B64" <<'PY'
import json, sys
from pathlib import Path

path, version, pub_date, url, sig = sys.argv[1:6]
platforms = {}
if sig:
    platforms["darwin-aarch64"] = {"signature": sig, "url": url}
Path(path).write_text(
    json.dumps(
        {
            "version": version,
            "notes": f"Sandwalk {version}",
            "pub_date": pub_date,
            "platforms": platforms,
        },
        indent=2,
    )
    + "\n"
)
print(f"    wrote {path}")
PY

echo ""
echo "OK: ${DMG_PATH}"
echo "    latest alias: ${DMG_LATEST_PATH}"
echo "    updater: ${UPDATER_TAR}"
echo "    manifest: ${LATEST_JSON}"
echo "    nested helper: Sandwalk.app/Contents/Helpers/Sandwalk Server.app"
echo "    install locally: INSTALL=1 ${SCRIPT_DIR}/package-macos-dmg.sh"
echo "    or: open \"${DMG_PATH}\" and drag Sandwalk to Applications"
