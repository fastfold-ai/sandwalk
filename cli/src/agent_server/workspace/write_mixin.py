"""Mutating workspace operations (write/upload/create/move/delete)."""

from __future__ import annotations

import base64
import os
import shutil
import tempfile
from pathlib import Path

from agent_server.models import WorkspaceFileContent
from agent_server.workspace.constants import MAX_FILE_SIZE
from agent_server.workspace.errors import WorkspaceConflictError, WorkspacePathError


class WorkspaceWriteMixin:
    root: Path

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
