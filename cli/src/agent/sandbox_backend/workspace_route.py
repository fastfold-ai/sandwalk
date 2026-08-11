"""Route session-workspace tool paths to the host Files panel + Modal /workspace.

Deepagents ``write_file`` with Modal as the default backend previously wrote
host-absolute paths (e.g. ``~/.sandwalk/workspaces/<id>/plans/...``) into the
sandbox at that literal path — outside ``/workspace``. End-of-turn pull only
syncs ``/workspace``, so the host Files panel stayed empty while the tool still
reported success.

This wrapper:
1. Detects session-workspace paths (host absolute, ``/workspace/...``, or relative)
2. Writes/edits the host file immediately (UI Files panel)
3. Mirrors the same bytes under Modal ``/workspace/...`` for compute
"""

from __future__ import annotations

import base64
import logging
import os
from pathlib import Path
from typing import Any

from deepagents.backends.protocol import EditResult, ReadResult, WriteResult

from agent.sandbox_sync.paths import WORKSPACE_REMOTE_ROOT

logger = logging.getLogger(__name__)


def _sandwalk_host_path(path: str | None) -> Path | None:
    """Return an absolute host path when it is under Sandwalk's dynamic base."""
    raw = str(path or "").strip()
    base = str(os.environ.get("SANDWALK_CONFIG_DIR") or "").strip()
    if not raw or not base:
        return None
    candidate = Path(raw).expanduser()
    if not candidate.is_absolute():
        return None
    try:
        root = Path(base).expanduser().resolve()
        resolved = candidate.parent.resolve() / candidate.name
        if resolved == root or resolved.is_relative_to(root):
            return resolved
    except (OSError, ValueError):
        return None
    return None


def _read_host_file(path: Path, offset: int, limit: int) -> ReadResult:
    """Read a host file directly, bypassing symlink-root checks in FS backends.

    Mirrors deepagents' text/binary + offset/limit + empty-content behavior so
    files under the ``project/`` symlink (which resolves outside the workspace
    root) can still be read by the model.
    """
    from deepagents.backends.filesystem import check_empty_content
    from deepagents.backends.protocol import FileData

    try:
        raw = path.read_bytes()
    except OSError as exc:
        return ReadResult(error=f"Error reading file '{path}': {exc}")

    try:
        content = raw.decode("utf-8")
    except UnicodeDecodeError:
        encoded = base64.standard_b64encode(raw).decode("ascii")
        return ReadResult(
            file_data=FileData(content=encoded, encoding="base64")
        )

    empty = check_empty_content(content)
    if empty:
        return ReadResult(file_data=FileData(content=empty, encoding="utf-8"))

    lines = content.splitlines(keepends=True)
    start = offset
    end = min(start + limit, len(lines))
    if start >= len(lines):
        return ReadResult(
            error=f"Line offset {offset} exceeds file length ({len(lines)} lines)"
        )
    return ReadResult(
        file_data=FileData(content="".join(lines[start:end]), encoding="utf-8")
    )


def workspace_relative_tool_path(
    path: str | None, workspace_root: str | Path
) -> str | None:
    """Return a posix relative path when ``path`` targets the session workspace.

    Also maps absolute paths that resolve through ``workspace/project`` (symlink
    to an external project folder) back to ``project/...`` so host mirroring and
    overwrite writes work the same as other workspace files.
    """
    raw = str(path or "").strip()
    if not raw:
        return None
    if raw.startswith("/skills/") or raw == "/skills":
        return None

    root = Path(workspace_root).expanduser().resolve()
    remote = WORKSPACE_REMOTE_ROOT.rstrip("/")
    if raw == remote or raw.startswith(f"{remote}/"):
        return raw[len(remote) :].lstrip("/")

    if not raw.startswith("/"):
        cleaned = raw.replace("\\", "/").lstrip("./")
        if not cleaned or ".." in cleaned.split("/"):
            return None
        return cleaned

    from agent_server.project_folder import (
        path_under_workspace_or_project,
        workspace_rel_via_project_mount,
    )

    try:
        candidate = Path(raw).expanduser()
        allowed = path_under_workspace_or_project(candidate, root)
    except (OSError, RuntimeError, ValueError):
        return None
    if allowed is None:
        return None
    try:
        return allowed.relative_to(root).as_posix()
    except ValueError:
        return workspace_rel_via_project_mount(allowed, root)


def _host_abs(root: Path, rel: str) -> str:
    return str(root / rel) if rel else str(root)


def _modal_path(rel: str) -> str:
    remote = WORKSPACE_REMOTE_ROOT.rstrip("/")
    return f"{remote}/{rel}" if rel else remote


def _mirror_host_text(root: Path, rel: str, content: str) -> Path:
    dest = root / rel if rel else root
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(content, encoding="utf-8")
    return dest


def _mirror_modal_text(inner: Any, rel: str, content: str) -> None:
    path = _modal_path(rel)
    payload = content.encode("utf-8")
    upload = getattr(inner, "upload_files", None)
    if callable(upload):
        try:
            upload([(path, payload)])
            return
        except Exception as exc:  # noqa: BLE001
            logger.debug("Modal upload mirror for %s failed: %s", path, exc)
    # FilesystemBackend.write refuses overwrites — skip when the path already
    # exists on an inner FS backend; host bytes were already written.
    try:
        from deepagents.backends import FilesystemBackend

        if isinstance(inner, FilesystemBackend):
            return
    except Exception:  # noqa: BLE001
        pass
    try:
        result = inner.write(path, content)
        if getattr(result, "error", None):
            logger.debug("Modal workspace write for %s: %s", path, result.error)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Modal mirror write failed for %s: %s", path, exc)


