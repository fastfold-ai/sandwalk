#!/usr/bin/env bash
# Build Plugin Manager zip for Sandwalk PyMOL MCP (commercial + open-source).
# Bundles the PyMOL plugin + vendored agentic-pymol MCP server (no git fetch).
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT_DIR="${ROOT_DIR}/dist"
PKG_DIR_NAME="sandwalk_pymol_plugin"
VERSION="${1:-}"

# Prefer packaging/vendor; fall back to CLI vendor (source of truth for sandwalk installs).
VENDOR_SRC="${ROOT_DIR}/vendor/agentic-pymol"
CLI_VENDOR="${ROOT_DIR}/../../cli/src/agent/mcps/pymol_mcp/vendor/agentic-pymol"
if [[ ! -f "${VENDOR_SRC}/pyproject.toml" && -f "${CLI_VENDOR}/pyproject.toml" ]]; then
  mkdir -p "${ROOT_DIR}/vendor"
  rm -rf "${VENDOR_SRC}"
  cp -R "${CLI_VENDOR}" "${VENDOR_SRC}"
fi
if [[ ! -f "${VENDOR_SRC}/pyproject.toml" ]]; then
  echo "Error: missing vendored agentic-pymol at ${VENDOR_SRC}" >&2
  exit 1
fi

if [[ -z "${VERSION}" ]]; then
  VERSION="$(tr -d '[:space:]' < "${ROOT_DIR}/VERSION")"
fi

# Normalize: accept 0.0.1 or v0.0.1; emit files with v-prefix.
VERSION_BARE="${VERSION#v}"
VERSION_TAG="v${VERSION_BARE}"

STAGING_DIR="$(mktemp -d)"
trap 'rm -rf "${STAGING_DIR}"' EXIT

mkdir -p "${OUT_DIR}" "${STAGING_DIR}/${PKG_DIR_NAME}"

python3 - "${ROOT_DIR}" "${STAGING_DIR}/${PKG_DIR_NAME}" "${VERSION_BARE}" <<'PY'
import pathlib
import re
import shutil
import sys

root = pathlib.Path(sys.argv[1])
dest = pathlib.Path(sys.argv[2])
version = sys.argv[3]
src_pkg = root / "sandwalk_pymol_plugin"
vendor_src = root / "vendor" / "agentic-pymol"

runtime_files = ["__init__.py", "plugin.ui"]
for rel in runtime_files:
    src = src_pkg / rel
    if not src.is_file():
        raise SystemExit(f"Missing runtime file: {src}")
    shutil.copy2(src, dest / rel)

if not (vendor_src / "pyproject.toml").is_file():
    raise SystemExit(f"Missing vendored package: {vendor_src}")
vendor_dest = dest / "vendor" / "agentic-pymol"
vendor_dest.parent.mkdir(parents=True, exist_ok=True)
shutil.copytree(vendor_src, vendor_dest)

init_path = dest / "__init__.py"
text = init_path.read_text(encoding="utf-8")
updated, n = re.subn(
    r'^PLUGIN_VERSION\s*=\s*["\'][^"\']*["\']',
    f'PLUGIN_VERSION = "{version}"',
    text,
    count=1,
    flags=re.M,
)
if n != 1:
    raise SystemExit("Could not stamp PLUGIN_VERSION in __init__.py")
init_path.write_text(updated, encoding="utf-8")
PY

VERSIONED_NAME="sandwalk-pymol-plugin-${VERSION_TAG}.zip"
STABLE_NAME="sandwalk-pymol-plugin.zip"
VERSIONED_PATH="${OUT_DIR}/${VERSIONED_NAME}"
STABLE_PATH="${OUT_DIR}/${STABLE_NAME}"

python3 - "${STAGING_DIR}" "${PKG_DIR_NAME}" "${VERSIONED_PATH}" <<'PY'
import pathlib
import sys
import zipfile

staging = pathlib.Path(sys.argv[1])
pkg = pathlib.Path(sys.argv[2])
zip_path = pathlib.Path(sys.argv[3])
root = staging / pkg

with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
    for path in sorted(root.rglob("*")):
        if path.is_file():
            zf.write(path, path.relative_to(staging))

print(zip_path)
PY

cp -f "${VERSIONED_PATH}" "${STABLE_PATH}"

echo "Built plugin zip (plugin + vendored agentic-pymol):"
echo "  ${VERSIONED_PATH}"
echo "  ${STABLE_PATH}"
echo ""
echo "Copy to sandwalk-landing for public hosting:"
echo "  mkdir -p ../../sandwalk-landing/public/pymol"
echo "  cp ${STABLE_PATH} ../../sandwalk-landing/public/pymol/plugin.zip"
echo "  cp ${VERSIONED_PATH} ../../sandwalk-landing/public/pymol/plugin-${VERSION_TAG}.zip"
echo "Public URLs:"
echo "  https://sandwalk.sh/pymol/plugin.zip"
echo "  https://sandwalk.sh/pymol/plugin-${VERSION_TAG}.zip"
