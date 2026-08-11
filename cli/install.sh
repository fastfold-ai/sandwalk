#!/usr/bin/env bash
# Sandwalk CLI installer (OpenCode-style one-liner)
#
#   curl -fsSL https://sandwalk.sh/install | bash
#   curl -fsSL https://sandwalk.sh/install | bash -s -- --pre
#   curl -fsSL https://sandwalk.sh/install | bash -s -- --version 0.0.1-rc.1
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

info()  { printf "${CYAN}%s${NC}\n" "$*"; }
ok()    { printf "${GREEN}%s${NC}\n" "$*"; }
warn()  { printf "${YELLOW}%s${NC}\n" "$*" >&2; }
fail()  { printf "${RED}Error: %s${NC}\n" "$*" >&2; exit 1; }

usage() {
  cat <<EOF
Sandwalk CLI installer

Usage:
  curl -fsSL https://sandwalk.sh/install | bash
  curl -fsSL https://sandwalk.sh/install | bash -s -- [options]

Options:
  -h, --help              Show this help
  -v, --version <ver>     Install a specific release tag (e.g. 0.0.1 or v0.0.1-rc.1)
      --ref <ref>         Git ref (branch / tag / sha); skips release lookup
      --pre               Use the newest GitHub release, including pre-releases
      --setup             Run interactive sandwalk setup after install
      --no-setup          Skip setup (default when stdin is not a TTY)

Installs the Python CLI from GitHub (cli/ subdirectory) via uv, pipx, or pip.
Default: latest stable GitHub Release tag. Falls back to main if no releases exist.

While the repo is private, GitHub auth is required (gh auth / SSH / token).
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
      [[ -n "${2:-}" ]] || fail "--version requires a value (e.g. 0.0.1-rc.1)"
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
[[ -n "$PYTHON" ]] || fail "Python not found. Install Python ${MIN_PYTHON}+ and try again."

PY_VERSION=$("$PYTHON" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
PY_MAJOR=$("$PYTHON" -c "import sys; print(sys.version_info.major)")
PY_MINOR=$("$PYTHON" -c "import sys; print(sys.version_info.minor)")
if [[ "$PY_MAJOR" -lt 3 ]] || { [[ "$PY_MAJOR" -eq 3 ]] && [[ "$PY_MINOR" -lt 11 ]]; }; then
  fail "Python ${MIN_PYTHON}+ required (found ${PY_VERSION})"
fi
ok "Found Python ${PY_VERSION}"

OS="$(uname -s)"
case "$OS" in
  Darwin) info "Detected macOS" ;;
  Linux)  info "Detected Linux" ;;
  *)      warn "Unsupported OS: $OS — installation may still work" ;;
esac

# ── Resolve git ref from GitHub Releases ───────────────────────

gh_api() {
  local url="$1"
  if command -v gh >/dev/null 2>&1 && gh auth status >/dev/null 2>&1; then
    gh api "$url" 2>/dev/null || true
  else
    local args=(-fsSL -H "Accept: application/vnd.github+json" -H "X-GitHub-Api-Version: 2022-11-28")
    if [[ -n "${GITHUB_TOKEN:-}" ]]; then
      args+=(-H "Authorization: Bearer ${GITHUB_TOKEN}")
    elif [[ -n "${GH_TOKEN:-}" ]]; then
      args+=(-H "Authorization: Bearer ${GH_TOKEN}")
    fi
    curl "${args[@]}" "$url" 2>/dev/null || true
  fi
}

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
    json=$(gh_api "${API_BASE}/releases?per_page=20")
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
    json=$(gh_api "${API_BASE}/releases/latest")
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

install_failed_hint() {
  warn ""
  warn "Install failed. If the repo is private, authenticate GitHub first:"
  warn "  gh auth login"
  warn "  # or: export GITHUB_TOKEN=…"
  warn ""
}

if command -v uv >/dev/null 2>&1; then
  info "Installing ${PACKAGE} via uv tool…"
  if ! uv tool install "$UV_SPEC" && ! uv tool install --force "$UV_SPEC"; then
    install_failed_hint
    fail "uv tool install failed"
  fi
  ok "Installed with uv"
elif command -v pipx >/dev/null 2>&1; then
  info "Installing ${PACKAGE} via pipx…"
  if ! pipx install "$GIT_SPEC" && ! pipx install --force "$GIT_SPEC"; then
    install_failed_hint
    fail "pipx install failed"
  fi
  ok "Installed with pipx"
else
  warn "uv/pipx not found — falling back to pip install --user"
  if ! "$PYTHON" -m pip install --user --upgrade "$UV_SPEC"; then
    install_failed_hint
    fail "pip install failed"
  fi
  ok "Installed with pip"
  USER_BIN=$("$PYTHON" -m site --user-base)/bin
  if ! printf '%s' "$PATH" | tr ':' '\n' | grep -qx "$USER_BIN"; then
    warn ""
    warn "Add this to your shell profile (~/.bashrc, ~/.zshrc, etc.):"
    warn "  export PATH=\"${USER_BIN}:\$PATH\""
    warn ""
  fi
fi

# ── Verify ─────────────────────────────────────────────────────

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
  printf "  sandwalk setup     ${MUTED}# configure providers / models${NC}\n"
  printf "  sandwalk serve     ${MUTED}# start the agent API${NC}\n"
  printf "  sandwalk --help\n"
  printf "\n${MUTED}Docs: ${NC}https://sandwalk.sh\n\n"
fi
