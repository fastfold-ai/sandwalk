#!/usr/bin/env bash
# Local equivalent of the required CI gate ("Agent CLI & Server" + "Local Web UI").
#
#   scripts/verify.sh            # everything (~2 min)
#   scripts/verify.sh web        # typecheck + lint + build + vitest coverage gate
#   scripts/verify.sh cli        # ruff + mypy + pytest (unit + functional, xdist)
#   scripts/verify.sh e2e        # Playwright grid/terminal specs (needs API on :8787)
#
# Exits non-zero on the first failing step so agents can stop and fix.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TARGET="${1:-all}"
step() { printf '\n\033[1m==> %s\033[0m\n' "$*"; }

run_web() {
  cd "$ROOT"
  step "web: typecheck (app + e2e)";  pnpm --filter @sandwalk/agent-local-web typecheck
  step "web: lint";                    pnpm --filter @sandwalk/agent-local-web lint:check
  step "web: build";                   pnpm --filter @sandwalk/agent-local-web build
  step "web: vitest + coverage gate";  pnpm --filter @sandwalk/agent-local-web test:coverage
}

run_cli() {
  cd "$ROOT/cli"
  local py=".venv/bin/python"
  [[ -x "$py" ]] || { echo "cli/.venv missing — run: cd cli && uv sync --extra dev" >&2; exit 1; }
  step "cli: ruff";   "$ROOT/cli/.venv/bin/ruff" check src   # CI lints src only
  step "cli: mypy";   "$ROOT/cli/.venv/bin/mypy"
  step "cli: pytest"; "$py" -m pytest tests/ -q --ignore=tests/integration_cli -n auto --dist worksteal -p no:cacheprovider
}

run_e2e() {
  cd "$ROOT/apps/local-web"
  if ! curl -fsS "${SANDWALK_API_URL:-http://127.0.0.1:8787}/v1/health" >/dev/null 2>&1; then
    echo "e2e: no API on ${SANDWALK_API_URL:-http://127.0.0.1:8787} — start scripts/dev-api.sh" >&2
    exit 1
  fi
  step "e2e: playwright (functional)"; pnpm e2e
}

case "$TARGET" in
  all) run_web; run_cli ;;
  web) run_web ;;
  cli) run_cli ;;
  e2e) run_e2e ;;
  *) echo "usage: scripts/verify.sh [all|web|cli|e2e]" >&2; exit 2 ;;
esac
printf '\n\033[32mverify %s: OK\033[0m\n' "$TARGET"
