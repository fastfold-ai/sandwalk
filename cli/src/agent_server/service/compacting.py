"""Session context compaction for longer agent runs."""

from __future__ import annotations

from agent_server.models import CompactSessionResponse
from agent_server.service.lifecycle import SessionBusyError


class _CompactingMixin:
    def compact_session(
        self,
        session_id: str,
        *,
        instructions: str | None = None,
    ) -> CompactSessionResponse:
        """Summarize older turns into one summary pair + keep the last turn.

        Mirrors the CLI ``/compact`` behavior so the next planner call sees a
        shorter history. Refuses while a run is active.
        """
        session = self.store.get_session(session_id)
        if session is None:
            raise KeyError(session_id)

        task = self._active_runs.get(session_id)
        if task is not None and not task.done():
            raise SessionBusyError("Session is busy; wait for the run to finish.")
        if session.status in {"running", "awaiting_approval"}:
            raise SessionBusyError("Session is busy; wait for the run to finish.")

        messages = self.store.list_messages(session_id)
        turns: list[tuple[str, str]] = []
        pending_user: str | None = None
        for message in messages:
            if message.role == "user":
                pending_user = message.content
            elif message.role == "assistant" and pending_user is not None:
                turns.append((pending_user, message.content))
                pending_user = None

        before = len(turns)
        if before <= 2:
            raise ValueError("Session too short to compact (need more than 2 turns).")

        older = turns[:-1]
        last_query, last_answer = turns[-1]
        context_lines = []
        for index, (query, answer) in enumerate(older, 1):
            context_lines.append(
                f"**Turn {index}**: {query[:200]}\n"
                f"  Finding: {answer[:1400]}"
            )
        context = "\n\n".join(context_lines)
        focus = f"\nFocus: {instructions}" if instructions else ""
        prompt = (
            "Summarize this research session into a brief paragraph that preserves "
            "key findings, entities, and conclusions. Be specific about results "
            f"and numbers.{focus}\n\n{context}"
        )

        from agent.config import Config
        from agent.session import Session

        llm = Session(config=Config.load(), verbose=False, mode="batch").get_llm()
        response = llm.chat(
            system=(
                "You are a research session summarizer. "
                "Be concise but preserve specific results."
            ),
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=1200,
        )
        summary = response.content if hasattr(response, "content") else str(response)
        if not str(summary).strip():
            raise ValueError("Summarizer returned empty output")

        self.store.clear_messages(session_id)
        self.store.add_message(
            session_id=session_id,
            role="user",
            content="[session summary]",
        )
        self.store.add_message(
            session_id=session_id,
            role="assistant",
            content=str(summary).strip(),
        )
        self.store.add_message(session_id=session_id, role="user", content=last_query)
        self.store.add_message(
            session_id=session_id,
            role="assistant",
            content=last_answer,
        )

        refreshed = self.store.get_session(session_id)
        if refreshed is not None:
            self.store.append_event(
                session_id=session_id,
                event_type="session.updated",
                payload={
                    "session": refreshed.model_dump(mode="json", by_alias=True)
                },
            )
        return CompactSessionResponse(
            turns_before=before,
            turns_after=2,
            summary=str(summary).strip(),
        )
