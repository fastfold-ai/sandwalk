#!/usr/bin/env bash
# lint.sh — run pinned SwiftLint (file_length gate)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "${ROOT}"

# Portable SwiftLint needs full Xcode's sourcekitd (not CLT alone).
if [[ -z "${DEVELOPER_DIR:-}" && -d /Applications/Xcode.app/Contents/Developer ]]; then
  export DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer
fi

"${ROOT}/scripts/install-swiftlint.sh"
BIN="${ROOT}/.tools/swiftlint"

echo "==> swiftlint lint (file_length)"
"${BIN}" lint --strict --config .swiftlint.yml