class HostWorkspaceMirrorBackend:
    """Proxy backend that mirrors workspace file ops onto the host tree."""

    def __init__(self, inner: Any, workspace_root: str | Path):
        self._inner = inner
        self._root = Path(workspace_root).expanduser().resolve()

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)

    def write(self, file_path: str, content: str) -> WriteResult:
        rel = workspace_relative_tool_path(file_path, self._root)
        if rel is None:
            host_path = _sandwalk_host_path(file_path)
            if host_path is not None:
                try:
                    host_path.parent.mkdir(parents=True, exist_ok=True)
                    host_path.write_text(content, encoding="utf-8")
                    return WriteResult(path=str(host_path))
                except OSError as exc:
                    return WriteResult(
                        error=f"Error writing host file '{file_path}': {exc}"
                    )
            return self._inner.write(file_path, content)
        try:
            _mirror_host_text(self._root, rel, content)
        except OSError as exc:
            return WriteResult(error=f"Error writing host file '{file_path}': {exc}")
        _mirror_modal_text(self._inner, rel, content)
        return WriteResult(path=_host_abs(self._root, rel))

    def edit(
        self,
        file_path: str,
        old_string: str,
        new_string: str,
        replace_all: bool = False,  # noqa: FBT001, FBT002
    ) -> EditResult:
        rel = workspace_relative_tool_path(file_path, self._root)
        if rel is None:
            host_path = _sandwalk_host_path(file_path)
            if host_path is not None and host_path.is_file():
                try:
                    text = host_path.read_text(encoding="utf-8")
                except OSError as exc:
                    return EditResult(
                        error=f"Error reading host file '{file_path}': {exc}"
                    )
                count = text.count(old_string)
                if count == 0:
                    return EditResult(error=f"String not found in {file_path}")
                if not replace_all and count > 1:
                    return EditResult(
                        error=(
                            f"Multiple matches for edit in {file_path} "
                            f"({count}); set replace_all=True to replace all."
                        )
                    )
                updated = (
                    text.replace(old_string, new_string)
                    if replace_all
                    else text.replace(old_string, new_string, 1)
                )
                try:
                    host_path.write_text(updated, encoding="utf-8")
                except OSError as exc:
                    return EditResult(
                        error=f"Error writing host file '{file_path}': {exc}"
                    )
                return EditResult(
                    path=str(host_path),
                    occurrences=count if replace_all else 1,
                )
            return self._inner.edit(
                file_path, old_string, new_string, replace_all=replace_all
            )
        host_path = self._root / rel if rel else self._root
        if not host_path.is_file():
            modal_res = self._inner.edit(
                _modal_path(rel), old_string, new_string, replace_all=replace_all
            )
            if getattr(modal_res, "error", None):
                return modal_res
            return EditResult(
                path=_host_abs(self._root, rel),
                occurrences=getattr(modal_res, "occurrences", None),
            )

        try:
            text = host_path.read_text(encoding="utf-8")
        except OSError as exc:
            return EditResult(error=f"Error reading host file '{file_path}': {exc}")
        count = text.count(old_string)
        if count == 0:
            return EditResult(error=f"String not found in {file_path}")
        if not replace_all and count > 1:
            return EditResult(
                error=(
                    f"Multiple matches for edit in {file_path} "
                    f"({count}); set replace_all=True to replace all."
                )
            )
        updated = (
            text.replace(old_string, new_string)
            if replace_all
            else text.replace(old_string, new_string, 1)
        )
        try:
            _mirror_host_text(self._root, rel, updated)
        except OSError as exc:
            return EditResult(error=f"Error writing host file '{file_path}': {exc}")
        _mirror_modal_text(self._inner, rel, updated)
        return EditResult(
            path=_host_abs(self._root, rel),
            occurrences=count if replace_all else 1,
        )

    def read(self, file_path: str, offset: int = 0, limit: int = 2000) -> Any:
        rel = workspace_relative_tool_path(file_path, self._root)
        if rel is None:
            host_path = _sandwalk_host_path(file_path)
            if host_path is not None and host_path.is_file():
                return _read_host_file(host_path, offset, limit)
            return self._inner.read(file_path, offset=offset, limit=limit)
        host_path = self._root / rel if rel else self._root
        if host_path.is_file():
            # Read directly: FilesystemBackend resolves the project/ symlink and
            # rejects it as "outside root directory".
            return _read_host_file(host_path, offset, limit)
        return self._inner.read(_modal_path(rel), offset=offset, limit=limit)

    # deepagents tool nodes call the async variants — route them through the
    # same host-mirror logic so workspace/project writes upsert instead of
    # falling through to the inner backend's create-only "already exists" path.
    async def awrite(self, file_path: str, content: str) -> WriteResult:
        import asyncio

        return await asyncio.to_thread(self.write, file_path, content)

    async def aedit(
        self,
        file_path: str,
        old_string: str,
        new_string: str,
        replace_all: bool = False,  # noqa: FBT001, FBT002
    ) -> EditResult:
        import asyncio

        return await asyncio.to_thread(
            self.edit, file_path, old_string, new_string, replace_all
        )

    async def aread(
        self, file_path: str, offset: int = 0, limit: int = 2000
    ) -> Any:
        import asyncio

        return await asyncio.to_thread(self.read, file_path, offset, limit)


def wrap_backend_for_host_workspace(backend: Any, workspace_root: str | Path) -> Any:
    """Wrap a Modal (or composite) backend so workspace paths hit the host tree."""
    root = str(Path(workspace_root).expanduser().resolve())
    if isinstance(backend, HostWorkspaceMirrorBackend):
        return backend
    return HostWorkspaceMirrorBackend(backend, root)
