"""Read-only session lookups: list/get/search."""

from __future__ import annotations

from agent_server.models import AgentSession
from agent_server.store.rows import session_from_row


class SessionQueryMixin:
    def sessions_revision(self) -> str:
        """Compact watermark for list polling — one aggregate row, no payloads.

        Bench sessions are excluded so multi-worker benches do not thrash the
        sidebar revision poll.
        """
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT COUNT(*),
                       COALESCE(MAX(updated_at), ''),
                       COALESCE(
                         SUM(CASE WHEN status = 'running' THEN 1 ELSE 0 END),
                         0
                       )
                FROM sessions
                WHERE COALESCE(source, '') != 'bench'
                """
            ).fetchone()
        count, updated_at, running = row[0], row[1], row[2]
        return f"{count}:{updated_at}:{running}"

    def list_sessions(
        self,
        *,
        project_id: str | None = None,
        include_bench: bool = False,
    ) -> list[AgentSession]:
        with self._connect() as connection:
            if project_id:
                rows = connection.execute(
                    """
                    SELECT * FROM sessions
                    WHERE project_id = ?
                    ORDER BY updated_at DESC, id DESC
                    """,
                    (project_id,),
                ).fetchall()
            elif include_bench:
                rows = connection.execute(
                    "SELECT * FROM sessions ORDER BY updated_at DESC, id DESC"
                ).fetchall()
            else:
                rows = connection.execute(
                    """
                    SELECT * FROM sessions
                    WHERE COALESCE(source, '') != 'bench'
                    ORDER BY updated_at DESC, id DESC
                    """
                ).fetchall()
        return [session_from_row(row) for row in rows]

    def get_session(self, session_id: str) -> AgentSession | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM sessions WHERE id = ?", (session_id,)
            ).fetchone()
        return session_from_row(row) if row else None

    def list_sessions_by_ids(self, ids: list[str]) -> list[AgentSession]:
        """Bulk metadata fetch for a specific set of session ids.

        Used to hydrate the frontend cache with sessions that live outside
        the current project scope but appear inside cross-project split
        groups (`grp_*` in localStorage). Silently skips ids that do not
        resolve to a real row so a stale group doesn't break the response.
        """
        cleaned = [i for i in ids if i]
        if not cleaned:
            return []
        placeholders = ",".join("?" for _ in cleaned)
        with self._connect() as connection:
            rows = connection.execute(
                f"SELECT * FROM sessions WHERE id IN ({placeholders})",
                cleaned,
            ).fetchall()
        return [session_from_row(row) for row in rows]

    def search_sessions(self, query: str, *, limit: int = 50) -> list[AgentSession]:
        normalized = query.strip()
        if not normalized:
            return self.list_sessions()[:limit]
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT DISTINCT sessions.*
                FROM sessions
                LEFT JOIN messages ON messages.session_id = sessions.id
                WHERE sessions.title LIKE ? ESCAPE '\\'
                   OR messages.content LIKE ? ESCAPE '\\'
                ORDER BY sessions.updated_at DESC, sessions.id DESC
                LIMIT ?
                """,
                (f"%{normalized}%", f"%{normalized}%", max(1, min(limit, 100))),
            ).fetchall()
        return [session_from_row(row) for row in rows]
