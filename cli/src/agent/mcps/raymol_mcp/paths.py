"""Locate the RayMol app binary and MCP handoff file."""

from __future__ import annotations

import os
import shutil
from pathlib import Path

SETUP_URL = "https://raymol.io/"
DEFAULT_APP_BINARY = Path("/Applications/RayMol.app/Contents/MacOS/RayMol")
HANDOFF_PATH = (
    Path.home() / "Library" / "Application Support" / "RayMol" / "mcp.json"
)


def find_raymol_binary() -> Path | None:
    """Return the RayMol executable if installed (PATH or /Applications)."""
    which = shutil.which("RayMol")
    if which:
        path = Path(which)
        if path.is_file() and os.access(path, os.X_OK):
            return path
    if DEFAULT_APP_BINARY.is_file() and os.access(DEFAULT_APP_BINARY, os.X_OK):
        return DEFAULT_APP_BINARY
    return None


def launcher_path() -> Path:
    """Resolved bridge command path (falls back to the default app location)."""
    found = find_raymol_binary()
    return found if found is not None else DEFAULT_APP_BINARY


def launcher_ready() -> bool:
    path = find_raymol_binary()
    return path is not None and path.is_file()


def handoff_ready() -> bool:
    """True when RayMol has written mcp.json (MCP enabled in the app)."""
    if not HANDOFF_PATH.is_file():
        return False
    try:
        text = HANDOFF_PATH.read_text(encoding="utf-8")
    except OSError:
        return False
    return '"port"' in text and '"token"' in text
