#!/usr/bin/env bash
# Sandwalk CLI installer
#
#   curl -fsSL https://sandwalk.sh/install.sh | bash
#   curl -fsSL https://sandwalk.sh/install.sh | bash -s -- --pre
#   curl -fsSL https://sandwalk.sh/install.sh | bash -s -- --version 0.1.11
#
set -euo pipefail

PACKAGE="sandwalk"
REPO="fastfold-ai/sandwalk"
REPO_GIT="https://github.com/${REPO}.git"
MIN_PYTHON="3.11"
API_BASE="https://api.github.com/repos/${REPO}"

MUTED='\033[0;2m'
CYAN='\033[0;36m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
RED='\033[0;31m'
NC='\033[0m'

# Status goes to stderr so command substitutions only capture the return value.
info()  { printf "${CYAN}%s${NC}\n" "$*" >&2; }
ok()    { printf "${GREEN}%s${NC}\n" "$*" >&2; }
warn()  { printf "${YELLOW}%s${NC}\n" "$*" >&2; }
fail()  { printf "${RED}Error: %s${NC}\n" "$*" >&2; exit 1; }

usage() {
  cat <<EOF
Sandwalk CLI installer

Usage:
  curl -fsSL https://sandwalk.sh/install.sh | bash
  curl -fsSL https://sandwalk.sh/install.sh | bash -s -- [options]

Options:
  -h, --help              Show this help
  -v, --version <ver>     Install a specific release tag (e.g. 0.1.11)
      --ref <ref>         Git ref (branch / tag / sha); skips release lookup
      --pre               Use the newest GitHub release, including pre-releases
      --setup             Run interactive sandwalk setup after install
      --no-setup          Skip setup (default when stdin is not a TTY)

Installs the Python CLI on macOS and Linux from GitHub (cli/ subdirectory)
via uv, pipx, or pip. Detects the OS and puts sandwalk on PATH.
Default: latest stable GitHub Release tag. Falls back to main if no releases exist.

After install, sandwalk desktop downloads the latest Mac app or Ubuntu .deb.
EOF
}

requested_version=""
explicit_ref=""
want_pre=false
force_setup=false
force_no_setup=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    -h|--help)
      usage
      exit 0
      ;;
    -v|--version)
      [[ -n "${2:-}" ]] || fail "--version requires a value (e.g. 0.1.11)"
      requested_version="$2"
      shift 2
      ;;
    --ref)
      [[ -n "${2:-}" ]] || fail "--ref requires a git ref"
      explicit_ref="$2"
      shift 2
      ;;
    --pre)
      want_pre=true
      shift
      ;;
    --setup)
      force_setup=true
      shift
      ;;
    --no-setup)
      force_no_setup=true
      shift
      ;;
    *)
      warn "Unknown option: $1"
      shift
      ;;
  esac
done

# ── Python ─────────────────────────────────────────────────────

PYTHON=""
for candidate in python3 python; do
  if command -v "$candidate" >/dev/null 2>&1; then
    PYTHON="$candidate"
    break
  fi
done
[[ -n "$PYTHON" ]] || fail "Python not found. Install Python 3 and try again."

PY_VERSION=$("$PYTHON" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
PY_MAJOR=$("$PYTHON" -c "import sys; print(sys.version_info.major)")
PY_MINOR=$("$PYTHON" -c "import sys; print(sys.version_info.minor)")
NEED_NEWER_PYTHON=0
if [[ "$PY_MAJOR" -lt 3 ]]; then
  fail "Python 3 is required (found ${PY_VERSION})"
fi
if [[ "$PY_MINOR" -lt 11 ]]; then
  NEED_NEWER_PYTHON=1
  warn "Python ${PY_VERSION} is older than ${MIN_PYTHON}. uv will install Python 3.12 for sandwalk."
else
  ok "Found Python ${PY_VERSION}"
fi

OS="$(uname -s)"
ARCH="$(uname -m)"
case "$OS" in
  Darwin) info "Detected macOS (${ARCH})" ;;
  Linux)  info "Detected Linux (${ARCH})" ;;
  *)      warn "Unsupported OS: $OS (${ARCH}) — the CLI install may still work" ;;
esac

# ── Resolve git ref from GitHub Releases ───────────────────────

