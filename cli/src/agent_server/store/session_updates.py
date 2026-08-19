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
        provider: str | None = None,
        model: str | None = None,
        openai_profile_id: str | None = None,
        update_llm: bool = False,
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
        next_provider = current.provider
        next_model = current.model
        next_profile = current.openai_profile_id
        if update_llm:
            # Explicit None from clear_llm wipes all three; otherwise patch only
            # the fields the caller provided (None means leave unchanged).
            if provider is None and model is None and openai_profile_id is None:
                next_provider = None
                next_model = None
                next_profile = None
            else:
                if provider is not None:
                    next_provider = provider.strip() or None
                if model is not None:
                    next_model = model.strip() or None
                if openai_profile_id is not None:
                    next_profile = openai_profile_id.strip() or None
        now = utc_now()
        with self._write_lock, self._connect() as connection:
            connection.execute(
                """
                UPDATE sessions
                SET title = ?, title_source = ?, organize_label = ?, project_id = ?,
                    specialist_id = ?, sandbox_backend = ?, provider = ?, model = ?,
                    openai_profile_id = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    next_title,
                    next_title_source,
                    next_label,
                    next_project_id,
                    next_specialist_id,
                    next_sandbox_backend,
                    next_provider,
                    next_model,
                    next_profile,
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
        session = self.get_session(session_id)
        if session is not None and getattr(session, "source", None) not in {
            "bench",
            "capy",
        }:
            # Push the transition on the global session bus so subscribers
            # (frontend `useGlobalSessionEvents`) can react without diffing
            # snapshots from a poll. Import lazily to avoid a circular
            # dependency between the store and the app-level bus.
            # Bench cells are omitted so live MMLU (etc.) do not leak into All.
            from agent_server.session_event_bus import (  # noqa: PLC0415
                SessionEventType,
                session_event_bus,
            )

            session_event_bus.publish(
                SessionEventType.SESSION_STATUS_CHANGED,
                {
                    "sessionId": session_id,
                    "status": status,
                    "session": session.model_dump(mode="json", by_alias=True),
                },
            )
        return session

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
