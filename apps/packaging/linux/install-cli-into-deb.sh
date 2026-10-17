#!/usr/bin/env bash
# Put the bundled agent CLI into an already-built Sandwalk .deb.
#
# Usage:
#   ./apps/packaging/linux/install-cli-into-deb.sh <agent-runtime-dir> <package.deb>
#
# Adds:
#   /usr/bin/sandwalk
#   /usr/lib/sandwalk/agent-runtime/   (relocatable CPython + sandwalk)
set -euo pipefail

RUNTIME="${1:-}"
DEB="${2:-}"
if [[ -z "${RUNTIME}" || -z "${DEB}" ]]; then
  echo "usage: $0 <agent-runtime-dir> <package.deb>" >&2
  exit 2
fi
if [[ ! -x "${RUNTIME}/bin/python3" && ! -x "${RUNTIME}/bin/python3.12" && ! -x "${RUNTIME}/bin/python" ]]; then
  echo "error: no python binary in ${RUNTIME}/bin" >&2
  exit 1
fi
if [[ ! -f "${DEB}" ]]; then
  echo "error: deb not found: ${DEB}" >&2
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(mktemp -d)"
trap 'rm -rf "${ROOT}"' EXIT

dpkg-deb -R "${DEB}" "${ROOT}"
mkdir -p "${ROOT}/usr/bin" "${ROOT}/usr/lib/sandwalk" "${ROOT}/usr/lib/systemd/user"
install -m 755 "${SCRIPT_DIR}/sandwalk" "${ROOT}/usr/bin/sandwalk"
install -m 755 "${SCRIPT_DIR}/sandwalk-serve" "${ROOT}/usr/lib/sandwalk/sandwalk-serve"
install -m 644 "${SCRIPT_DIR}/sandwalk.service" "${ROOT}/usr/lib/systemd/user/sandwalk.service"
rm -rf "${ROOT}/usr/lib/sandwalk/agent-runtime"
cp -a "${RUNTIME}" "${ROOT}/usr/lib/sandwalk/agent-runtime"

if [[ -f "${ROOT}/DEBIAN/control" ]]; then
  SIZE_KB="$(du -sk "${ROOT}" | awk '{print $1}')"
  if grep -q '^Installed-Size:' "${ROOT}/DEBIAN/control"; then
    sed -i.bak "s/^Installed-Size:.*/Installed-Size: ${SIZE_KB}/" "${ROOT}/DEBIAN/control"
    rm -f "${ROOT}/DEBIAN/control.bak"
  else
    printf 'Installed-Size: %s\n' "${SIZE_KB}" >> "${ROOT}/DEBIAN/control"
  fi
fi

(
  cd "${ROOT}"
  find . -type f ! -path './DEBIAN/*' -print0 \
    | sort -z \
    | xargs -0 md5sum \
    | sed 's|  \./|  |'
) > "${ROOT}/DEBIAN/md5sums"

dpkg-deb --root-owner-group -Zxz -b "${ROOT}" "${DEB}"
echo "OK: CLI installed into ${DEB}"
