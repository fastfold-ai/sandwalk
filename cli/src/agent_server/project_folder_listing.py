"""List / read / mutate files from a project's linked folder (not Library blobs)."""

from __future__ import annotations

import base64
import hashlib
import mimetypes
import os
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from agent_server.library.kind import library_kind_for_name
from agent_server.models import (
    ProjectFolderFile,
    ProjectFolderListing,
    UseLibraryInChatResponse,
    WorkspaceFileContent,
)
from agent_server.project_folder import PROJECT_FOLDER_LINK_NAME
from agent_server.workspace.constants import TEXT_SUFFIXES
from agent_server.workspace.filenames import sanitize_upload_filename

_SKIP_DIR_NAMES = frozenset(
    {
        ".git",
        "__pycache__",
        ".venv",
        "node_modules",
        ".sandwalk",
        "dist",
        "build",
        ".next",
        ".turbo",
        "target",
    }
)
_MAX_FILES = 200
_MAX_READ_BYTES = 8 * 1024 * 1024
_SAFE_NAME = re.compile(r"^[^/\\]+$")


def _resolve_file(folder_path: str, relative_path: str) -> tuple[Path, Path, str]:
    """Return (root, absolute file path, normalized relative path)."""
    root = Path(folder_path).expanduser().resolve()
    if not root.is_dir():
        raise ValueError(f"Project folder is not a directory: {root}")

    value = str(relative_path or "").strip().replace("\\", "/")
    while value.startswith("./"):
        value = value[2:]
    if not value or value.startswith("/") or ".." in Path(value).parts:
        raise ValueError("Invalid project folder path.")

    candidate = (root / value).resolve(strict=False)
    try:
        if candidate != root and not candidate.is_relative_to(root):
            raise ValueError("Path escapes the project folder.")
    except (OSError, ValueError) as exc:
        raise ValueError("Path escapes the project folder.") from exc
    if not candidate.is_file():
        raise FileNotFoundError(value)
    return root, candidate, value


def _entry_for(root: Path, path: Path) -> ProjectFolderFile:
    rel = path.relative_to(root).as_posix()
    stat = path.stat()
    return ProjectFolderFile(
        path=rel,
        name=path.name,
        kind=library_kind_for_name(path.name),
        size=stat.st_size,
        mtime=datetime.fromtimestamp(stat.st_mtime, UTC),
    )


def list_project_folder_files(folder_path: str) -> ProjectFolderListing:
    root = Path(folder_path).expanduser().resolve()
    if not root.is_dir():
        raise ValueError(f"Project folder is not a directory: {root}")

    files: list[ProjectFolderFile] = []
    truncated = False
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        dirnames[:] = sorted(
            name
            for name in dirnames
            if name not in _SKIP_DIR_NAMES and not name.startswith(".")
        )
        base = Path(dirpath)
        for name in sorted(filenames):
            if name.startswith(".") or name in _SKIP_DIR_NAMES:
                continue
            path = base / name
            if not path.is_file():
                continue
            try:
                rel = path.relative_to(root).as_posix()
                stat = path.stat()
            except OSError:
                continue
            files.append(
                ProjectFolderFile(
                    path=rel,
                    name=path.name,
                    kind=library_kind_for_name(path.name),
                    size=stat.st_size,
                    mtime=datetime.fromtimestamp(stat.st_mtime, UTC),
                )
            )
            if len(files) >= _MAX_FILES:
                truncated = True
                break
        if truncated:
            break

    files.sort(
        key=lambda item: (
            -(item.mtime.timestamp() if item.mtime else 0.0),
            item.path.lower(),
        )
    )
    return ProjectFolderListing(
        folder_path=str(root),
        truncated=truncated,
        data=files,
    )


def read_project_folder_file(folder_path: str, relative_path: str) -> WorkspaceFileContent:
    _root, candidate, value = _resolve_file(folder_path, relative_path)
    data = candidate.read_bytes()
    if len(data) > _MAX_READ_BYTES:
        raise ValueError("File is too large to preview.")

    mime_type = mimetypes.guess_type(candidate.name)[0] or "application/octet-stream"
    is_text = mime_type.startswith("text/") or candidate.suffix.lower() in TEXT_SUFFIXES
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
        path=value,
        content=content,
        encoding=encoding,
        mime_type=mime_type,
        version=hashlib.sha256(data).hexdigest(),
        size=len(data),
        mtime=datetime.fromtimestamp(candidate.stat().st_mtime, UTC),
    )


def rename_project_folder_file(
    folder_path: str, relative_path: str, new_name: str
) -> ProjectFolderFile:
    root, source, _value = _resolve_file(folder_path, relative_path)
    safe = sanitize_upload_filename(new_name)
    if not safe or not _SAFE_NAME.match(safe):
        raise ValueError("Invalid file name.")
    dest = source.parent / safe
    resolved = dest.resolve(strict=False)
    try:
        if not resolved.is_relative_to(root):
            raise ValueError("Path escapes the project folder.")
    except (OSError, ValueError) as exc:
        raise ValueError("Path escapes the project folder.") from exc
    if dest.exists():
        raise ValueError(f"A file named {safe!r} already exists.")
    source.rename(dest)
    return _entry_for(root, dest)


def delete_project_folder_file(folder_path: str, relative_path: str) -> None:
    _root, candidate, _value = _resolve_file(folder_path, relative_path)
    candidate.unlink()


def use_project_folder_in_chat(
    *,
    agent_service,
    project_id: str,
    paths: list[str],
    folder_path: str,
    title: str | None = None,
) -> UseLibraryInChatResponse:
    """Start a project session with ``project/...`` attachments (live folder mount)."""
    if not paths:
        raise ValueError("At least one path is required.")
    # Validate each path exists under the linked folder before creating a session.
    for relative in paths:
        _resolve_file(folder_path, relative)

    session = agent_service.create_session(
        title=title or "Project folder chat",
        workspace_path=None,
        project_id=project_id,
        client_surface="ui",
    )
    agent_service.ensure_workspace(session.id)
    mounted: list[str] = []
    for relative in paths:
        value = relative.strip().replace("\\", "/")
        if value in {"", "."}:
            mounted.append(PROJECT_FOLDER_LINK_NAME)
        else:
            mounted.append(f"{PROJECT_FOLDER_LINK_NAME}/{value}")
    return UseLibraryInChatResponse(session_id=session.id, paths=mounted)
