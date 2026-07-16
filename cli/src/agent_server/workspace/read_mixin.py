"""Path resolution + read-only workspace operations (list/read)."""

from __future__ import annotations

import base64
import hashlib
import mimetypes
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from agent_server.models import WorkspaceFile, WorkspaceFileContent
from agent_server.workspace.constants import MAX_FILE_SIZE, TEXT_SUFFIXES
from agent_server.workspace.errors import WorkspacePathError


class WorkspaceReadMixin:
    root: Path

    def resolve(self, relative_path: str, *, must_exist: bool = False) -> Path:
        value = str(relative_path or "").strip().replace("\\", "/")
        candidate = (self.root / value).resolve(strict=False)
        if not candidate.is_relative_to(self.root):
            raise WorkspacePathError("Path escapes the session workspace.")
        if must_exist and not candidate.exists():
            raise FileNotFoundError(value)
        return candidate

    def relative(self, path: Path) -> str:
        return path.relative_to(self.root).as_posix()

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
        iterator = directory.rglob("*") if recursive else directory.iterdir()
        output: list[WorkspaceFile] = []
        for path in iterator:
            rel = self.relative(path)
            if any(part in {".git", "__pycache__", ".venv"} for part in path.relative_to(self.root).parts):
                continue
            try:
                stat = path.stat()
            except OSError:
                continue
            output.append(
                WorkspaceFile(
                    path=rel,
                    name=path.name,
                    type="directory" if path.is_dir() else "file",
                    size=None if path.is_dir() else stat.st_size,
                    mtime=datetime.fromtimestamp(stat.st_mtime, UTC),
                )
            )
        return sorted(output, key=lambda item: (item.type != "directory", item.path.lower()))

    def read(self, relative_path: str) -> WorkspaceFileContent:
        path = self.resolve(relative_path, must_exist=True)
        if not path.is_file():
            raise IsADirectoryError(relative_path)
        size = path.stat().st_size
        if size > MAX_FILE_SIZE:
            raise WorkspacePathError(f"File exceeds the {MAX_FILE_SIZE // (1024 * 1024)}MB limit.")
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
            path=self.relative(path),
            content=content,
            encoding=encoding,
            mime_type=mime_type,
            version=self._version(data),
            size=len(data),
            mtime=self._mtime(path),
        )
