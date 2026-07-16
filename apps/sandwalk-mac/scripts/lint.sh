#!/usr/bin/env bash
# lint.sh — run pinned SwiftLint (advisory file_length warning)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "${ROOT}"

# Portable SwiftLint needs full Xcode's sourcekitd (not CLT alone).
if [[ -z "${DEVELOPER_DIR:-}" && -d /Applications/Xcode.app/Contents/Developer ]]; then
  export DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer
fi

"${ROOT}/scripts/install-swiftlint.sh"
BIN="${ROOT}/.tools/swiftlint"

echo "==> swiftlint lint (advisory file_length)"
# No --strict: file_length warnings must not fail CI/commits.
"${BIN}" lint --config .swiftlint.yml
