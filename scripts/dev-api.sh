#!/usr/bin/env bash
# Run the agent API from this checkout (not the copy bundled in Sandwalk.app).
#
#   scripts/dev-api.sh            # 127.0.0.1:8787, auth settings from the app's settings.json
#   PORT=8789 scripts/dev-api.sh
#
# Python does not hot-reload: re-run after editing cli/src. Ctrl+C stops it.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-8787}"

if [[ -z "${SANDWALK_SETTINGS_PATH:-}" ]]; then
  case "$(uname -s)" in
    Darwin) export SANDWALK_SETTINGS_PATH="$HOME/Library/Application Support/Sandwalk/settings.json" ;;
    *) export SANDWALK_SETTINGS_PATH="${XDG_CONFIG_HOME:-$HOME/.config}/sandwalk/settings.json" ;;
  esac
fi
export SANDWALK_DB_AUTO_HEAL="${SANDWALK_DB_AUTO_HEAL:-1}"

if lsof -nP -iTCP:"$PORT" -sTCP:LISTEN >/dev/null 2>&1; then
  echo "dev-api: something already listens on :$PORT" >&2
  lsof -nP -iTCP:"$PORT" -sTCP:LISTEN | awk 'NR>1 {print "  " $1 " pid=" $2}' >&2
  echo "dev-api: if that is the packaged menubar server, run scripts/stop-packaged-app.sh first" >&2
  exit 1
fi

cd "$ROOT/cli"
if [[ -x .venv/bin/sandwalk ]]; then
  exec .venv/bin/sandwalk serve --host "$HOST" --port "$PORT" "$@"
fi
exec uv run sandwalk serve --host "$HOST" --port "$PORT" "$@"
