"""Auto-title generation for sessions still marked ``title_source=pending``."""

from __future__ import annotations

from agent_server.models import AgentSession


class _TitlingMixin:
    @staticmethod
    def _should_auto_title(session: AgentSession | None) -> bool:
        return bool(session is not None and session.title_source == "pending")

    def auto_title_session(self, session_id: str, *, force: bool = False) -> AgentSession:
        """Generate a title while ``title_source`` is still ``pending``.

        ``force`` only lowers the message-count gate for the LLM call; it does
        not override a settled ``auto``/``user`` title.
        """
        session = self.store.get_session(session_id)
        if session is None:
            raise KeyError(session_id)
        if not self._should_auto_title(session):
            return session

        from agent_server.title import (
            TitleResult,
            fallback_title_from_query,
            first_user_content,
            generate_session_title,
            should_attempt_llm_title,
        )

        messages = [
            {"role": message.role, "content": message.content}
            for message in self.store.list_messages(session_id)
        ]
        fallback = first_user_content(messages)
        if should_attempt_llm_title(messages, force=force):
            result = generate_session_title(messages, fallback_query=fallback)
        else:
            # Too early for a model call — readable interim title, stay pending.
            result = TitleResult(
                title=fallback_title_from_query(fallback),
                final=False,
            )
        if not result.title:
            return session
        updated = self.store.update_session(
            session_id,
            title=result.title,
            title_source="auto" if result.final else "pending",
        )
        if updated is None:
            raise KeyError(session_id)
        return updated
