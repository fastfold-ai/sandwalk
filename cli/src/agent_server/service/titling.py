"""Auto-title generation for sessions still carrying a placeholder title."""

from __future__ import annotations

from agent_server.models import AgentSession


class _TitlingMixin:
    @staticmethod
    def _should_auto_title(title: str | None) -> bool:
        from agent_server.title import is_placeholder_title

        return is_placeholder_title(title)

    def auto_title_session(self, session_id: str, *, force: bool = False) -> AgentSession:
        session = self.store.get_session(session_id)
        if session is None:
            raise KeyError(session_id)
        if not force and not self._should_auto_title(session.title):
            return session

        from agent_server.title import generate_session_title

        messages = [
            {"role": message.role, "content": message.content}
            for message in self.store.list_messages(session_id)
        ]
        fallback = next(
            (
                message.content
                for message in self.store.list_messages(session_id)
                if message.role == "user" and str(message.content or "").strip()
            ),
            None,
        )
        title = generate_session_title(messages, fallback_query=fallback)
        if not title:
            return session
        updated = self.store.update_session(session_id, title=title)
        if updated is None:
            raise KeyError(session_id)
        return updated
