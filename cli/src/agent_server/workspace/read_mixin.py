"""Path resolution + read-only workspace operations (list/read)."""

from __future__ import annotations

import base64
import hashlib
import mimetypes
import os
import time
from collections import deque
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from agent_server.models import WorkspaceFile, WorkspaceFileContent
from agent_server.project_folder import PROJECT_FOLDER_LINK_NAME
from agent_server.workspace.constants import TEXT_SUFFIXES
from agent_server.workspace.errors import WorkspacePathError

_SKIP_DIR_NAMES = frozenset(
    {
        ".git",
        "__pycache__",
        ".venv",
        "venv",
        "node_modules",
        ".pnpm-store",
        ".cache",
        ".Trash",
        "Library",
        ".npm",
        ".cargo",
        ".rustup",
        "target",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".next",
        "dist",
        "build",
    }
)

# Bounds for the recursive Files listing. A session whose workspace is a
# home directory (imported CLI sessions often run from `~`) would otherwise
# walk hundreds of thousands of entries in a worker thread; that one stat
# loop held the GIL hard enough to stall every model run in the process.
# The Files panel is a browse surface, not an index — partial is fine.
_LIST_MAX_ENTRIES = 5_000
_LIST_MAX_DEPTH = 8
_LIST_TIME_BUDGET_S = 1.5


