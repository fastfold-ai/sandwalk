"""Locate sandwalk-bench packs/fixtures and optionally import the package."""

from __future__ import annotations

import os
import sys
from pathlib import Path


def bench_root() -> Path | None:
    """Return apps/benchmarking root when available."""
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
    return None


def ensure_sandwalk_bench_importable() -> bool:
    """Add apps/benchmarking/src to sys.path; return True if import works."""
    root = bench_root()
    if root is None:
        return False
    src = root / "src"
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
