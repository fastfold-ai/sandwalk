"""Upload local workspace/skills content into a sandbox."""

from __future__ import annotations

import logging
from collections.abc import Sequence
from pathlib import Path

from .paths import (
    SKILLS_REMOTE_ROOT,
    UPLOAD_BATCH_SIZE,
    WORKSPACE_REMOTE_ROOT,
    SupportsUploadDownload,
    chunked,
    iter_local_files,
    remote_workspace_path,
    should_skip_path,
)

logger = logging.getLogger(__name__)


def ensure_remote_directories(
    backend: SupportsUploadDownload,
    remote_paths: Sequence[str],
    *,
    timeout: int = 60,
) -> None:
    """Create parent directories for remote file paths (Modal upload often needs them)."""
    parents: set[str] = set()
    for remote in remote_paths:
        cleaned = str(remote).replace("\\", "/").strip()
        if not cleaned.startswith("/"):
            continue
        parent = str(Path(cleaned).parent)
        while parent and parent != "/" and parent not in parents:
            parents.add(parent)
            parent = str(Path(parent).parent)
    if not parents:
        return
    # Shortest first so parents exist before children.
    ordered = " ".join(f"'{p}'" for p in sorted(parents, key=lambda p: (p.count("/"), p)))
    try:
        backend.execute(f"mkdir -p {ordered}", timeout=timeout)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Remote mkdir failed: %s", exc)


def push_tree(
    backend: SupportsUploadDownload,
    local_root: str | Path,
    *,
    remote_root: str = WORKSPACE_REMOTE_ROOT,
) -> int:
    """Upload local workspace files into the sandbox. Returns file count."""
    root = Path(local_root).expanduser().resolve()
    files = iter_local_files(root)
    payload: list[tuple[str, bytes]] = []
    for path in files:
        rel = path.relative_to(root).as_posix()
        remote = remote_workspace_path(rel, remote_root=remote_root)
        try:
            payload.append((remote, path.read_bytes()))
        except OSError as exc:
            logger.warning("Skipping unreadable workspace file %s: %s", path, exc)
    if not payload:
        return 0
    ensure_remote_directories(backend, [path for path, _ in payload])
    uploaded = 0
    for batch in chunked(payload, UPLOAD_BATCH_SIZE):
        backend.upload_files(list(batch))
        uploaded += len(batch)
    return uploaded


def push_paths(
    backend: SupportsUploadDownload,
    local_root: str | Path,
    relative_paths: Sequence[str],
    *,
    remote_root: str = WORKSPACE_REMOTE_ROOT,
) -> int:
    """Upload specific relative paths from the local workspace."""
    root = Path(local_root).expanduser().resolve()
    payload: list[tuple[str, bytes]] = []
    for rel in relative_paths:
        cleaned = str(rel).replace("\\", "/").lstrip("/")
        if not cleaned or ".." in cleaned.split("/"):
            continue
        path = (root / cleaned).resolve()
        if not path.is_file() or not path.is_relative_to(root):
            continue
        if should_skip_path(path, root=root):
            continue
        payload.append(
            (remote_workspace_path(cleaned, remote_root=remote_root), path.read_bytes())
        )
    if not payload:
        return 0
    ensure_remote_directories(backend, [path for path, _ in payload])
    backend.upload_files(payload)
    return len(payload)


def seed_skills(
    backend: SupportsUploadDownload,
    skill_source_dirs: Sequence[str | Path],
    *,
    remote_root: str = SKILLS_REMOTE_ROOT,
) -> int:
    """Copy host skill trees into Modal ``/skills/``. Later dirs overwrite earlier names."""
    payload: list[tuple[str, bytes]] = []
    for source in skill_source_dirs:
        src = Path(source).expanduser().resolve()
        if not src.is_dir():
            continue
        for path in src.rglob("*"):
            if not path.is_file():
                continue
            if should_skip_path(path, root=src):
                continue
            rel = path.relative_to(src).as_posix()
            # Preserve skill folder name under /skills/<name>/...
            remote = f"{remote_root.rstrip('/')}/{rel}"
            try:
                payload.append((remote, path.read_bytes()))
            except OSError as exc:
                logger.warning("Skipping unreadable skill file %s: %s", path, exc)
    if not payload:
        return 0
    ensure_remote_directories(backend, [path for path, _ in payload])
    uploaded = 0
    for batch in chunked(payload, UPLOAD_BATCH_SIZE):
        backend.upload_files(list(batch))
        uploaded += len(batch)
    return uploaded
