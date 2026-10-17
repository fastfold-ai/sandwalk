#!/bin/sh
set -eu
chmod 755 /usr/lib/sandwalk/sandwalk-serve /usr/bin/sandwalk 2>/dev/null || true
if command -v systemctl >/dev/null 2>&1; then
  systemctl daemon-reload || true
fi
