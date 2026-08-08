"""Locate the RayMol app binary and MCP handoff file."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

SETUP_URL = "https://raymol.io/"
DEFAULT_APP_BINARY = Path("/Applications/RayMol.app/Contents/MacOS/RayMol")
HANDOFF_PATH = (
    Path.home() / "Library" / "Application Support" / "RayMol" / "mcp.json"
)
_BUNDLE_ID = "io.raymol.RayMol"


def _usable(path: Path | None) -> Path | None:
    """Return ``path`` when it looks like a RayMol executable."""
    if path is None:
        return None
    try:
        resolved = path.expanduser().resolve(strict=False)
    except OSError:
        resolved = path.expanduser()
    if not resolved.is_file():
        return None
    # Prefer executable, but accept a present Mach-O/script — some sandboxed
    # callers see the file while os.access(X_OK) spuriously fails.
    if os.access(resolved, os.X_OK) or resolved.stat().st_mode & 0o111:
        return resolved
    if resolved.name.lower() in {"raymol", "pymol"}:
        return resolved
    return None


def _binaries_in_app(app: Path) -> list[Path]:
    mac_os = app / "Contents" / "MacOS"
    if not mac_os.is_dir():
        return []
    preferred: list[Path] = []
    other: list[Path] = []
    try:
        entries = list(mac_os.iterdir())
    except OSError:
        return []
    for item in entries:
        if not item.is_file():
            continue
        name = item.name.lower()
        if name == "raymol":
            preferred.append(item)
        elif "raymol" in name or name == "pymol":
            other.append(item)
    return preferred + other


def _apps_from_mdfind() -> list[Path]:
    try:
        proc = subprocess.run(
            [
                "mdfind",
                f"kMDItemCFBundleIdentifier == '{_BUNDLE_ID}'",
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return []
    apps: list[Path] = []
    for line in (proc.stdout or "").splitlines():
        text = line.strip()
        if not text:
            continue
        path = Path(text)
        if path.suffix == ".app" and path.is_dir():
            apps.append(path)
    return apps


def _candidate_apps() -> list[Path]:
    apps: list[Path] = []
    seen: set[str] = set()

    def add(app: Path) -> None:
        try:
            key = str(app.expanduser().resolve(strict=False))
        except OSError:
            key = str(app)
        if key in seen:
            return
        seen.add(key)
        apps.append(app)

    add(Path("/Applications/RayMol.app"))
    add(Path.home() / "Applications" / "RayMol.app")
    for app in _apps_from_mdfind():
        add(app)
    for root in (Path("/Applications"), Path.home() / "Applications"):
        if not root.is_dir():
            continue
        try:
            for item in root.iterdir():
                if item.suffix == ".app" and "raymol" in item.name.lower():
                    add(item)
        except OSError:
            continue
    return apps


def _config_override() -> Path | None:
    try:
        from agent.config import Config

        raw = str(Config.load().get("mcp.raymol_binary") or "").strip()
    except Exception:  # noqa: BLE001 — discovery must stay best-effort
        return None
    if not raw:
        return None
    return _usable(Path(raw))


def find_raymol_binary() -> Path | None:
    """Return the RayMol executable if installed (config, PATH, Applications)."""
    override = _config_override()
    if override is not None:
        return override

    for name in ("RayMol", "raymol"):
        which = shutil.which(name)
        found = _usable(Path(which) if which else None)
        if found is not None:
            return found

    for app in _candidate_apps():
        for binary in _binaries_in_app(app):
            found = _usable(binary)
            if found is not None:
                return found

    return _usable(DEFAULT_APP_BINARY)


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
