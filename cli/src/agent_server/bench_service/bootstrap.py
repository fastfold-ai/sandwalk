"""Locate sandwalk-bench packs/fixtures and optionally import the package."""

from __future__ import annotations

import os
import sys
from pathlib import Path


def _bundled_root() -> Path | None:
    """Packs shipped inside the wheel (uv tool / pip install)."""
    candidate = Path(__file__).resolve().parent.parent / "bench_bundled"
    if (candidate / "packs").is_dir():
        return candidate
    return None


def bench_root() -> Path | None:
    """Return apps/benchmarking (or bundled) root when available.

    Order: ``SANDWALK_BENCH_ROOT`` → monorepo checkout → wheel-bundled copy.
    """
    env = (os.environ.get("SANDWALK_BENCH_ROOT") or "").strip()
    if env:
        p = Path(env).expanduser().resolve()
        if p.is_dir():
            return p
    # cli/src/agent_server/bench_service/bootstrap.py → parents[4] = repo root
    here = Path(__file__).resolve()
    for parent in [here.parents[i] for i in range(2, 7)]:
        candidate = parent / "apps" / "benchmarking"
        if (candidate / "packs").is_dir():
            return candidate
        if parent.name == "benchmarking" and (parent / "packs").is_dir():
            return parent
    return _bundled_root()


def bench_cache_root() -> Path:
    """Writable cache for downloaded suite datasets (any install layout)."""
    base = Path(
        os.environ.get("SANDWALK_CONFIG_DIR") or Path.home() / ".sandwalk"
    ).expanduser()
    root = base / "bench"
    (root / ".cache" / "mcq").mkdir(parents=True, exist_ok=True)
    return root


def ensure_sandwalk_bench_importable() -> bool:
    """Add sandwalk_bench to sys.path; return True if import works."""
    candidates: list[Path] = []
    root = bench_root()
    if root is not None:
        # Checkout: apps/benchmarking/src ; bundled: bench_bundled/python
        candidates.append(root / "src")
        candidates.append(root / "python")
    bundled = _bundled_root()
    if bundled is not None:
        candidates.append(bundled / "python")
    for src in candidates:
        if src.is_dir() and str(src) not in sys.path:
            sys.path.insert(0, str(src))
    try:
        import sandwalk_bench  # noqa: F401

        return True
    except ImportError:
        return False


def packs_dir() -> Path | None:
    root = bench_root()
    return (root / "packs") if root else None


def fixtures_dir() -> Path | None:
    root = bench_root()
    return (root / "fixtures") if root else None


def results_dir() -> Path:
    """Persisted bench results under the user config dir."""
    base = Path(
        os.environ.get("SANDWALK_CONFIG_DIR")
        or Path.home() / ".sandwalk"
    ).expanduser()
    d = base / "bench-runs"
    d.mkdir(parents=True, exist_ok=True)
    return d
