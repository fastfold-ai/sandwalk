#!/usr/bin/env bash
# relaunch-macos-app.sh - stop, rebuild, reinstall and relaunch the Sandwalk macOS app
#
# Wraps package-macos-dmg.sh with a verified shutdown and a post-launch health check.
# The shutdown step matters: the agent's uvicorn worker can outlive its parent and keep
# holding both the API port and the SQLite lock, which makes the next start fail with
# "Another Sandwalk server already has this database open".
#
# Usage:
#   ./apps/packaging/relaunch-macos-app.sh
#
# Env:
#   STOP_ONLY=1      stop everything and exit (no build, no launch)
#   SKIP_BUILD=1      relaunch the installed app without rebuilding
#   PORT=8787         API port to free and probe
#   TIMEOUT=90        seconds to wait for the API to report healthy
#   CONFIG=, SKIP_TAURI=   forwarded to package-macos-dmg.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
APP="${HOME}/Applications/Sandwalk.app"
SUPPORT="${HOME}/Library/Application Support/Sandwalk"
DB="${HOME}/.sandwalk/agent-server.db"
PORT="${PORT:-8787}"
TIMEOUT="${TIMEOUT:-90}"

port_pids() { lsof -nP -tiTCP:"${PORT}" -sTCP:LISTEN 2>/dev/null || true; }
db_pids() { [[ -f "${DB}" ]] && lsof -t "${DB}" 2>/dev/null || true; }
helper_pid() { pgrep -f "Helpers/Sandwalk Server.app/Contents/MacOS/Sandwalk" 2>/dev/null | head -n 1 || true; }
# Packaged apps spawn ``python -m cli serve``; checkout installs use ``sandwalk serve``.
agent_pids() {
  pgrep -f "bin/sandwalk serve" 2>/dev/null || true
  pgrep -f "agent-runtime/.*/python.*/-m cli serve" 2>/dev/null || true
  pgrep -f "python.* -m cli serve" 2>/dev/null || true
}

# Stop the client, the helper, and the agent, then verify nothing still holds the
# API port or the database. Runs twice: once up front, and again right before launch
# because package-macos-dmg.sh's install step also kills the helper, which orphans
# any agent that a start-on-launch relaunch spawned during the build.
stop_all() {
  osascript -e 'quit app "Sandwalk"' 2>/dev/null || true
  osascript -e 'quit app "Sandwalk Server"' 2>/dev/null || true
  sleep 1
  pkill -x sandwalk-desktop 2>/dev/null || true
  pkill -x Sandwalk 2>/dev/null || true
  pkill -f "bin/sandwalk serve" 2>/dev/null || true
  pkill -f "python.* -m cli serve" 2>/dev/null || true

  # Give the agent a moment to shut down gracefully, then force what is left.
  for _ in $(seq 1 10); do
    [[ -z "$(port_pids)$(db_pids)" ]] && break
    sleep 0.5
  done

  local leftover
  leftover="$(port_pids)$(db_pids)"
  if [[ -n "${leftover}" ]]; then
    echo "    forcing orphans: $(echo ${leftover} | tr '\n' ' ')"
    pkill -9 -f "bin/sandwalk serve" 2>/dev/null || true
    pkill -9 -f "python.* -m cli serve" 2>/dev/null || true
    local pid
    for pid in $(port_pids) $(db_pids); do kill -9 "${pid}" 2>/dev/null || true; done
    sleep 1
  fi

  if [[ -n "$(port_pids)" ]]; then
    echo "error: port ${PORT} still held by: $(port_pids | tr '\n' ' ')"
    exit 1
  fi
  if [[ -n "$(db_pids)" ]]; then
    echo "error: database still locked by: $(db_pids | tr '\n' ' ')"
    exit 1
  fi

  # Stale control plane would point the client at a dead helper.
  rm -f "${SUPPORT}/control.json"
}

# --- 1. Stop ------------------------------------------------------------------
echo "==> Stopping Sandwalk..."
stop_all
echo "    stopped (port ${PORT} free, database unlocked)"

if [[ "${STOP_ONLY:-0}" == "1" ]]; then
  exit 0
fi

# --- 2. Build + install -------------------------------------------------------
if [[ "${SKIP_BUILD:-0}" == "1" ]]; then
  echo "==> Skipping build (SKIP_BUILD=1)"
  [[ -d "${APP}" ]] || { echo "error: ${APP} not installed; run without SKIP_BUILD"; exit 1; }
else
  INSTALL=1 "${SCRIPT_DIR}/package-macos-dmg.sh"
fi

# --- 3. Launch + verify -------------------------------------------------------
# The build takes long enough that a start-on-launch relaunch can slip in and get
# half-killed by the install step, so clear the field again before launching.
echo "==> Clearing pre-launch state..."
stop_all

# Truncate so the health check only judges this run, not earlier failures.
mkdir -p "${SUPPORT}/logs"
: > "${SUPPORT}/logs/server.log" 2>/dev/null || true

echo "==> Launching ${APP}..."
open "${APP}"

# Require the supervised chain, not just a healthy port: an orphaned agent left over
# from a previous run answers /api/health while no helper owns it.
healthy=0
for i in $(seq 1 "${TIMEOUT}"); do
  hp="$(helper_pid)"
  code="$(curl -s -m 2 -o /dev/null -w '%{http_code}' "http://127.0.0.1:${PORT}/v1/health" || true)"
  if [[ -n "${hp}" && "${code}" == "200" ]]; then
    orphan=0
    for pid in $(agent_pids); do
      [[ "$(ps -o ppid= -p "${pid}" 2>/dev/null | xargs)" == "1" ]] && orphan=1
    done
    if [[ "${orphan}" == "0" ]]; then
      echo "    helper ${hp} up, API healthy after ${i}s"
      healthy=1
      break
    fi
  fi
  sleep 1
done

echo "==> Process chain:"
pgrep -fl "Sandwalk.app/Contents/MacOS/sandwalk-desktop" || echo "    client NOT running"
pgrep -fl "Helpers/Sandwalk Server.app/Contents/MacOS/Sandwalk" || echo "    helper NOT running"
if ! pgrep -fl "bin/sandwalk serve" && ! pgrep -fl "python.* -m cli serve"; then
  echo "    agent NOT running"
fi

if [[ "${healthy}" != "1" ]]; then
  echo ""
  echo "error: supervised chain did not come up within ${TIMEOUT}s"
  echo "       (helper running + API 200 + no agent reparented to launchd)"
  echo "       tail -n 40 \"${SUPPORT}/logs/server.log\""
  exit 1
fi

echo ""
echo "OK: Sandwalk running - http://127.0.0.1:${PORT} (docs: /docs)"
