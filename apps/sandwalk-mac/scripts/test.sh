#!/usr/bin/env bash
# test.sh — run Sandwalk unit tests with scoped code coverage (≥80% on pure modules)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "${ROOT}"

echo "==> SwiftLint (pinned file_length gate)"
"${ROOT}/scripts/lint.sh"

COVERAGE_THRESHOLD="${COVERAGE_THRESHOLD:-80}"

# Pure logic included in the coverage gate (mirrors local-web vitest include set).
COVERAGE_SOURCES=(
  Sources/SandwalkCore/PathSupport.swift
  Sources/SandwalkCore/SettingsSection.swift
  Sources/SandwalkCore/AppConfig.swift
  Sources/SandwalkCore/AuthSettingsStore.swift
  Sources/SandwalkCore/AgentAPI/AgentAPIModels.swift
)

# XCTest lives in full Xcode, not Command Line Tools alone.
if [[ -z "${DEVELOPER_DIR:-}" && -d /Applications/Xcode.app/Contents/Developer ]]; then
  export DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer
fi

echo "==> swift test --enable-code-coverage"
swift test --enable-code-coverage

BIN_DIR="$(swift build --show-bin-path)"
PROFDATA="${BIN_DIR}/codecov/default.profdata"
# SPM names the test binary <Package>PackageTests.xctest on macOS.
XCTEST_BUNDLE="${BIN_DIR}/SandwalkPackageTests.xctest"
if [[ -d "${XCTEST_BUNDLE}" ]]; then
  BINARY="${XCTEST_BUNDLE}/Contents/MacOS/SandwalkPackageTests"
else
  BINARY="${BIN_DIR}/SandwalkPackageTests"
fi

echo ""
echo "==> Coverage report (unit-testable SandwalkCore modules, threshold ${COVERAGE_THRESHOLD}%)"
if [[ ! -f "${PROFDATA}" || ! -x "${BINARY}" ]]; then
  echo "Could not locate profdata/binary for llvm-cov."
  echo "  profdata: ${PROFDATA}"
  echo "  binary:   ${BINARY}"
  exit 1
fi

REPORT="$(xcrun llvm-cov report \
  "${BINARY}" \
  -instr-profile="${PROFDATA}" \
  -ignore-filename-regex='\.build|Tests/' \
  "${COVERAGE_SOURCES[@]}")"

echo "${REPORT}"

LINE_COV="$(echo "${REPORT}" | awk '/^TOTAL/ {
  gsub(/%/, "", $10)
  print $10
}')"

if [[ -z "${LINE_COV}" ]]; then
  echo ""
  echo "ERROR: Could not parse line coverage from llvm-cov TOTAL row."
  exit 1
fi

echo ""
echo "Scoped line coverage: ${LINE_COV}% (threshold: ${COVERAGE_THRESHOLD}%)"

# Persist text + lcov for CI artifacts and Codecov (same style as Agent CLI uploads).
echo "${REPORT}" > coverage-report.txt
xcrun llvm-cov export \
  "${BINARY}" \
  -instr-profile="${PROFDATA}" \
  -format=lcov \
  -ignore-filename-regex='\.build|Tests/' \
  "${COVERAGE_SOURCES[@]}" \
  > coverage.lcov
echo "Wrote coverage-report.txt and coverage.lcov"

if awk -v cov="${LINE_COV}" -v thresh="${COVERAGE_THRESHOLD}" 'BEGIN { exit (cov + 0 >= thresh + 0) ? 0 : 1 }'; then
  echo "Coverage gate passed."
else
  echo "ERROR: Scoped line coverage ${LINE_COV}% is below ${COVERAGE_THRESHOLD}%."
  exit 1
fi

echo ""
echo "HTML report (scoped modules):"
echo "  xcrun llvm-cov show ${BINARY} -instr-profile=${PROFDATA} -format=html -output-dir coverage-html ${COVERAGE_SOURCES[*]}"
echo "  open coverage-html/index.html"
