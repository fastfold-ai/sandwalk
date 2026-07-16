"""Sanitize client-provided upload filenames (never trust raw UploadFile.filename)."""

from __future__ import annotations

import re
from pathlib import Path

# Keep extension; collapse everything else to safe [A-Za-z0-9._-].
_UNSAFE = re.compile(r"[^A-Za-z0-9._-]+")
_DOTS = re.compile(r"\.{2,}")
_MAX_STEM = 120


def sanitize_upload_filename(raw: str | None, *, fallback: str = "upload.bin") -> str:
    """Return a safe basename for workspace uploads.

    - Drops any directory components from the client name
    - Replaces spaces/unicode/special chars with ``_``
    - Rejects empty / ``.`` / ``..`` results
    """
    name = Path(str(raw or "").replace("\\", "/")).name.strip()
    if not name or name in {".", ".."}:
        return fallback

    suffix = Path(name).suffix
    stem = Path(name).stem
    # Preserve a trailing extension even if stem sanitizes empty.
    safe_stem = _UNSAFE.sub("_", stem).strip("._")
    safe_stem = _DOTS.sub(".", safe_stem)
    if not safe_stem:
        safe_stem = "upload"
    safe_stem = safe_stem[:_MAX_STEM].rstrip("._") or "upload"

    safe_suffix = ""
    if suffix:
        ext = _UNSAFE.sub("", suffix.lower())
        if ext.startswith(".") and len(ext) > 1:
            safe_suffix = ext

    return f"{safe_stem}{safe_suffix}" if safe_suffix else safe_stem


def unique_upload_relative_path(
    workspace_root: Path,
    relative_dir: str,
    filename: str,
) -> str:
    """Pick ``dir/name.ext``, or ``dir/name-1.ext`` if the target already exists."""
    rel_dir = Path(str(relative_dir or "uploads").replace("\\", "/"))
    # Disallow absolute / parent segments in the destination directory.
    parts = [part for part in rel_dir.parts if part not in {"", ".", ".."}]
    safe_dir = Path(*parts) if parts else Path("uploads")
    candidate_rel = (safe_dir / filename).as_posix()
    if not (workspace_root / candidate_rel).exists():
        return candidate_rel
    stem = Path(filename).stem
    suffix = Path(filename).suffix
    for index in range(1, 1000):
        alt_rel = (safe_dir / f"{stem}-{index}{suffix}").as_posix()
        if not (workspace_root / alt_rel).exists():
            return alt_rel
    return (safe_dir / f"{stem}-dup{suffix}").as_posix()
