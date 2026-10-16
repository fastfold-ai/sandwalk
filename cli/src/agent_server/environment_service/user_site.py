"""A writable package directory for runtimes that cannot be modified in place.

The Mac app ships CPython inside a signed, sealed bundle. uv marks that copy
``EXTERNALLY-MANAGED``, and writing into it would break the code-signing seal
and be wiped by the next update anyway. Catalog installs for such runtimes go
to a per-user directory that the server adds to ``sys.path`` at startup. The
built-in sandbox runs ``run_python`` in this same process, so anything placed
there is importable by the agent on the next call.

A normal venv (dev checkout, ``uv tool install``) keeps installing into itself.
"""

from __future__ import annotations

import importlib
import logging
import os
import site
import sys
import sysconfig
from pathlib import Path

logger = logging.getLogger("environment_service")

_ENV_OVERRIDE = "SANDWALK_USER_SITE"
_ENV_FORCE = "SANDWALK_FORCE_USER_SITE"


def runtime_is_sealed() -> bool:
    """True when packages must not be written into the running interpreter."""
    if (os.environ.get(_ENV_FORCE) or "").strip() in {"1", "true", "yes"}:
        return True
    try:
        paths = sysconfig.get_paths()
        stdlib = Path(paths["stdlib"])
        purelib = Path(paths["purelib"])
    except (KeyError, TypeError):
        return False
    # The marker belongs to the base install. A venv built on a uv-managed
    # CPython shares that stdlib but owns its own site-packages, so only honour
    # the marker when we are running the base interpreter itself (as the app does).
    in_venv = sys.prefix != sys.base_prefix
    if not in_venv and (stdlib / "EXTERNALLY-MANAGED").exists():
        return True
    # A read-only site-packages (e.g. inside an .app bundle) counts too.
    return purelib.is_dir() and not os.access(purelib, os.W_OK)


def user_site_dir() -> Path:
    """Where catalog packages live for a sealed runtime."""
    override = (os.environ.get(_ENV_OVERRIDE) or "").strip()
    if override:
        return Path(override).expanduser()
    from agent_server.auth_settings import settings_dir

    tag = f"py{sys.version_info.major}.{sys.version_info.minor}"
    return settings_dir() / "python-packages" / tag


def active_user_site() -> Path | None:
    """The user site directory in use, or None when the runtime is writable."""
    if not runtime_is_sealed():
        return None
    return user_site_dir()


def activate_user_site() -> Path | None:
    """Create the user site and put it on ``sys.path``. Idempotent."""
    target = active_user_site()
    if target is None:
        return None
    try:
        target.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        logger.warning("Could not create user site %s: %s", target, exc)
        return None
    resolved = str(target)
    if resolved not in sys.path:
        # addsitedir honours .pth files; appending keeps bundled core deps first.
        site.addsitedir(resolved)
    importlib.invalidate_caches()
    logger.info("User site active for sealed runtime: %s", resolved)
    return target


def refresh_imports() -> None:
    """Make freshly installed distributions visible to this process."""
    importlib.invalidate_caches()


__all__ = [
    "activate_user_site",
    "active_user_site",
    "refresh_imports",
    "runtime_is_sealed",
    "user_site_dir",
]
