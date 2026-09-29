#!/usr/bin/env bash
# Quit the installed Sandwalk.app and its menubar "Sandwalk Server" helper so
# the bundled API stops holding :8787 and the checkout API can take over.
set -euo pipefail
osascript -e 'tell application "Sandwalk" to quit' >/dev/null 2>&1 || true
sleep 1
pkill -f 'Sandwalk Server.app/Contents/MacOS/Sandwalk' 2>/dev/null || true
sleep 1
pkill -f 'agent-runtime/bin/python3.*-m cli serve' 2>/dev/null || true
sleep 1
if pgrep -fl 'Sandwalk' >/dev/null 2>&1; then
  echo "still running:" >&2
  pgrep -fl 'Sandwalk' >&2 || true
  exit 1
fi
echo "packaged Sandwalk stopped; :8787 is free"
