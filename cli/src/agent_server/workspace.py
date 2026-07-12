"""Project-scoped local filesystem operations for web sessions."""

from __future__ import annotations

import base64
import hashlib
import mimetypes
import os
import shutil
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from agent_server.models import WorkspaceFile, WorkspaceFileContent

MAX_FILE_SIZE = 40 * 1024 * 1024
TEXT_SUFFIXES = {
    ".cif",
    ".css",
    ".csv",
    ".html",
    ".htm",
    ".js",
    ".json",
    ".jsx",
    ".md",
    ".mmcif",
    ".pdb",
    ".py",
    ".sdf",
    ".svg",
    ".ts",
    ".tsv",
    ".tsx",
    ".txt",
    ".xml",
    ".yaml",
    ".yml",
}


class WorkspacePathError(ValueError):
    pass


class WorkspaceConflictError(RuntimeError):
    def __init__(self, current: WorkspaceFileContent) -> None:
        super().__init__("Workspace file changed since it was loaded.")
        self.current = current


class WorkspaceService:
    def __init__(self, root: Path) -> None:
        self.root = root.expanduser().resolve()
        if not self.root.is_dir():
            raise WorkspacePathError(f"Workspace directory does not exist: {self.root}")

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

    def write(
        self,
        relative_path: str,
        *,
        content: str,
        encoding: str = "text",
        base_version: str | None = None,
    ) -> WorkspaceFileContent:
        path = self.resolve(relative_path)
        if path.exists() and path.is_dir():
            raise IsADirectoryError(relative_path)
        if base_version is not None and path.exists():
            current = self.read(relative_path)
            if current.version != base_version:
                raise WorkspaceConflictError(current)
        data = (
            base64.b64decode(content, validate=True)
            if encoding == "base64"
            else content.encode("utf-8")
        )
        if len(data) > MAX_FILE_SIZE:
            raise WorkspacePathError(f"File exceeds the {MAX_FILE_SIZE // (1024 * 1024)}MB limit.")
        path.parent.mkdir(parents=True, exist_ok=True)
        file_descriptor, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
        try:
            with os.fdopen(file_descriptor, "wb") as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
            Path(temp_name).replace(path)
        finally:
            Path(temp_name).unlink(missing_ok=True)
        return self.read(self.relative(path))

    def upload(self, relative_path: str, data: bytes) -> WorkspaceFileContent:
        if len(data) > MAX_FILE_SIZE:
            raise WorkspacePathError(f"File exceeds the {MAX_FILE_SIZE // (1024 * 1024)}MB limit.")
        return self.write(
            relative_path,
            content=base64.b64encode(data).decode("ascii"),
            encoding="base64",
        )

    def create_folder(self, relative_path: str) -> str:
        path = self.resolve(relative_path)
        path.mkdir(parents=True, exist_ok=True)
        return self.relative(path)

    def move(self, source_path: str, target_path: str) -> str:
        source = self.resolve(source_path, must_exist=True)
        target = self.resolve(target_path)
        if target.exists():
            raise FileExistsError(target_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(source), str(target))
        return self.relative(target)

    def delete(self, relative_path: str, *, recursive: bool = False) -> None:
        path = self.resolve(relative_path, must_exist=True)
        if path == self.root:
            raise WorkspacePathError("Cannot delete the workspace root.")
        if path.is_dir():
            if not recursive:
                path.rmdir()
            else:
                shutil.rmtree(path)
        else:
            path.unlink()
