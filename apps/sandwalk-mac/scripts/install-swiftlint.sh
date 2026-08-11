#!/usr/bin/env bash
# install-swiftlint.sh — download a pinned SwiftLint portable binary into .tools/
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "${ROOT}"

VERSION="$(tr -d '[:space:]' < .swiftlint-version)"
TOOLS_DIR="${ROOT}/.tools"
BIN="${TOOLS_DIR}/swiftlint"
STAMP="${TOOLS_DIR}/swiftlint.version"

if [[ -x "${BIN}" && -f "${STAMP}" && "$(cat "${STAMP}")" == "${VERSION}" ]]; then
  echo "SwiftLint ${VERSION} already installed at ${BIN}"
  "${BIN}" version
  exit 0
fi

TMP="$(mktemp -d)"
cleanup() { rm -rf "${TMP}"; }
trap cleanup EXIT

ZIP_URL="https://github.com/realm/SwiftLint/releases/download/${VERSION}/portable_swiftlint.zip"
echo "==> Downloading SwiftLint ${VERSION}"
curl -fsSL "${ZIP_URL}" -o "${TMP}/swiftlint.zip"
unzip -q "${TMP}/swiftlint.zip" -d "${TMP}/out"

mkdir -p "${TOOLS_DIR}"
# Portable zip contains a `swiftlint` binary at the top level.
install -m 755 "${TMP}/out/swiftlint" "${BIN}"
printf '%s\n' "${VERSION}" > "${STAMP}"

echo "Installed SwiftLint $(${BIN} version) -> ${BIN}"
