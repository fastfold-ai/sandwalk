"""Workspace-items denormalized index (FAS-107).

One row per pane-able thing (chat, terminal, later files/preview/etc.).
The tab strip / sidebar / split picker query this table instead of
UNIONing per kind — writes fan out via ``upsert_workspace_item`` from the
kind-specific mixin. Deletes cascade via ``delete_workspace_item``.

Precedent: Notion's block table, Airtable's table > view > row split,
VSCode's Tab.input discriminated union.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime

from agent_server.models import WorkspaceItem, WorkspaceItemKind
from agent_server.store.util import utc_now


def _iso(value: datetime) -> str:
    return value.isoformat()


def _row_to_item(row: sqlite3.Row) -> WorkspaceItem:
    return WorkspaceItem(
        id=str(row["id"]),
        kind=str(row["kind"]),  # type: ignore[arg-type]
        project_id=(str(row["project_id"]) if row["project_id"] is not None else None),
        organize_label=(
            str(row["organize_label"]) if row["organize_label"] is not None else None
        ),
        title=str(row["title"]),
        updated_at=datetime.fromisoformat(str(row["updated_at"])),
    )


class WorkspaceItemMixin:
    """CRUD over the workspace_items denormalized index."""

    def upsert_workspace_item(
        self,
        *,
        item_id: str,
        kind: WorkspaceItemKind,
        project_id: str | None,
        organize_label: str | None,
        title: str,
        updated_at: datetime | None = None,
    ) -> None:
        """Write-through called by chat/terminal create/update paths.

        Idempotent: safe to call on every mutation of the underlying entity.
        Callers must hold ``self._write_lock`` (this method opens its own
        connection so it composes with the callers's ``with self._connect()``
        block only when explicitly serialized — we do the safe thing here
        by grabbing the write lock ourselves).
        """
        ts = _iso(updated_at or utc_now())
        with self._write_lock, self._connect() as connection:  # type: ignore[attr-defined]
            connection.execute(
                """
                INSERT INTO workspace_items(
                    id, kind, project_id, organize_label, title, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    kind = excluded.kind,
                    project_id = excluded.project_id,
                    organize_label = excluded.organize_label,
                    title = excluded.title,
                    updated_at = excluded.updated_at
                """,
                (item_id, kind, project_id, organize_label, title, ts),
            )

    def delete_workspace_item(self, item_id: str) -> None:
        """No-op if the row is not present. Callers may delete the underlying
        entity first (chat / terminal) and then call this to clean the index."""
        with self._write_lock, self._connect() as connection:  # type: ignore[attr-defined]
            connection.execute("DELETE FROM workspace_items WHERE id = ?", (item_id,))

    def list_workspace_items(
        self,
        *,
        project_id: str | None = None,
        kinds: list[WorkspaceItemKind] | None = None,
        limit: int = 200,
    ) -> list[WorkspaceItem]:
        """Ordered by updated_at DESC. Pass ``project_id=None`` to list all;
        pass an explicit empty string for "no-project" items."""
        clauses: list[str] = []
        params: list[object] = []
        if project_id is not None:
            if project_id == "":
                clauses.append("project_id IS NULL")
            else:
                clauses.append("project_id = ?")
                params.append(project_id)
        if kinds:
            placeholders = ", ".join("?" for _ in kinds)
            clauses.append(f"kind IN ({placeholders})")
            params.extend(kinds)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(max(1, min(limit, 1000)))
        with self._connect() as connection:  # type: ignore[attr-defined]
            rows = connection.execute(
                f"""
                SELECT id, kind, project_id, organize_label, title, updated_at
                FROM workspace_items
                {where}
                ORDER BY updated_at DESC
                LIMIT ?
                """,
                tuple(params),
            ).fetchall()
        return [_row_to_item(row) for row in rows]

    def get_workspace_item(self, item_id: str) -> WorkspaceItem | None:
        with self._connect() as connection:  # type: ignore[attr-defined]
            row = connection.execute(
                """
                SELECT id, kind, project_id, organize_label, title, updated_at
                FROM workspace_items
                WHERE id = ?
                """,
                (item_id,),
            ).fetchone()
        return _row_to_item(row) if row else None
