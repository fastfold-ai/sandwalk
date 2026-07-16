"""Shared-session and workspace bookkeeping for AgentLoop."""

import logging
from datetime import UTC, datetime

logger = logging.getLogger("loop")


class LoopStateMixin:
    """Owns session workspace resolution and turn persistence into AgentStore."""

    def _ensure_shared_session(self) -> None:
        session_id = str(self.trajectory.session_id or "").strip()
        if not session_id:
            return
        title = (self.trajectory.title or "").strip()
        if title:
            self.store.ensure_session(session_id, title=title)
        else:
            self.store.ensure_session(session_id)
        # Always materialize a session workspace so CLI shell/skills get
        # SANDWALK_SESSION_WORKSPACE (same path the local UI file tree uses).
        try:
            from agent_server.service import resolve_session_workspace

            resolve_session_workspace(session_id, store=self.store, persist=True)
        except Exception:
            logger.exception(
                "Failed to ensure CLI session workspace",
                extra={"session_id": session_id},
            )

    def ensure_workspace_path(self) -> str | None:
        """Return the absolute session workspace path, creating it if needed."""
        session_id = str(self.trajectory.session_id or "").strip()
        if not session_id:
            return None
        try:
            from agent_server.service import resolve_session_workspace

            return str(
                resolve_session_workspace(session_id, store=self.store, persist=True)
            )
        except Exception:
            logger.exception(
                "Failed to resolve CLI session workspace",
                extra={"session_id": session_id},
            )
            return None

    def _persist_turn_to_store(
        self,
        query: str,
        answer: str,
        *,
        run_id: str | None = None,
        user_message_id: str | None = None,
    ) -> None:
        session_id = str(self.trajectory.session_id or "").strip()
        if not session_id:
            return
        title = (self.trajectory.title or "").strip() or query.strip()[:80] or "New research session"
        self.store.ensure_session(session_id, title=title)
        if self.trajectory.title:
            self.store.update_session(session_id, title=self.trajectory.title)
        now = datetime.now(UTC)
        if not user_message_id:
            self.store.add_message(
                session_id=session_id,
                role="user",
                content=query,
                created_at=now,
            )
        assistant_message = self.store.add_message(
            session_id=session_id,
            role="assistant",
            content=answer,
            created_at=datetime.fromtimestamp(now.timestamp() + 0.001, tz=UTC),
        )
        if run_id:
            self.store.append_event(
                session_id=session_id,
                run_id=run_id,
                event_type="assistant.message",
                payload={
                    "message": assistant_message.model_dump(
                        mode="json", by_alias=True
                    )
                },
            )
            self.store.append_event(
                session_id=session_id,
                run_id=run_id,
                event_type="run.completed",
                payload={"messageId": assistant_message.id},
            )
        self.store.set_session_status(session_id, "idle")
