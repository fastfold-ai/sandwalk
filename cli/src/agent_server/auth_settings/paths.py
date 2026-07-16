"""Cross-platform settings file location + session-cookie constants."""

from __future__ import annotations

import os
import sys
from pathlib import Path

SESSION_COOKIE = "sandwalk_session"
SESSION_MAX_AGE = 86400  # 24h
SESSION_REMEMBER_MAX_AGE = 2592000  # 30d
AUTH_EXEMPT_PATHS = frozenset(
    {
        "/v1/health",
        "/v1/auth/status",
        "/v1/auth/login",
        "/v1/auth/logout",
    }
)


def settings_dir() -> Path:
    override = (os.environ.get("SANDWALK_HOME") or "").strip()
    if override:
        return Path(override).expanduser().resolve()

    path_override = (os.environ.get("SANDWALK_SETTINGS_PATH") or "").strip()
    if path_override:
        return Path(path_override).expanduser().resolve().parent

    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "Sandwalk"
    if sys.platform == "win32":
        appdata = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
        return Path(appdata) / "Sandwalk"
    xdg = (os.environ.get("XDG_CONFIG_HOME") or "").strip()
    if xdg:
        return Path(xdg).expanduser() / "sandwalk"
    return Path.home() / ".config" / "sandwalk"


def settings_path() -> Path:
    path_override = (os.environ.get("SANDWALK_SETTINGS_PATH") or "").strip()
    if path_override:
        return Path(path_override).expanduser().resolve()
    return settings_dir() / "settings.json"
