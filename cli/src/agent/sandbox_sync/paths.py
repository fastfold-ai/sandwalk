"""Path helpers and shared protocol/constants for sandbox sync."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any, Protocol

WORKSPACE_REMOTE_ROOT = "/workspace"
SKILLS_REMOTE_ROOT = "/skills"

_IGNORE_DIR_NAMES = frozenset(
    {".git", "__pycache__", ".venv", "node_modules", ".pytest_cache", ".mypy_cache"}
)
_IGNORE_FILE_NAMES = frozenset({".DS_Store", "Thumbs.db"})

# Cap single upload batches to keep Modal FS calls bounded.
UPLOAD_BATCH_SIZE = 40


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


def chunked(items: Sequence[Any], size: int) -> Iterable[Sequence[Any]]:
    for i in range(0, len(items), size):
        yield items[i : i + size]


def execute_output(result: Any) -> str:
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
