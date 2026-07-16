"""Best-effort on-disk size measurement for files and directory trees."""

from __future__ import annotations

import subprocess
from pathlib import Path


def _path_size_bytes(path: Path) -> int:
    """Return total bytes for a file or directory. Missing paths count as 0."""
    if not path.exists():
        return 0
    if path.is_file() or path.is_symlink():
        try:
            return path.stat().st_size
        except OSError:
            return 0
    # Prefer `du` — much faster than walking multi‑GB dataset trees.
    try:
        result = subprocess.run(
            ["du", "-sk", str(path)],
            check=False,
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode == 0 and result.stdout.strip():
            kib = int(result.stdout.split()[0])
            return max(0, kib * 1024)
    except (OSError, ValueError, subprocess.TimeoutExpired):
        pass

    total = 0
    try:
        for child in path.rglob("*"):
            try:
                if child.is_file() and not child.is_symlink():
                    total += child.stat().st_size
            except OSError:
                continue
    except OSError:
        return total
    return total
