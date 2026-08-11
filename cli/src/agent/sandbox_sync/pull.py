"""Download sandbox workspace content back to the local workspace."""

from __future__ import annotations

from pathlib import Path

from .paths import (
    UPLOAD_BATCH_SIZE,
    WORKSPACE_REMOTE_ROOT,
    SupportsUploadDownload,
    chunked,
    execute_output,
    local_rel_from_remote,
)


def list_remote_files(
    backend: SupportsUploadDownload,
    *,
    remote_root: str = WORKSPACE_REMOTE_ROOT,
) -> list[str]:
    """List files under remote_root via sandbox ``find``."""
    cmd = f'find {remote_root} -type f 2>/dev/null | head -n 5000'
    result = backend.execute(cmd, timeout=120)
    lines = [ln.strip() for ln in execute_output(result).splitlines() if ln.strip()]
    return [ln for ln in lines if ln.startswith(remote_root.rstrip("/"))]


def pull_tree(
    backend: SupportsUploadDownload,
    local_root: str | Path,
    *,
    remote_root: str = WORKSPACE_REMOTE_ROOT,
) -> int:
    """Download sandbox workspace files into the local workspace. Returns file count."""
    root = Path(local_root).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    remote_paths = list_remote_files(backend, remote_root=remote_root)
    if not remote_paths:
        return 0
    written = 0
    for batch in chunked(remote_paths, UPLOAD_BATCH_SIZE):
        responses = backend.download_files(list(batch))
        for item in responses or []:
            path = getattr(item, "path", None)
            content = getattr(item, "content", None)
            error = getattr(item, "error", None)
            if isinstance(item, dict):
                path = item.get("path", path)
                content = item.get("content", content)
                error = item.get("error", error)
            if error or path is None or content is None:
                continue
            rel = local_rel_from_remote(str(path), remote_root=remote_root)
            if rel is None or rel == "" or ".." in rel.split("/"):
                continue
            dest = (root / rel).resolve()
            if not dest.is_relative_to(root):
                continue
            dest.parent.mkdir(parents=True, exist_ok=True)
            data = content if isinstance(content, (bytes, bytearray)) else bytes(content)
            dest.write_bytes(data)
            written += 1
    return written
