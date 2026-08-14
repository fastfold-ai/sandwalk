#!/usr/bin/env bash
# bundle-agent-runtime.sh — copy a relocatable CPython + install sandwalk into it.
#
# Usage:
#   ./apps/packaging/bundle-agent-runtime.sh <dest-dir>
#
# Env:
#   AGENT_RUNTIME_PYTHON=3.12   (default)
#   SKIP_SMOKE=1                skip import smoke test
set -euo pipefail

DEST="${1:-}"
if [[ -z "${DEST}" ]]; then
  echo "usage: $0 <dest-dir>" >&2
  exit 2
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
CLI_DIR="${REPO_ROOT}/cli"
PY_VER="${AGENT_RUNTIME_PYTHON:-3.12}"

if ! command -v uv >/dev/null 2>&1; then
  echo "error: uv is required to bundle the agent runtime" >&2
  exit 1
fi

echo "==> Bundling agent runtime (CPython ${PY_VER}) → ${DEST}"
uv python install "${PY_VER}"

PYTHON_BIN="$(uv python find "${PY_VER}")"
if [[ -z "${PYTHON_BIN}" || ! -x "${PYTHON_BIN}" ]]; then
  echo "error: uv python find ${PY_VER} failed" >&2
  exit 1
fi
PYTHON_PREFIX="$(cd "$(dirname "${PYTHON_BIN}")/.." && pwd)"
if [[ ! -d "${PYTHON_PREFIX}/lib" ]]; then
  echo "error: expected full CPython prefix at ${PYTHON_PREFIX}" >&2
  exit 1
fi
echo "    source: ${PYTHON_PREFIX}"

rm -rf "${DEST}"
mkdir -p "${DEST}"
# Full prefix copy (bin/lib/include/share) so the interpreter is relocatable.
cp -a "${PYTHON_PREFIX}/." "${DEST}/"

# Prefer versioned binary; fall back to python3.
RUNTIME_PY=""
for name in "python${PY_VER}" python3 python; do
  if [[ -x "${DEST}/bin/${name}" ]]; then
    RUNTIME_PY="${DEST}/bin/${name}"
    break
  fi
done
if [[ -z "${RUNTIME_PY}" ]]; then
  echo "error: no python binary under ${DEST}/bin" >&2
  exit 1
fi

echo "==> Installing sandwalk (core deps) into runtime…"
# This tree is a private copy of CPython we own for the DMG — not a system
# interpreter. uv still treats managed builds as externally-managed without this.
(
  cd "${CLI_DIR}"
  uv pip install \
    --python "${RUNTIME_PY}" \
    --break-system-packages \
    --link-mode=copy \
    .
)

if [[ "${SKIP_SMOKE:-0}" != "1" ]]; then
  echo "==> Smoke-testing runtime imports…"
  "${RUNTIME_PY}" -c "import cli, agent_server, fastapi; print('ok', cli.__name__)"
  "${RUNTIME_PY}" -m cli --version >/dev/null
fi

echo "OK: agent runtime at ${DEST}"
echo "    python: ${RUNTIME_PY}"
