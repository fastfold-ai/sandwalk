"""Upgrade-flavor resolution and PyPI version checks (cached, non-blocking)."""

import json
import time
import urllib.error
import urllib.request

from _version import __version__
from cli.constants import (
    _SEMVER_TRIPLET_PATTERN,
    _UPGRADE_CACHE_MAX_AGE_S,
    _UPGRADE_CACHE_PATH,
    PYPI_PROJECT_JSON_URL,
    UV_INSTALL_FLAVORS,
    UV_UPGRADE_PYTHON_VERSION,
)


def _normalize_upgrade_flavor(value: object) -> str | None:
    normalized = str(value or "").strip().lower()
    return normalized if normalized in UV_INSTALL_FLAVORS else None


def _default_upgrade_flavor() -> str:
    import os

    return "win_build" if os.name == "nt" else "all"


def resolve_upgrade_flavor(cfg=None, persist: bool = True) -> str:
    """Resolve uv install flavor from config, with OS fallback."""
    if cfg is None:
        from agent.config import Config
        cfg = Config.load()

    configured = _normalize_upgrade_flavor(cfg.get("install.uv_flavor"))
    if configured:
        return configured

    fallback = _default_upgrade_flavor()
    if persist:
        try:
            cfg.set("install.uv_flavor", fallback)
            cfg.save()
        except Exception:
            # Upgrade flow should still continue even if config write fails.
            pass
    return fallback


def build_upgrade_command(flavor: str) -> list[str]:
    normalized = _normalize_upgrade_flavor(flavor) or _default_upgrade_flavor()
    package_ref = f"sandwalk[{normalized}]"
    return ["uv", "tool", "install", package_ref, "--python", UV_UPGRADE_PYTHON_VERSION, "--upgrade"]


def _parse_semver_triplet(version: str) -> tuple[int, int, int] | None:
    match = _SEMVER_TRIPLET_PATTERN.match(str(version or "").strip())
    if not match:
        return None
    return tuple(int(part) for part in match.groups())


def is_newer_version(latest: str, current: str) -> bool:
    latest_triplet = _parse_semver_triplet(latest)
    current_triplet = _parse_semver_triplet(current)
    if not latest_triplet or not current_triplet:
        return False
    return latest_triplet > current_triplet


def fetch_pypi_latest_version(timeout_s: float = 2.5) -> str | None:
    req = urllib.request.Request(
        url=PYPI_PROJECT_JSON_URL,
        headers={"Accept": "application/json"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            text = resp.read().decode("utf-8", errors="replace")
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError):
        return None

    try:
        payload = json.loads(text) if text else {}
    except Exception:
        return None

    if not isinstance(payload, dict):
        return None
    info = payload.get("info")
    if not isinstance(info, dict):
        return None
    version = str(info.get("version") or "").strip()
    return version or None


def get_upgrade_available_version(current_version: str = __version__) -> str | None:
    latest = fetch_pypi_latest_version()
    if not latest:
        return None
    return latest if is_newer_version(latest, current_version) else None


def _get_cached_upgrade_available_version(current_version: str = __version__) -> str | None:
    """Return cached upgrade notice if fresh; never performs network I/O."""
    try:
        if not _UPGRADE_CACHE_PATH.exists():
            return None
        payload = json.loads(_UPGRADE_CACHE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(payload, dict):
        return None
    checked_at = float(payload.get("checked_at") or 0)
    if checked_at <= 0 or (time.time() - checked_at) > _UPGRADE_CACHE_MAX_AGE_S:
        return None
    latest = str(payload.get("latest") or "").strip()
    if not latest:
        return None
    return latest if is_newer_version(latest, current_version) else None


def _write_upgrade_cache(latest: str | None) -> None:
    """Persist latest seen PyPI version for non-blocking future boots."""
    try:
        _UPGRADE_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        _UPGRADE_CACHE_PATH.write_text(
            json.dumps(
                {
                    "latest": str(latest or "").strip(),
                    "checked_at": time.time(),
                }
            ),
            encoding="utf-8",
        )
    except Exception:
        pass


def _start_upgrade_check_refresh() -> None:
    """Refresh cached PyPI latest version in a daemon thread."""
    import threading

    def _worker():
        latest = fetch_pypi_latest_version()
        _write_upgrade_cache(latest)

    try:
        threading.Thread(target=_worker, daemon=True).start()
    except Exception:
        pass
