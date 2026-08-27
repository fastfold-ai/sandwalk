"""Read-only session lookups: list/get/search."""

from __future__ import annotations

from agent_server.models import AgentSession
from agent_server.store.rows import session_from_row


class SessionQueryMixin:
    def sessions_revision(self) -> str:
        """Compact watermark for list polling — one aggregate row, no payloads.

        Bench sessions are omitted from the global watermark so a live suite
        does not thrash Dashboard polling. Project-scoped lists still include
        them and skip this watermark.
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
                WHERE COALESCE(source, '') NOT IN ('bench', 'capy')
                """
            ).fetchone()
        count, updated_at, running = row[0], row[1], row[2]
        return f"{count}:{updated_at}:{running}"

    def list_sessions(
        self,
        *,
        project_id: str | None = None,
        include_bench: bool | None = None,
        include_hidden: bool = False,
    ) -> list[AgentSession]:
        clauses: list[str] = []
        params: list[str] = []
        if project_id:
            clauses.append("project_id = ?")
            params.append(project_id)
        show_bench = include_bench if include_bench is not None else bool(project_id)
        if not include_hidden:
            if show_bench:
                clauses.append("COALESCE(source, '') != 'capy'")
            else:
                clauses.append("COALESCE(source, '') NOT IN ('bench', 'capy')")
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with self._connect() as connection:
            rows = connection.execute(
                f"""
                SELECT * FROM sessions
                {where}
                ORDER BY updated_at DESC, id DESC
                """,
                params,
            ).fetchall()
        return [session_from_row(row) for row in rows]

    def get_session(self, session_id: str) -> AgentSession | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM sessions WHERE id = ?", (session_id,)
            ).fetchone()
        return session_from_row(row) if row else None

    def get_session_by_source(self, source: str) -> AgentSession | None:
        normalized = (source or "").strip().lower()
        if not normalized:
            return None
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT * FROM sessions
                WHERE source = ?
                ORDER BY updated_at DESC, id DESC
                LIMIT 1
                """,
                (normalized,),
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
                WHERE COALESCE(sessions.source, '') NOT IN ('bench', 'capy')
                  AND (
                    sessions.title LIKE ? ESCAPE '\\'
                    OR messages.content LIKE ? ESCAPE '\\'
                  )
                ORDER BY sessions.updated_at DESC, sessions.id DESC
                LIMIT ?
                """,
                (f"%{normalized}%", f"%{normalized}%", max(1, min(limit, 100))),
            ).fetchall()
        return [session_from_row(row) for row in rows]
