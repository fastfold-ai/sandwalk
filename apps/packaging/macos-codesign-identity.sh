#!/usr/bin/env bash
# Print the Developer ID Application identity to use for codesign.
# Prefer CODESIGN_IDENTITY / APPLE_SIGNING_IDENTITY; otherwise pick the first
# Developer ID Application identity in the keychain. Prints "-" if none.
set -euo pipefail

if [[ -n "${CODESIGN_IDENTITY:-}" ]]; then
  printf '%s\n' "${CODESIGN_IDENTITY}"
  exit 0
fi
if [[ -n "${APPLE_SIGNING_IDENTITY:-}" ]]; then
  printf '%s\n' "${APPLE_SIGNING_IDENTITY}"
  exit 0
fi

DETECTED="$(
  security find-identity -v -p codesigning 2>/dev/null \
    | sed -n 's/.*"\(Developer ID Application: .*\)".*/\1/p' \
    | head -n 1
)"
if [[ -n "${DETECTED}" ]]; then
  printf '%s\n' "${DETECTED}"
else
  printf '%s\n' "-"
fi