resolve_ref() {
  if [[ -n "$explicit_ref" ]]; then
    printf '%s\n' "$explicit_ref"
    return
  fi

  if [[ -n "$requested_version" ]]; then
    local ver="${requested_version#v}"
    printf 'v%s\n' "$ver"
    return
  fi

  local json tag=""
  if [[ "$want_pre" == true ]]; then
    info "Resolving newest GitHub release (including pre-releases)…"
    json=$(curl -fsSL -H "Accept: application/vnd.github+json" "${API_BASE}/releases?per_page=20" 2>/dev/null || true)
    tag=$(printf '%s' "$json" | "$PYTHON" -c '
import json, sys
try:
    rows = json.load(sys.stdin)
except Exception:
    sys.exit(0)
for row in rows:
    if not isinstance(row, dict) or row.get("draft"):
        continue
    name = (row.get("tag_name") or "").strip()
    if name:
        print(name)
        break
' 2>/dev/null || true)
  else
    info "Resolving latest stable GitHub release…"
    json=$(curl -fsSL -H "Accept: application/vnd.github+json" "${API_BASE}/releases/latest" 2>/dev/null || true)
    tag=$(printf '%s' "$json" | "$PYTHON" -c '
import json, sys
try:
    row = json.load(sys.stdin)
except Exception:
    sys.exit(0)
if isinstance(row, dict) and not row.get("message"):
    print((row.get("tag_name") or "").strip())
' 2>/dev/null || true)
  fi

  if [[ -n "$tag" ]]; then
    printf '%s\n' "$tag"
    return
  fi

  warn "No GitHub release found — falling back to main"
  printf 'main\n'
}

REF="$(resolve_ref)"
ok "Installing sandwalk from git ref: ${REF}"

GIT_SPEC="git+${REPO_GIT}@${REF}#subdirectory=cli"
UV_SPEC="${PACKAGE} @ ${GIT_SPEC}"

# ── Install ────────────────────────────────────────────────────
# Prefer uv (isolated tool env, works on PEP 668 distros). Then pipx.
# If neither is present, bootstrap uv before falling back to pip --user.

ensure_uv_on_path() {
  command -v uv >/dev/null 2>&1 && return 0
  local dir
  for dir in "${HOME}/.local/bin" "${HOME}/.cargo/bin"; do
    if [[ -x "${dir}/uv" ]]; then
      export PATH="${dir}:${PATH}"
      return 0
    fi
  done
  return 1
}

bootstrap_uv() {
  info "uv not found — bootstrapping uv (https://astral.sh/uv)…"
  if ! curl -LsSf https://astral.sh/uv/install.sh | sh; then
    return 1
  fi
  ensure_uv_on_path || return 1
  ok "Bootstrapped uv ($(uv --version 2>/dev/null || echo ok))"
}

if ! ensure_uv_on_path && ! command -v pipx >/dev/null 2>&1; then
  bootstrap_uv || warn "Could not bootstrap uv — will try pip next"
fi

if ensure_uv_on_path; then
  info "Installing ${PACKAGE} via uv tool…"
  if [[ "$NEED_NEWER_PYTHON" == 1 ]]; then
    uv tool install --python 3.12 "$UV_SPEC" || uv tool install --force --python 3.12 "$UV_SPEC" \
      || fail "uv tool install failed"
  else
    uv tool install "$UV_SPEC" || uv tool install --force "$UV_SPEC" \
      || fail "uv tool install failed"
  fi
  ok "Installed with uv"
elif command -v pipx >/dev/null 2>&1; then
  info "Installing ${PACKAGE} via pipx…"
  pipx install "$GIT_SPEC" || pipx install --force "$GIT_SPEC" || fail "pipx install failed"
  ok "Installed with pipx"
else
  warn "uv/pipx not found — falling back to pip install --user"
  "$PYTHON" -m pip install --user --upgrade "$UV_SPEC" \
    || fail "pip install failed (on Debian/Ubuntu try: curl -LsSf https://astral.sh/uv/install.sh | sh)"
  ok "Installed with pip"
  USER_BIN=$("$PYTHON" -m site --user-base)/bin
  if ! printf '%s' "$PATH" | tr ':' '\n' | grep -qx "$USER_BIN"; then
    warn ""
    warn "Add this to your shell profile (~/.bashrc, ~/.zshrc, etc.):"
    warn "  export PATH=\"${USER_BIN}:\$PATH\""
    warn ""
  fi
fi

# ── PATH ───────────────────────────────────────────────────────

ensure_local_bin_on_path() {
  local marker="# Added by Sandwalk"
  local line='export PATH="$HOME/.local/bin:$PATH"'
  local profiles=()
  case "$OS" in
    Darwin) profiles=("${HOME}/.zprofile" "${HOME}/.zshrc") ;;
    Linux)  profiles=("${HOME}/.profile" "${HOME}/.bashrc") ;;
    *)      profiles=("${HOME}/.profile") ;;
  esac
  local profile
  for profile in "${profiles[@]}"; do
    if [[ -f "$profile" ]] && grep -q '\.local/bin' "$profile"; then
      continue
    fi
    printf '\n%s\n%s\n' "$marker" "$line" >> "$profile"
    ok "Added ~/.local/bin to ${profile#"${HOME}/"}"
  done
}

# ── Verify ─────────────────────────────────────────────────────

export PATH="${HOME}/.local/bin:${PATH}"
ensure_local_bin_on_path

if ! command -v sandwalk >/dev/null 2>&1; then
  warn "'sandwalk' not found on PATH. Restart your shell, then run: sandwalk --version"
  warn "Next: sandwalk setup"
  exit 0
fi

ok "sandwalk $(sandwalk --version 2>/dev/null || echo '(installed)')"

run_setup=false
if [[ "$force_setup" == true ]]; then
  run_setup=true
elif [[ "$force_no_setup" == true ]]; then
  run_setup=false
elif [[ -t 0 ]]; then
  run_setup=true
fi

if [[ "$run_setup" == true ]]; then
  info ""
  info "Running setup wizard…"
  info ""
  sandwalk setup
else
  printf "\n${MUTED}Next steps:${NC}\n"
  printf "  sandwalk setup      ${MUTED}# configure providers / models${NC}\n"
  printf "  sandwalk desktop    ${MUTED}# install the Mac app or Ubuntu .deb${NC}\n"
  printf "  sandwalk serve      ${MUTED}# start the agent API${NC}\n"
  printf "  sandwalk --help\n"
  printf "\n${MUTED}Docs: ${NC}https://sandwalk.sh\n\n"
fi
