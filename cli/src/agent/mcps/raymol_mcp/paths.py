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


def _mdfind(query: str) -> list[Path]:
    try:
        proc = subprocess.run(
            ["mdfind", query],
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


def _apps_from_mdfind() -> list[Path]:
    """Spotlight lookup by bundle id, then by app name.

    Spotlight does not index mounted disk images, so this misses a RayMol that is
    running straight from its DMG — see ``running_binaries``.
    """
    apps = _mdfind(f"kMDItemCFBundleIdentifier == '{_BUNDLE_ID}'")
    if apps:
        return apps
    return _mdfind("kMDItemFSName == 'RayMol.app'")


def running_binaries() -> list[Path]:
    """RayMol executables taken from the process table.

    The most reliable signal on a fresh Mac: it finds the app wherever it is
    actually running from, including a mounted DMG (which Spotlight never indexes)
    or any directory the user happens to keep it in.
    """
    try:
        proc = subprocess.run(
            ["ps", "-Axo", "comm="],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return []
    found: list[Path] = []
    seen: set[str] = set()
    for line in (proc.stdout or "").splitlines():
        text = line.strip()
        if not text or "raymol" not in text.lower():
            continue
        path = Path(text)
        if path.name.lower() != "raymol" and "RayMol.app/Contents/MacOS" not in text:
            continue
        if text in seen:
            continue
        seen.add(text)
        found.append(path)
    return found


def _apps_on_volumes() -> list[Path]:
    """RayMol.app on mounted volumes — e.g. opened straight from the DMG."""
    apps: list[Path] = []
    volumes = Path("/Volumes")
    if not volumes.is_dir():
        return apps
    try:
        entries = list(volumes.iterdir())
    except OSError:
        return apps
    for volume in entries:
        try:
            for item in volume.iterdir():
                if item.suffix == ".app" and "raymol" in item.name.lower():
                    apps.append(item)
        except OSError:
            # Unreadable / unmounting volume — skip.
            continue
    return apps


def _apps_from_homebrew() -> list[Path]:
    """Homebrew cask staging dirs, in case the /Applications link is missing."""
    apps: list[Path] = []
    for caskroom in (
        Path("/opt/homebrew/Caskroom"),
        Path("/usr/local/Caskroom"),
    ):
        cask = caskroom / "raymol"
        if not cask.is_dir():
            continue
        try:
            for version in cask.iterdir():
                for item in version.iterdir():
                    if item.suffix == ".app" and "raymol" in item.name.lower():
                        apps.append(item)
        except OSError:
            continue
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
    for app in _apps_from_homebrew():
        add(app)
    for app in _apps_on_volumes():
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

def on_removable_volume(path: Path) -> bool:
    """True when the path lives under /Volumes (e.g. still inside the DMG)."""
    try:
        return str(path.resolve(strict=False)).startswith("/Volumes/")
    except OSError:
        return str(path).startswith("/Volumes/")


def find_raymol_binary() -> Path | None:
    """Return the RayMol executable if installed.

    Order: config override, the running process, PATH, then candidate app bundles.
    Every source is validated against the filesystem, so a stale override or a
    Spotlight hit for a deleted app never wins.

    A binary under ``/Volumes`` (RayMol still running from its DMG) is used only
    as a last resort — it disappears on eject, so a permanent install always wins
    even when the removable copy is what is currently running.
    """
    removable: Path | None = None

    def consider(candidate: Path | None) -> Path | None:
        """Return a permanent match, stashing the first removable one."""
        nonlocal removable
        found = _usable(candidate)
        if found is None:
            return None
        if on_removable_volume(found):
            if removable is None:
                removable = found
            return None
        return found

    override = consider(_config_override())
    if override is not None:
        return override

    # A running RayMol covers non-standard locations Spotlight will not index.
    for binary in running_binaries():
        found = consider(binary)
        if found is not None:
            return found

    for name in ("RayMol", "raymol"):
        which = shutil.which(name)
        found = consider(Path(which) if which else None)
        if found is not None:
            return found

    for app in _candidate_apps():
        for binary in _binaries_in_app(app):
            found = consider(binary)
            if found is not None:
                return found

    # Never return the default path unless it exists — callers exec this, and a
    # missing path surfaces as a confusing ENOENT from the MCP probe.
    permanent = consider(DEFAULT_APP_BINARY)
    if permanent is not None:
        return permanent
    return removable


def launcher_path() -> Path:
    """Resolved bridge command path (falls back to the default app location)."""
    found = find_raymol_binary()
    return found if found is not None else DEFAULT_APP_BINARY


def bridge_command() -> str | None:
    """Executable path for ``RayMol --mcp-bridge``, or None when not on disk.

    Callers that spawn the bridge must use this rather than ``launcher_path``,
    which returns a display-only default when RayMol is missing.
    """
    found = find_raymol_binary()
    return str(found) if found is not None else None


def launcher_ready() -> bool:
    """True when Sandwalk can actually spawn the RayMol bridge.

    Requires the RayMol executable on disk. Sandwalk drives RayMol by spawning
    ``RayMol --mcp-bridge``, so the binary is mandatory — a handoff file alone is
    not enough. ``mcp.json`` outlives the app that wrote it (RayMol quit, was
    deleted, or its DMG was ejected), and treating that as ready only defers the
    failure to an ENOENT when the bridge is spawned.

    Kept in sync with ``ensure_launcher`` so Install and Enable agree.
    """
    return find_raymol_binary() is not None


def handoff_ready() -> bool:
    """True when RayMol has written mcp.json (MCP enabled in the app)."""
    if not HANDOFF_PATH.is_file():
        return False
    try:
        text = HANDOFF_PATH.read_text(encoding="utf-8")
    except OSError:
        return False
    return '"port"' in text and '"token"' in text
