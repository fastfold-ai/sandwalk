"""Small formatting/sizing helpers for the dataset downloader."""

from pathlib import Path


def _format_size(num_bytes: int) -> str:
    """Render a byte count as a human-readable KB/MB/GB string."""
    size = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024 or unit == "TB":
            return f"{int(size)}{unit}" if unit == "B" else f"{size:.1f}{unit}"
        size /= 1024
    return f"{size:.1f}TB"


def _dataset_disk_size(path: Path, expected: set[str]) -> int:
    """Sum the on-disk bytes of a dataset's expected files that exist in ``path``."""
    if not path.exists():
        return 0
    total = 0
    for f in path.iterdir():
        if f.is_file() and (not expected or f.name in expected):
            try:
                total += f.stat().st_size
            except OSError:
                continue
    return total
