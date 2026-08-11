"""Package-root path helpers."""

from __future__ import annotations

import os
from pathlib import Path

PKG_ROOT = Path(__file__).resolve().parents[2]
PACKS_DIR = PKG_ROOT / "packs"
FIXTURES_DIR = PKG_ROOT / "fixtures"


def _default_cache_dir() -> Path:
    """Prefer a writable user cache; fall back to package-relative for checkouts."""
    env = (os.environ.get("SANDWALK_BENCH_CACHE") or "").strip()
    if env:
        return Path(env).expanduser()
    config = (os.environ.get("SANDWALK_CONFIG_DIR") or "").strip()
    if config:
        return Path(config).expanduser() / "bench" / ".cache"
    user = Path.home() / ".sandwalk" / "bench" / ".cache"
    # Always prefer the user cache so wheel installs (read-only site-packages)
    # and checkouts share the same download location.
    return user


CACHE_DIR = _default_cache_dir()
