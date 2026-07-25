"""Library items CRUD in the agent SQLite store."""

from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime

from agent_server.models.library import LibraryItem, LibraryKind
from agent_server.store.util import utc_now


def library_item_from_row(row: sqlite3.Row) -> LibraryItem:
    return LibraryItem(
        id=str(row["id"]),
        sha256=str(row["sha256"]),
        bytes=int(row["bytes"]),
        mime=row["mime"],
        original_name=str(row["original_name"]),
        display_name=str(row["display_name"]),
        kind=str(row["kind"]),  # type: ignore[arg-type]
        origin_session_id=row["origin_session_id"],
        created_at=datetime.fromisoformat(str(row["created_at"])),
        updated_at=datetime.fromisoformat(str(row["updated_at"])),
    )


class LibraryMixin:
    def create_library_item(
        self,
        *,
        sha256: str,
        bytes_size: int,
        mime: str | None,
        original_name: str,
        display_name: str,
        kind: LibraryKind,
        origin_session_id: str | None = None,
    ) -> LibraryItem:
        now = utc_now()
        item_id = str(uuid.uuid4())
        with self._write_lock, self._connect() as connection:
            connection.execute(
                """
                INSERT INTO library_items(
                    id, sha256, bytes, mime, original_name, display_name,
                    kind, origin_session_id, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    item_id,
                    sha256,
                    int(bytes_size),
                    mime,
                    original_name,
                    display_name,
                    kind,
                    origin_session_id,
                    now.isoformat(),
                    now.isoformat(),
                ),
            )
            if origin_session_id:
                connection.execute(
                    """
                    INSERT OR IGNORE INTO library_item_sessions(item_id, session_id)
                    VALUES (?, ?)
                    """,
                    (item_id, origin_session_id),
                )
        item = self.get_library_item(item_id)
        if item is None:
            raise RuntimeError("Failed to create library item.")
        return item

    def get_library_item(self, item_id: str) -> LibraryItem | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM library_items WHERE id = ?",
                (item_id,),
            ).fetchone()
        if row is None:
            return None
        return library_item_from_row(row)

    def get_library_item_by_sha(self, sha256: str) -> LibraryItem | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT * FROM library_items
                WHERE sha256 = ?
                ORDER BY updated_at DESC, id DESC
                LIMIT 1
                """,
                (sha256,),
            ).fetchone()
        if row is None:
            return None
        return library_item_from_row(row)

    def _library_filter_sql(
        self,
        *,
        kind: LibraryKind | None = None,
        query: str | None = None,
    ) -> tuple[str, list[object]]:
        clauses: list[str] = []
        params: list[object] = []
        if kind:
            clauses.append("kind = ?")
            params.append(kind)
        needle = (query or "").strip()
        if needle:
            clauses.append("(display_name LIKE ? OR original_name LIKE ?)")
            like = f"%{needle}%"
            params.extend([like, like])
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        return where, params

    def count_library_items(
        self,
        *,
        kind: LibraryKind | None = None,
        query: str | None = None,
    ) -> int:
        where, params = self._library_filter_sql(kind=kind, query=query)
        with self._connect() as connection:
            row = connection.execute(
                f"SELECT COUNT(*) AS n FROM library_items {where}",
                params,
            ).fetchone()
        return int(row["n"] if row else 0)

    def list_library_items(
        self,
        *,
        kind: LibraryKind | None = None,
        query: str | None = None,
        page: int = 0,
        per_page: int = 48,
        limit: int | None = None,
    ) -> list[LibraryItem]:
        where, params = self._library_filter_sql(kind=kind, query=query)
        # Legacy `limit` = first page size (used by older callers/tests).
        size = int(limit) if limit is not None else int(per_page)
        capped = max(1, min(size, 500))
        page_value = max(0, int(page))
        offset = page_value * capped
        with self._connect() as connection:
            rows = connection.execute(
                f"""
                SELECT * FROM library_items
                {where}
                ORDER BY updated_at DESC, id DESC
                LIMIT ? OFFSET ?
                """,
                (*params, capped, offset),
            ).fetchall()
        return [library_item_from_row(row) for row in rows]

    def update_library_item_display_name(
        self,
        item_id: str,
        display_name: str,
    ) -> LibraryItem | None:
        normalized = display_name.strip()
        if not normalized:
            raise ValueError("Display name cannot be empty.")
        now = utc_now()
        with self._write_lock, self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE library_items
                SET display_name = ?, updated_at = ?
                WHERE id = ?
                """,
                (normalized, now.isoformat(), item_id),
            )
            if cursor.rowcount == 0:
                return None
        return self.get_library_item(item_id)

    def update_library_item_content(
        self,
        item_id: str,
        *,
        sha256: str,
        bytes_size: int,
        mime: str | None,
        kind: LibraryKind,
    ) -> LibraryItem | None:
        now = utc_now()
        with self._write_lock, self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE library_items
                SET sha256 = ?, bytes = ?, mime = ?, kind = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    sha256,
                    int(bytes_size),
                    mime,
                    kind,
                    now.isoformat(),
                    item_id,
                ),
            )
            if cursor.rowcount == 0:
                return None
        return self.get_library_item(item_id)

    def link_library_item_session(self, item_id: str, session_id: str) -> None:
        with self._write_lock, self._connect() as connection:
            connection.execute(
                """
                INSERT OR IGNORE INTO library_item_sessions(item_id, session_id)
                VALUES (?, ?)
                """,
                (item_id, session_id),
            )

    def count_library_items_for_sha(self, sha256: str) -> int:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT COUNT(*) AS n FROM library_items WHERE sha256 = ?",
                (sha256,),
            ).fetchone()
        return int(row["n"] if row else 0)

    def delete_library_item(self, item_id: str) -> tuple[bool, str | None]:
        """Delete item row. Returns (deleted, sha256_if_no_remaining_refs)."""
        item = self.get_library_item(item_id)
        if item is None:
            return False, None
        with self._write_lock, self._connect() as connection:
            connection.execute(
                "DELETE FROM library_item_sessions WHERE item_id = ?",
                (item_id,),
            )
            connection.execute(
                "DELETE FROM library_items WHERE id = ?",
                (item_id,),
            )
            row = connection.execute(
                "SELECT COUNT(*) AS n FROM library_items WHERE sha256 = ?",
                (item.sha256,),
            ).fetchone()
        remaining = int(row["n"] if row else 0)
        return True, (item.sha256 if remaining == 0 else None)
