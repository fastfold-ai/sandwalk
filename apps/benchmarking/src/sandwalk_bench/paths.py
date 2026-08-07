"""Package-root path helpers."""

from __future__ import annotations

from pathlib import Path

PKG_ROOT = Path(__file__).resolve().parents[2]
PACKS_DIR = PKG_ROOT / "packs"
FIXTURES_DIR = PKG_ROOT / "fixtures"
CACHE_DIR = PKG_ROOT / ".cache"
