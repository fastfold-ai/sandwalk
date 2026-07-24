"""Session mutations: update/workspace/status/delete/touch."""

from __future__ import annotations

from agent_server.models import AgentSession, SessionStatus, TitleSource
from agent_server.store.util import require_sandbox_backend, utc_now


class SessionUpdateMixin:
    def update_session(
        self,
        session_id: str,
        *,
        title: str | None = None,
        title_source: TitleSource | None = None,
        organize_label: str | None = None,
        update_organize_label: bool = False,
        project_id: str | None = None,
        update_project_id: bool = False,
        specialist_id: str | None = None,
        update_specialist_id: bool = False,
        sandbox_backend: str | None = None,
        update_sandbox_backend: bool = False,
    ) -> AgentSession | None:
        current = self.get_session(session_id)
        if current is None:
            return None
        next_title = current.title
        next_title_source = current.title_source
        if title is not None:
            next_title = title.strip()
            if not next_title:
                raise ValueError("Session title cannot be empty.")
            # Explicit source wins; otherwise a title patch from the API is a
            # user rename and must stop further auto-title attempts.
            if title_source is not None:
                next_title_source = title_source
            else:
                next_title_source = "user"
        elif title_source is not None:
            next_title_source = title_source
        next_label = organize_label if update_organize_label else current.organize_label
        next_project_id = current.project_id
        if update_project_id:
            if project_id is not None and self.get_project(project_id) is None:
                raise ValueError(f"Project not found: {project_id}")
            next_project_id = project_id
        next_specialist_id = current.specialist_id
        if update_specialist_id:
            if specialist_id is not None and self.get_specialist(specialist_id) is None:
                raise ValueError(f"Specialist not found: {specialist_id}")
            next_specialist_id = specialist_id
        next_sandbox_backend = current.sandbox_backend
        if update_sandbox_backend:
            if sandbox_backend is not None:
                next_sandbox_backend = require_sandbox_backend(sandbox_backend)
            else:
                next_sandbox_backend = None
        now = utc_now()
        with self._write_lock, self._connect() as connection:
            connection.execute(
                """
                UPDATE sessions
                SET title = ?, title_source = ?, organize_label = ?, project_id = ?,
                    specialist_id = ?, sandbox_backend = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    next_title,
                    next_title_source,
                    next_label,
                    next_project_id,
                    next_specialist_id,
                    next_sandbox_backend,
                    now.isoformat(),
                    session_id,
                ),
            )
        return self.get_session(session_id)

    def set_workspace_path(self, session_id: str, workspace_path: str) -> AgentSession | None:
        with self._write_lock, self._connect() as connection:
            connection.execute(
                "UPDATE sessions SET workspace_path = ?, updated_at = ? WHERE id = ?",
                (workspace_path, utc_now().isoformat(), session_id),
            )
        return self.get_session(session_id)

    def delete_session(self, session_id: str) -> bool:
        with self._write_lock, self._connect() as connection:
            cursor = connection.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
        return cursor.rowcount > 0

    def set_session_status(self, session_id: str, status: SessionStatus) -> AgentSession | None:
        now = utc_now()
        with self._write_lock, self._connect() as connection:
            connection.execute(
                "UPDATE sessions SET status = ?, updated_at = ? WHERE id = ?",
                (status, now.isoformat(), session_id),
            )
        return self.get_session(session_id)

    def touch_session(self, session_id: str) -> AgentSession | None:
        """Bump updated_at + last_message_at so the session sorts as recent in the UI."""
        now = utc_now()
        with self._write_lock, self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE sessions
                SET updated_at = ?, last_message_at = ?
                WHERE id = ?
                """,
                (now.isoformat(), now.isoformat(), session_id),
            )
            if cursor.rowcount <= 0:
                return None
        return self.get_session(session_id)
