#!/usr/bin/env bash
# Run the dashboard UI against a local API with hot reload.
#
#   scripts/dev-ui.sh            # Tauri desktop window + Vite on :1420 (default)
#   scripts/dev-ui.sh web        # browser SPA only (Vite on :1420, open the printed URL)
#
# The UI talks to SANDWALK_API_URL (default http://127.0.0.1:8787) — start
# scripts/dev-api.sh first. TS/React edits hot-reload; Rust edits rebuild the
# Tauri binary and relaunch the window automatically.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MODE="${1:-tauri}"
export SANDWALK_API_URL="${SANDWALK_API_URL:-http://127.0.0.1:8787}"
cd "$ROOT"
case "$MODE" in
  web)   exec pnpm --filter @sandwalk/agent-local-web dev --port 1420 --strictPort ;;
  tauri) exec pnpm --filter @sandwalk/agent-local-web tauri:dev ;;
  *) echo "usage: scripts/dev-ui.sh [tauri|web]" >&2; exit 2 ;;
esac
