"""Terminal-as-first-class-item persistence (FAS-107).

The row here is the durable metadata for a terminal (id, cwd, title,
project). The live PTY (fd, buffer, WebSocket subscribers) is held in
``PtyManager`` and is expected to be respawned on restart from this row —
same pattern as VSCode's process reconnection, iTerm2's Restore Windows,
Zed's pty-host RFC. Scrollback bytes live in ``pty_scrollback``.

Writes fan out to ``workspace_items`` via ``upsert_workspace_item`` so the
tab strip / sidebar can query a single indexed table.
"""

from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime

from agent_server.models import TerminalSession, TerminalStatus, TerminalTitleSource
from agent_server.store.util import utc_now


def _iso(value: datetime) -> str:
    return value.isoformat()


def _row_to_terminal(row: sqlite3.Row) -> TerminalSession:
    last_activity = row["last_activity_at"]
    return TerminalSession(
        id=str(row["id"]),
        title=str(row["title"]),
        title_source=str(row["title_source"]),  # type: ignore[arg-type]
        project_id=(str(row["project_id"]) if row["project_id"] is not None else None),
        workspace_path=(
            str(row["workspace_path"]) if row["workspace_path"] is not None else None
        ),
        shell=(str(row["shell"]) if row["shell"] is not None else None),
        origin_chat_id=(
            str(row["origin_chat_id"]) if row["origin_chat_id"] is not None else None
        ),
        slot_key=(str(row["slot_key"]) if row["slot_key"] is not None else None),
        status=str(row["status"]),  # type: ignore[arg-type]
        last_activity_at=(
            datetime.fromisoformat(str(last_activity)) if last_activity is not None else None
        ),
        created_at=datetime.fromisoformat(str(row["created_at"])),
        updated_at=datetime.fromisoformat(str(row["updated_at"])),
    )