class WorkspaceReadMixin:
    root: Path

    def resolve(self, relative_path: str, *, must_exist: bool = False) -> Path:
        value = str(relative_path or "").strip().replace("\\", "/")
        while value.startswith("./"):
            value = value[2:]
        joined = self.root / value
        candidate = joined.resolve(strict=False)
        if not self._is_allowed_path(value, candidate):
            raise WorkspacePathError("Path escapes the session workspace.")
        if must_exist and not candidate.exists():
            raise FileNotFoundError(value)
        return candidate

    def _is_allowed_path(self, relative: str, candidate: Path) -> bool:
        """Allow workspace paths, plus the intentional ``project/`` mount."""
        try:
            if candidate == self.root or candidate.is_relative_to(self.root):
                return True
        except (OSError, ValueError):
            pass

        parts = Path(relative).parts
        if not parts or parts[0] != PROJECT_FOLDER_LINK_NAME:
            return False
        link = self.root / PROJECT_FOLDER_LINK_NAME
        if not link.exists():
            return False
        try:
            target = link.resolve()
        except OSError:
            return False
        try:
            return candidate == target or candidate.is_relative_to(target)
        except (OSError, ValueError):
            return False

    def relative(self, path: Path) -> str:
        try:
            return path.relative_to(self.root).as_posix()
        except ValueError:
            pass
        # Resolved paths under the project mount map back to project/...
        link = self.root / PROJECT_FOLDER_LINK_NAME
        if not link.exists():
            raise ValueError(f"{path} is not inside the workspace")
        try:
            target = link.resolve()
            rel = path.resolve(strict=False).relative_to(target).as_posix()
        except (OSError, ValueError) as exc:
            raise ValueError(f"{path} is not inside the workspace") from exc
        return PROJECT_FOLDER_LINK_NAME if rel == "." else f"{PROJECT_FOLDER_LINK_NAME}/{rel}"

    @staticmethod
    def _mtime(path: Path) -> datetime:
        return datetime.fromtimestamp(path.stat().st_mtime, UTC)

    @staticmethod
    def _version(data: bytes) -> str:
        return hashlib.sha256(data).hexdigest()

    def list(self, relative_path: str = "", *, recursive: bool = True) -> list[WorkspaceFile]:
        directory = self.resolve(relative_path, must_exist=True)
        if not directory.is_dir():
            raise NotADirectoryError(relative_path)
        output: list[WorkspaceFile] = []
        if not recursive:
            for path in directory.iterdir():
                item = self._file_entry(path)
                if item is not None:
                    output.append(item)
            return sorted(output, key=lambda item: (item.type != "directory", item.path.lower()))

        # Breadth-first so a truncated listing still shows the top of the
        # tree completely. One scandir stat per entry (no second Path.stat /
        # is_dir). Symlinked directories are followed only for the
        # workspace/project link; a home directory full of symlinks could
        # otherwise loop or escape.
        deadline = time.monotonic() + _LIST_TIME_BUDGET_S
        project_link = (self.root / PROJECT_FOLDER_LINK_NAME).resolve(strict=False)
        queue: deque[tuple[Path, int]] = deque([(directory, 0)])
        seen_dirs: set[tuple[int, int]] = set()
        while queue and len(output) < _LIST_MAX_ENTRIES:
            if time.monotonic() > deadline:
                break
            current, depth = queue.popleft()
            try:
                key = (current.stat().st_dev, current.stat().st_ino)
            except OSError:
                continue
            if key in seen_dirs:
                continue
            seen_dirs.add(key)
            try:
                with os.scandir(current) as entries:
                    children = sorted(entries, key=lambda e: e.name.lower())
            except OSError:
                continue
            for entry in children:
                if len(output) >= _LIST_MAX_ENTRIES:
                    break
                if entry.name in _SKIP_DIR_NAMES:
                    continue
                item = self._dir_entry(entry)
                if item is None:
                    continue
                output.append(item)
                if item.type != "directory" or depth + 1 > _LIST_MAX_DEPTH:
                    continue
                if entry.is_symlink():
                    try:
                        if Path(entry.path).resolve(strict=False) != project_link:
                            continue
                    except OSError:
                        continue
                queue.append((Path(entry.path), depth + 1))
        return sorted(output, key=lambda item: (item.type != "directory", item.path.lower()))

    def _dir_entry(self, entry: os.DirEntry[str]) -> WorkspaceFile | None:
        path = Path(entry.path)
        try:
            rel = self.relative(path)
        except ValueError:
            return None
        if any(part in _SKIP_DIR_NAMES for part in Path(rel).parts):
            return None
        try:
            is_dir = entry.is_dir(follow_symlinks=True)
            stat = entry.stat(follow_symlinks=True)
        except OSError:
            return None
        return WorkspaceFile(
            path=rel,
            name=entry.name,
            type="directory" if is_dir else "file",
            size=None if is_dir else stat.st_size,
            mtime=datetime.fromtimestamp(stat.st_mtime, UTC),
        )

    def _file_entry(self, path: Path) -> WorkspaceFile | None:
        try:
            rel = self.relative(path)
        except ValueError:
            return None
        if any(part in _SKIP_DIR_NAMES for part in Path(rel).parts):
            return None
        try:
            stat = path.stat()
        except OSError:
            return None
        is_dir = path.is_dir()
        return WorkspaceFile(
            path=rel,
            name=path.name,
            type="directory" if is_dir else "file",
            size=None if is_dir else stat.st_size,
            mtime=datetime.fromtimestamp(stat.st_mtime, UTC),
        )

    def read(self, relative_path: str) -> WorkspaceFileContent:
        path = self.resolve(relative_path, must_exist=True)
        if not path.is_file():
            raise IsADirectoryError(relative_path)
        data = path.read_bytes()
        mime_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        is_text = mime_type.startswith("text/") or path.suffix.lower() in TEXT_SUFFIXES
        encoding: Literal["text", "base64"]
        if is_text:
            try:
                content = data.decode("utf-8")
                encoding = "text"
            except UnicodeDecodeError:
                content = base64.b64encode(data).decode("ascii")
                encoding = "base64"
        else:
            content = base64.b64encode(data).decode("ascii")
            encoding = "base64"
        return WorkspaceFileContent(
            path=relative_path.strip().replace("\\", "/") or self.relative(path),
            content=content,
            encoding=encoding,
            mime_type=mime_type,
            version=self._version(data),
            size=len(data),
            mtime=self._mtime(path),
        )
