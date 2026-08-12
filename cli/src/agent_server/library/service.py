"""Library service: ingest, list, rename, delete, use-in-chat."""

from __future__ import annotations

import base64
import logging
import mimetypes
import threading
from pathlib import Path
from typing import Literal

from agent_server.library.blobs import LibraryBlobStore
from agent_server.library.kind import library_kind_for_name
from agent_server.models.library import (
    LibraryFileContent,
    LibraryItem,
    LibraryItemList,
    LibraryKind,
    LibraryPagination,
    LibrarySyncResponse,
    UseLibraryInChatResponse,
)
from agent_server.service import AgentService
from agent_server.store import AgentStore
from agent_server.workspace import TEXT_SUFFIXES
from agent_server.workspace.filenames import (
    sanitize_upload_filename,
    unique_upload_relative_path,
)

logger = logging.getLogger("agent_server.library")

_BACKFILL_META_KEY = "library_workspace_backfill_v1"
_SCAN_DIRS = ("uploads", "outputs", "artifacts")
_SKIP_NAMES = {".DS_Store", "Thumbs.db", ".gitkeep"}
_SKIP_DIR_NAMES = {"__pycache__", ".git", "node_modules", ".venv", "venv"}
_SKIP_SUFFIXES = {".pyc", ".pyo", ".tmp", ".swp"}


