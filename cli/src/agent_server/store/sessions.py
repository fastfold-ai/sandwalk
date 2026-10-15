"""Session creation."""

from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime

from agent_server.models import AgentSession, TitleSource
from agent_server.store.rows import session_from_row
from agent_server.store.util import require_sandbox_backend, utc_now

DEFAULT_SESSION_TITLE = "New research session"

# Connector / origin values a session row may carry. Mirrors ``SessionSource``
# in ``models/sessions.py`` and the normalizer in ``store/rows.py``.
SESSION_SOURCES = frozenset({"slack", "bench", "capy", "claude", "codex", "opencode", "fx", "hermes"})


def initial_title_source(title: str | None) -> TitleSource:
    """Placeholder create titles stay ``pending`` so auto-title can run later.

    The desktop app historically created sessions as ``Untitled session``. That
    must not be treated as a manual rename (``user``), or auto-title never fires.
    """
    from agent_server.title import is_placeholder_title

    cleaned = (title or "").strip()
    if not cleaned or is_placeholder_title(cleaned):
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
        source: str | None = None,
        source_label: str | None = None,
        client_surface: str | None = None,
        provider: str | None = None,
        model: str | None = None,
        openai_profile_id: str | None = None,
    ) -> AgentSession:
        return self.ensure_session(
            str(uuid.uuid4()),
            title=title,
            workspace_path=workspace_path,
            project_id=project_id,
            specialist_id=specialist_id,
            sandbox_backend=sandbox_backend,
            source=source,
            source_label=source_label,
            client_surface=client_surface,
            provider=provider,
            model=model,
            openai_profile_id=openai_profile_id,
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
        source: str | None = None,
        source_label: str | None = None,
        client_surface: str | None = None,
        provider: str | None = None,
        model: str | None = None,
        openai_profile_id: str | None = None,
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

        normalized_source = (source or "").strip().lower() or None
        if normalized_source is not None and normalized_source not in SESSION_SOURCES:
            raise ValueError(f"source must be one of {', '.join(sorted(SESSION_SOURCES))}")

        from agent_server.store.usage import normalize_surface

        if normalized_source == "slack":
            surface = "slack"
        else:
            surface = normalize_surface(client_surface)

        now = utc_now()
        created = created_at or now
        updated = updated_at or created
        resolved_title = (title or DEFAULT_SESSION_TITLE).strip() or DEFAULT_SESSION_TITLE
        resolved_provider = (provider or "").strip() or None
        resolved_model = (model or "").strip() or None
        resolved_profile = (openai_profile_id or "").strip() or None
        if resolved_provider is None and resolved_model is None:
            from agent.config import Config

            config = Config.load()
            resolved_provider = str(config.get("llm.provider") or "").strip() or None
            resolved_model = str(config.get("llm.model") or "").strip() or None
            resolved_profile = (
                str(config.get("llm.openai_active_profile") or "").strip() or None
            )
        session = AgentSession(
            id=normalized_id,
            title=resolved_title,
            title_source=initial_title_source(title),
            status="idle",
            organize_label=None,
            project_id=project_id,
            specialist_id=specialist_id,
            sandbox_backend=normalized_backend,
            provider=resolved_provider,
            model=resolved_model,
            openai_profile_id=resolved_profile,
            workspace_path=workspace_path,
            source=normalized_source,  # type: ignore[arg-type]
            source_label=(source_label or "").strip() or None,
            client_surface=surface,  # type: ignore[arg-type]
            last_message_at=None,
            created_at=created,
            updated_at=updated,
        )
        with self._write_lock, self._connect() as connection:
            connection.execute(
                """
                INSERT INTO sessions(
                    id, title, title_source, status, organize_label, project_id,
                    specialist_id, sandbox_backend, provider, model,
                    openai_profile_id, workspace_path, source, source_label,
                    client_surface, last_message_at, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    session.provider,
                    session.model,
                    session.openai_profile_id,
                    session.workspace_path,
                    session.source,
                    session.source_label,
                    session.client_surface,
                    None,
                    session.created_at.isoformat(),
                    session.updated_at.isoformat(),
                ),
            )
        # Fan out to the workspace_items index (FAS-107). The tab strip /
        # sidebar / split picker query that table instead of UNIONing per
        # kind. Every chat mutation must keep the mirror row in sync.
        self.upsert_workspace_item(  # type: ignore[attr-defined]
            item_id=session.id,
            kind="chat",
            project_id=session.project_id,
            organize_label=session.organize_label,
            title=session.title,
            updated_at=session.updated_at,
        )
        return session