class TerminalSessionMixin:
    """CRUD for terminals. See ``WorkspaceItemMixin`` for the index side."""

    def create_terminal(
        self,
        *,
        title: str | None = None,
        project_id: str | None = None,
        workspace_path: str | None = None,
        shell: str | None = None,
        origin_chat_id: str | None = None,
        slot_key: str | None = None,
        terminal_id: str | None = None,
    ) -> TerminalSession:
        resolved_id = (terminal_id or f"term_{uuid.uuid4().hex}").strip()
        if not resolved_id:
            raise ValueError("Terminal id cannot be empty.")
        cleaned_title = (title or "").strip()
        resolved_title = cleaned_title or self._default_terminal_title()
        resolved_source: TerminalTitleSource = "user" if cleaned_title else "pending"
        now = utc_now()
        terminal = TerminalSession(
            id=resolved_id,
            title=resolved_title,
            title_source=resolved_source,
            project_id=project_id,
            workspace_path=workspace_path,
            shell=shell,
            origin_chat_id=origin_chat_id,
            slot_key=slot_key,
            status="idle",
            last_activity_at=None,
            created_at=now,
            updated_at=now,
        )
        with self._write_lock, self._connect() as connection:  # type: ignore[attr-defined]
            connection.execute(
                """
                INSERT INTO terminal_sessions(
                    id, title, title_source, project_id, workspace_path,
                    shell, origin_chat_id, slot_key, status,
                    last_activity_at, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    terminal.id,
                    terminal.title,
                    terminal.title_source,
                    terminal.project_id,
                    terminal.workspace_path,
                    terminal.shell,
                    terminal.origin_chat_id,
                    terminal.slot_key,
                    terminal.status,
                    None,
                    _iso(terminal.created_at),
                    _iso(terminal.updated_at),
                ),
            )
        # Write-through to the unified index. Kept outside the SQL block so
        # the workspace_items row lands after the parent row commits.
        self.upsert_workspace_item(  # type: ignore[attr-defined]
            item_id=terminal.id,
            kind="terminal",
            project_id=terminal.project_id,
            organize_label=None,
            title=terminal.title,
            updated_at=terminal.updated_at,
        )
        return terminal

    def get_terminal(self, terminal_id: str) -> TerminalSession | None:
        with self._connect() as connection:  # type: ignore[attr-defined]
            row = connection.execute(
                """
                SELECT id, title, title_source, project_id, workspace_path,
                       shell, origin_chat_id, slot_key, status,
                       last_activity_at, created_at, updated_at
                FROM terminal_sessions
                WHERE id = ?
                """,
                (terminal_id,),
            ).fetchone()
        return _row_to_terminal(row) if row else None

    def list_terminals(
        self,
        *,
        project_id: str | None = None,
        limit: int = 200,
    ) -> list[TerminalSession]:
        clauses: list[str] = []
        params: list[object] = []
        if project_id is not None:
            if project_id == "":
                clauses.append("project_id IS NULL")
            else:
                clauses.append("project_id = ?")
                params.append(project_id)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(max(1, min(limit, 1000)))
        with self._connect() as connection:  # type: ignore[attr-defined]
            rows = connection.execute(
                f"""
                SELECT id, title, title_source, project_id, workspace_path,
                       shell, origin_chat_id, slot_key, status,
                       last_activity_at, created_at, updated_at
                FROM terminal_sessions
                {where}
                ORDER BY updated_at DESC
                LIMIT ?
                """,
                tuple(params),
            ).fetchall()
        return [_row_to_terminal(row) for row in rows]

    def update_terminal(
        self,
        terminal_id: str,
        *,
        title: str | None = None,
        title_source: TerminalTitleSource | None = None,
        project_id: str | None = None,
        organize_label: str | None = None,
        status: TerminalStatus | None = None,
        last_activity_at: datetime | None = None,
    ) -> TerminalSession | None:
        existing = self.get_terminal(terminal_id)
        if existing is None:
            return None
        assignments: list[str] = []
        params: list[object] = []
        if title is not None:
            assignments.append("title = ?")
            params.append(title)
            if title_source is None:
                title_source = "user"
        if title_source is not None:
            assignments.append("title_source = ?")
            params.append(title_source)
        if project_id is not None:
            assignments.append("project_id = ?")
            params.append(project_id or None)
        if status is not None:
            assignments.append("status = ?")
            params.append(status)
        if last_activity_at is not None:
            assignments.append("last_activity_at = ?")
            params.append(_iso(last_activity_at))
        # organize_label is stored on the workspace_items row (index-side),
        # not on the terminal_sessions row — same shape as SessionGroup.
        # We still want to bump updated_at even if only that changed.
        now = utc_now()
        assignments.append("updated_at = ?")
        params.append(_iso(now))
        with self._write_lock, self._connect() as connection:  # type: ignore[attr-defined]
            connection.execute(
                f"UPDATE terminal_sessions SET {', '.join(assignments)} WHERE id = ?",
                (*params, terminal_id),
            )
        refreshed = self.get_terminal(terminal_id)
        if refreshed is None:
            return None
        # Sync the index. organize_label is preserved (or set) here since the
        # index is where it lives.
        effective_label = organize_label
        if effective_label is None:
            existing_item = self.get_workspace_item(terminal_id)  # type: ignore[attr-defined]
            effective_label = existing_item.organize_label if existing_item else None
        self.upsert_workspace_item(  # type: ignore[attr-defined]
            item_id=refreshed.id,
            kind="terminal",
            project_id=refreshed.project_id,
            organize_label=effective_label,
            title=refreshed.title,
            updated_at=refreshed.updated_at,
        )
        return refreshed

    def delete_terminal(self, terminal_id: str) -> bool:
        with self._write_lock, self._connect() as connection:  # type: ignore[attr-defined]
            cursor = connection.execute(
                "DELETE FROM terminal_sessions WHERE id = ?",
                (terminal_id,),
            )
            deleted = cursor.rowcount > 0
        if deleted:
            # pty_scrollback cascades via FK ON DELETE CASCADE (see migrations).
            self.delete_workspace_item(terminal_id)  # type: ignore[attr-defined]
        return deleted

    def _default_terminal_title(self) -> str:
        """Auto-name for a new terminal: ``Terminal 1``, ``Terminal 2``, …

        Counts existing terminals to pick the next ordinal. Not strictly
        monotonic under concurrent creates — good enough for a single-user
        desktop app; the frontend can always rename.
        """
        with self._connect() as connection:  # type: ignore[attr-defined]
            row = connection.execute(
                "SELECT COUNT(*) AS n FROM terminal_sessions"
            ).fetchone()
        n = int(row["n"] if row else 0) + 1
        return f"Terminal {n}"
