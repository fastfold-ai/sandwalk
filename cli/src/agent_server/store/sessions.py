"""Session creation."""

from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime

from agent_server.models import AgentSession, TitleSource
from agent_server.store.rows import session_from_row
from agent_server.store.util import require_sandbox_backend, utc_now

DEFAULT_SESSION_TITLE = "New research session"


def initial_title_source(title: str | None) -> TitleSource:
    cleaned = (title or "").strip()
    if not cleaned or cleaned == DEFAULT_SESSION_TITLE:
        return "pending"
    return "user"


class SessionCreateMixin:
    """``create_session``/``ensure_session`` — the rest of session CRUD lives in
    :mod:`agent_server.store.session_queries` and
    :mod:`agent_server.store.session_updates`.
    """

    @staticmethod
    def _session(row: sqlite3.Row) -> AgentSession:
        return session_from_row(row)

    def create_session(
        self,
        *,
        title: str | None,
        workspace_path: str | None,
        project_id: str | None = None,
        specialist_id: str | None = None,
        sandbox_backend: str | None = None,
    ) -> AgentSession:
        return self.ensure_session(
            str(uuid.uuid4()),
            title=title,
            workspace_path=workspace_path,
            project_id=project_id,
            specialist_id=specialist_id,
            sandbox_backend=sandbox_backend,
        )

    def ensure_session(
        self,
        session_id: str,
        *,
        title: str | None = None,
        workspace_path: str | None = None,
        project_id: str | None = None,
        specialist_id: str | None = None,
        sandbox_backend: str | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
    ) -> AgentSession:
        normalized_id = str(session_id or "").strip()
        if not normalized_id:
            raise ValueError("Session id cannot be empty.")
        existing = self.get_session(normalized_id)
        if existing is not None:
            # Titles are owned by create/update/auto-title. Workspace boot and
            # CLI ensure paths often pass the default placeholder; never clobber
            # a settled title, and only upgrade while still pending.
            incoming = (title or "").strip()
            if (
                incoming
                and incoming != existing.title
                and existing.title_source == "pending"
                and incoming != DEFAULT_SESSION_TITLE
            ):
                return (
                    self.update_session(
                        normalized_id,
                        title=incoming,
                        title_source="auto",
                    )
                    or existing
                )
            return existing

        if project_id is not None and self.get_project(project_id) is None:
            raise ValueError(f"Project not found: {project_id}")
        if specialist_id is not None and self.get_specialist(specialist_id) is None:
            raise ValueError(f"Specialist not found: {specialist_id}")
        normalized_backend = None
        if sandbox_backend is not None:
            normalized_backend = require_sandbox_backend(sandbox_backend)

        now = utc_now()
        created = created_at or now
        updated = updated_at or created
        resolved_title = (title or DEFAULT_SESSION_TITLE).strip() or DEFAULT_SESSION_TITLE
        session = AgentSession(
            id=normalized_id,
            title=resolved_title,
            title_source=initial_title_source(title),
            status="idle",
            organize_label=None,
            project_id=project_id,
            specialist_id=specialist_id,
            sandbox_backend=normalized_backend,
            workspace_path=workspace_path,
            last_message_at=None,
            created_at=created,
            updated_at=updated,
        )
        with self._write_lock, self._connect() as connection:
            connection.execute(
                """
                INSERT INTO sessions(
                    id, title, title_source, status, organize_label, project_id,
                    specialist_id, sandbox_backend, workspace_path, last_message_at,
                    created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session.id,
                    session.title,
                    session.title_source,
                    session.status,
                    session.organize_label,
                    session.project_id,
                    session.specialist_id,
                    session.sandbox_backend,
                    session.workspace_path,
                    None,
                    session.created_at.isoformat(),
                    session.updated_at.isoformat(),
                ),
            )
        return session
