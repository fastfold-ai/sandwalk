"""Bidirectional sync between a local session workspace and a Modal sandbox FS."""

from __future__ import annotations

import logging
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any, Protocol

logger = logging.getLogger(__name__)

WORKSPACE_REMOTE_ROOT = "/workspace"
SKILLS_REMOTE_ROOT = "/skills"

_IGNORE_DIR_NAMES = frozenset(
    {".git", "__pycache__", ".venv", "node_modules", ".pytest_cache", ".mypy_cache"}
)
_IGNORE_FILE_NAMES = frozenset({".DS_Store", "Thumbs.db"})

# Cap single upload batches to keep Modal FS calls bounded.
_UPLOAD_BATCH_SIZE = 40


class SupportsUploadDownload(Protocol):
    def upload_files(self, files: list[tuple[str, bytes]]) -> Any: ...

    def download_files(self, paths: list[str]) -> Any: ...

    def execute(self, command: str, *, timeout: int | None = None) -> Any: ...


def should_skip_path(path: Path, *, root: Path) -> bool:
    try:
        rel = path.relative_to(root)
    except ValueError:
        return True
    if any(part in _IGNORE_DIR_NAMES for part in rel.parts[:-1]):
        return True
    if path.name in _IGNORE_FILE_NAMES or path.name in _IGNORE_DIR_NAMES:
        return True
    return False


def iter_local_files(root: Path) -> list[Path]:
    root = root.expanduser().resolve()
    if not root.is_dir():
        return []
    files: list[Path] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if should_skip_path(path, root=root):
            continue
        files.append(path)
    return files


def remote_workspace_path(rel_posix: str, *, remote_root: str = WORKSPACE_REMOTE_ROOT) -> str:
    cleaned = rel_posix.replace("\\", "/").lstrip("/")
    if ".." in cleaned.split("/"):
        raise ValueError(f"Unsafe relative path: {rel_posix!r}")
    return f"{remote_root.rstrip('/')}/{cleaned}" if cleaned else remote_root.rstrip("/")


def local_rel_from_remote(
    remote_path: str, *, remote_root: str = WORKSPACE_REMOTE_ROOT
) -> str | None:
    prefix = remote_root.rstrip("/") + "/"
    if remote_path == remote_root.rstrip("/"):
        return ""
    if not remote_path.startswith(prefix):
        return None
    return remote_path[len(prefix) :]


def _chunked(items: Sequence[Any], size: int) -> Iterable[Sequence[Any]]:
    for i in range(0, len(items), size):
        yield items[i : i + size]


def _execute_output(result: Any) -> str:
    if result is None:
        return ""
    if isinstance(result, str):
        return result
    output = getattr(result, "output", None)
    if output is not None:
        return str(output)
    if isinstance(result, dict):
        return str(result.get("output") or "")
    return str(result)


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
    for batch in _chunked(payload, _UPLOAD_BATCH_SIZE):
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


def list_remote_files(
    backend: SupportsUploadDownload,
    *,
    remote_root: str = WORKSPACE_REMOTE_ROOT,
) -> list[str]:
    """List files under remote_root via sandbox ``find``."""
    cmd = f'find {remote_root} -type f 2>/dev/null | head -n 5000'
    result = backend.execute(cmd, timeout=120)
    lines = [ln.strip() for ln in _execute_output(result).splitlines() if ln.strip()]
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
    for batch in _chunked(remote_paths, _UPLOAD_BATCH_SIZE):
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
    for batch in _chunked(payload, _UPLOAD_BATCH_SIZE):
        backend.upload_files(list(batch))
        uploaded += len(batch)
    return uploaded