class LibraryService:
    def __init__(
        self,
        store: AgentStore,
        agent_service: AgentService,
        blobs: LibraryBlobStore | None = None,
    ) -> None:
        self.store = store
        self.agent_service = agent_service
        self.blobs = blobs or LibraryBlobStore()
        self._sync_lock = threading.Lock()

    def ingest_bytes(
        self,
        data: bytes,
        *,
        filename: str,
        mime: str | None = None,
        origin_session_id: str | None = None,
        display_name: str | None = None,
    ) -> LibraryItem:
        safe_name = sanitize_upload_filename(filename)
        sha256, size = self.blobs.put_bytes(data)
        guessed, _ = mimetypes.guess_type(safe_name)
        kind = library_kind_for_name(safe_name)
        name = (display_name or safe_name).strip() or safe_name
        return self.store.create_library_item(
            sha256=sha256,
            bytes_size=size,
            mime=mime or guessed,
            original_name=safe_name,
            display_name=name,
            kind=kind,
            origin_session_id=origin_session_id,
        )

    def ingest_file(
        self,
        path: Path,
        *,
        filename: str | None = None,
        mime: str | None = None,
        origin_session_id: str | None = None,
        display_name: str | None = None,
    ) -> LibraryItem:
        source = path.expanduser().resolve()
        safe_name = sanitize_upload_filename(filename or source.name)
        sha256, size = self.blobs.put_file(source)
        guessed, _ = mimetypes.guess_type(safe_name)
        kind = library_kind_for_name(safe_name)
        name = (display_name or safe_name).strip() or safe_name
        return self.store.create_library_item(
            sha256=sha256,
            bytes_size=size,
            mime=mime or guessed,
            original_name=safe_name,
            display_name=name,
            kind=kind,
            origin_session_id=origin_session_id,
        )

    def list_items(
        self,
        *,
        kind: LibraryKind | None = None,
        query: str | None = None,
        project_id: str | None = None,
        page: int = 0,
        per_page: int = 48,
    ) -> LibraryItemList:
        self.ensure_workspace_backfill()
        page_value = max(0, int(page))
        per_page_value = max(1, min(int(per_page), 500))
        total = self.store.count_library_items(
            kind=kind, query=query, project_id=project_id
        )
        data = self.store.list_library_items(
            kind=kind,
            query=query,
            project_id=project_id,
            page=page_value,
            per_page=per_page_value,
        )
        has_more = (page_value + 1) * per_page_value < total
        return LibraryItemList(
            data=data,
            pagination=LibraryPagination(
                page=page_value,
                per_page=per_page_value,
                total=total,
                has_more=has_more,
            ),
        )

    def ensure_workspace_backfill(self) -> None:
        """One-time scan of existing session workspaces into the Library index."""
        if self.store.get_meta(_BACKFILL_META_KEY) == "1":
            return
        with self._sync_lock:
            if self.store.get_meta(_BACKFILL_META_KEY) == "1":
                return
            try:
                result = self.sync_from_workspaces()
                logger.info(
                    "Library backfill: sessions=%s ingested=%s linked=%s skipped=%s",
                    result.scanned_sessions,
                    result.ingested,
                    result.linked,
                    result.skipped,
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("Library workspace backfill failed: %s", exc)
                return
            self.store.set_meta(_BACKFILL_META_KEY, "1")

    def sync_from_workspaces(self) -> LibrarySyncResponse:
        """Index files under uploads/outputs/artifacts across all sessions."""
        sessions = self.store.list_sessions()
        ingested = 0
        linked = 0
        skipped = 0
        scanned = 0
        for session in sessions:
            root = self._session_workspace_root(session.id, session.workspace_path)
            if root is None:
                continue
            scanned += 1
            for relative in self._iter_library_candidate_files(root):
                path = root / relative
                try:
                    status = self._ingest_workspace_file(
                        path,
                        origin_session_id=session.id,
                    )
                except Exception as exc:  # noqa: BLE001
                    logger.debug(
                        "Library sync skip %s (%s): %s",
                        session.id,
                        relative,
                        exc,
                    )
                    skipped += 1
                    continue
                if status == "ingested":
                    ingested += 1
                elif status == "linked":
                    linked += 1
                else:
                    skipped += 1
        return LibrarySyncResponse(
            scanned_sessions=scanned,
            ingested=ingested,
            linked=linked,
            skipped=skipped,
        )

    def _session_workspace_root(
        self,
        session_id: str,
        workspace_path: str | None,
    ) -> Path | None:
        if workspace_path:
            root = Path(workspace_path).expanduser()
            if root.is_dir():
                return root.resolve()
        try:
            from agent_server.service import default_workspace_path

            root = default_workspace_path(session_id)
            if root.is_dir():
                return root.resolve()
        except Exception:  # noqa: BLE001
            return None
        return None

    def _iter_library_candidate_files(self, root: Path) -> list[str]:
        found: list[str] = []
        for dirname in _SCAN_DIRS:
            base = root / dirname
            if not base.is_dir():
                continue
            for path in base.rglob("*"):
                if not path.is_file():
                    continue
                if any(part in _SKIP_DIR_NAMES for part in path.parts):
                    continue
                if path.name in _SKIP_NAMES or path.name.startswith("."):
                    continue
                if path.suffix.lower() in _SKIP_SUFFIXES:
                    continue
                try:
                    relative = path.relative_to(root).as_posix()
                except ValueError:
                    continue
                found.append(relative)
        return found

    def _ingest_workspace_file(
        self,
        path: Path,
        *,
        origin_session_id: str,
    ) -> str:
        try:
            size = path.stat().st_size
        except OSError:
            return "skipped"
        if size <= 0:
            return "skipped"
        sha256, _ = self.blobs.put_file(path)
        existing = self.store.get_library_item_by_sha(sha256)
        if existing is not None:
            self.store.link_library_item_session(existing.id, origin_session_id)
            return "linked"
        self.ingest_file(
            path,
            filename=path.name,
            origin_session_id=origin_session_id,
        )
        return "ingested"

    def get_item(self, item_id: str) -> LibraryItem | None:
        return self.store.get_library_item(item_id)

    def rename(self, item_id: str, display_name: str) -> LibraryItem | None:
        return self.store.update_library_item_display_name(item_id, display_name)

    def write_content(
        self,
        item_id: str,
        data: bytes,
        *,
        mime: str | None = None,
    ) -> LibraryItem:
        item = self.store.get_library_item(item_id)
        if item is None:
            raise KeyError(item_id)
        old_sha = item.sha256
        sha256, size = self.blobs.put_bytes(data)
        name = item.display_name or item.original_name
        guessed, _ = mimetypes.guess_type(name)
        kind = library_kind_for_name(name)
        updated = self.store.update_library_item_content(
            item_id,
            sha256=sha256,
            bytes_size=size,
            mime=mime or item.mime or guessed,
            kind=kind,
        )
        if updated is None:
            raise KeyError(item_id)
        if old_sha != sha256 and self.store.count_library_items_for_sha(old_sha) == 0:
            self.blobs.maybe_delete_blob(old_sha)
        return updated

    def delete(self, item_id: str) -> bool:
        deleted, orphan_sha = self.store.delete_library_item(item_id)
        if orphan_sha:
            self.blobs.maybe_delete_blob(orphan_sha)
        return deleted

    def content_path(self, item_id: str) -> Path | None:
        item = self.store.get_library_item(item_id)
        if item is None:
            return None
        path = self.blobs.path_for(item.sha256)
        if not path.is_file():
            return None
        return path

    def read_file_content(self, item_id: str) -> LibraryFileContent | None:
        item = self.store.get_library_item(item_id)
        if item is None:
            return None
        path = self.blobs.path_for(item.sha256)
        if not path.is_file():
            return None
        data = path.read_bytes()
        name = item.display_name or item.original_name
        mime = item.mime or mimetypes.guess_type(name)[0] or "application/octet-stream"
        suffix = Path(name).suffix.lower()
        is_text = mime.startswith("text/") or suffix in TEXT_SUFFIXES
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
        return LibraryFileContent(
            path=name,
            content=content,
            encoding=encoding,
            mime_type=mime,
            version=item.sha256,
            size=len(data),
            mtime=item.updated_at,
        )

    def use_in_chat(
        self,
        item_ids: list[str],
        *,
        project_id: str | None = None,
        title: str | None = None,
    ) -> UseLibraryInChatResponse:
        items: list[LibraryItem] = []
        for item_id in item_ids:
            item = self.store.get_library_item(item_id)
            if item is None:
                raise KeyError(item_id)
            items.append(item)
        session = self.agent_service.create_session(
            title=title or "Library chat",
            workspace_path=None,
            project_id=project_id,
            client_surface="ui",
        )
        session = self.agent_service.ensure_workspace(session.id)
        if not session.workspace_path:
            raise RuntimeError("Session has no workspace.")
        root = Path(session.workspace_path)
        paths: list[str] = []
        for item in items:
            safe_name = sanitize_upload_filename(item.display_name or item.original_name)
            relative = unique_upload_relative_path(root, "uploads", safe_name)
            dest = root / relative
            self.blobs.materialize(item.sha256, dest)
            self.store.link_library_item_session(item.id, session.id)
            paths.append(relative)
        return UseLibraryInChatResponse(session_id=session.id, paths=paths)

    def try_ingest_upload(
        self,
        data: bytes,
        *,
        filename: str,
        mime: str | None,
        session_id: str,
    ) -> None:
        """Best-effort ingest after a workspace upload (never raises to caller)."""
        try:
            self.ingest_bytes(
                data,
                filename=filename,
                mime=mime,
                origin_session_id=session_id,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Library ingest after upload failed: %s", exc)
