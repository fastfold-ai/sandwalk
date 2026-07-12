"""
AgentLoop: wraps AgentRunner with trajectory persistence and clarification.

Provides the ``AgentLoop`` class used by the interactive terminal for
multi-turn sessions with memory, and ``ClarificationNeeded`` for requesting
additional input from the user.
"""

import logging
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime

from agent.runner import AgentRunner
from agent.trace_store import TraceStore
from agent.trajectory import Trajectory
from agent_server.session_sync import import_trajectory
from agent_server.store import AgentStore

logger = logging.getLogger("loop")


@dataclass
class Clarification:
    """A request for user clarification before executing a query."""
    question: str
    missing: list[str] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)


class ClarificationNeeded(Exception):
    """Raised when the planner needs additional information."""

    def __init__(self, clarification: Clarification):
        self.clarification = clarification
        super().__init__(clarification.question)


class AgentLoop:
    """Multi-turn agent loop with trajectory memory.

    Wraps ``AgentRunner`` (SDK-based) and maintains a ``Trajectory``
    for multi-turn session context. Also dual-writes turns into the shared
    SQLite ``AgentStore`` so CLI sessions appear in the local web UI.
    """

    def __init__(self, session, evidence_board=None, thread_id: int = 0,
                 headless: bool = False, store: AgentStore | None = None,
                 session_id: str | None = None):
        self.session = session
        self.evidence_board = evidence_board
        self.thread_id = thread_id
        self.headless = headless
        self.store = store or AgentStore()
        resolved_id = str(session_id or "").strip() or str(uuid.uuid4())[:8]
        self.trajectory = Trajectory(session_id=resolved_id)
        self.trajectory.model = session.current_model
        self.trace_store = TraceStore(session_id=resolved_id)
        self._runner = AgentRunner(
            session, trajectory=self.trajectory, trace_store=self.trace_store,
        )
        self._ensure_shared_session()

    def _ensure_shared_session(self) -> None:
        session_id = str(self.trajectory.session_id or "").strip()
        if not session_id:
            return
        title = (self.trajectory.title or "").strip() or "New research session"
        self.store.ensure_session(session_id, title=title)

    def _persist_turn_to_store(self, query: str, answer: str) -> None:
        session_id = str(self.trajectory.session_id or "").strip()
        if not session_id:
            return
        title = (self.trajectory.title or "").strip() or query.strip()[:80] or "New research session"
        self.store.ensure_session(session_id, title=title)
        if self.trajectory.title:
            self.store.update_session(session_id, title=self.trajectory.title)
        now = datetime.now(UTC)
        self.store.add_message(
            session_id=session_id,
            role="user",
            content=query,
            created_at=now,
        )
        self.store.add_message(
            session_id=session_id,
            role="assistant",
            content=answer,
            created_at=datetime.fromtimestamp(now.timestamp() + 0.001, tz=UTC),
        )
        self.store.set_session_status(session_id, "idle")

    def run(self, query: str, context: dict | None = None,
            progress_callback=None):
        """Execute a query and record it in the trajectory."""
        result = self._runner.run(query, context, progress_callback=progress_callback)

        # Check for clarification request in result
        if result and result.raw_results:
            clar_data = result.raw_results.get("clarification")
            if isinstance(clar_data, dict) and clar_data.get("clarification_needed"):
                raise ClarificationNeeded(Clarification(
                    question=clar_data.get("question", "Could you clarify?"),
                    missing=clar_data.get("missing", []),
                    suggestions=clar_data.get("suggestions", []),
                ))

        # Record turn in trajectory
        if result:
            self.trajectory.add_turn(
                query=query,
                answer=result.summary or "",
                plan=result.plan,
            )
            if not self.trajectory.title or self._is_placeholder_title(
                self.trajectory.title
            ):
                self.trajectory.title = self._generate_title(
                    query, result.summary or ""
                )
            self.trajectory.model = self.session.current_model
            self.trajectory.save()
            try:
                self._persist_turn_to_store(query, result.summary or "")
            except Exception:
                logger.exception(
                    "Failed to dual-write CLI turn into shared AgentStore",
                    extra={"session_id": self.trajectory.session_id},
                )

        return result

    @staticmethod
    def _is_placeholder_title(title: str | None) -> bool:
        from agent_server.title import is_placeholder_title

        return is_placeholder_title(title)

    def _generate_title(self, query: str, answer: str) -> str:
        from agent_server.title import fallback_title_from_query, generate_session_title

        messages = [
            {"role": "user", "content": query},
            {"role": "assistant", "content": answer},
        ]
        return generate_session_title(messages, fallback_query=query) or (
            fallback_title_from_query(query) or "New research session"
        )

    @classmethod
    def resume(cls, session, session_id: str, store: AgentStore | None = None):
        """Resume a saved session by ID (JSONL and/or shared SQLite store)."""
        normalized_id = str(session_id or "").strip()
        if not normalized_id:
            raise FileNotFoundError("No session id provided.")

        agent_store = store or AgentStore()
        trajectory: Trajectory | None = None
        try:
            session_path = Trajectory.resolve_session_path(normalized_id)
            trajectory = Trajectory.load(session_path)
        except FileNotFoundError:
            trajectory = None

        if trajectory is None:
            shared = agent_store.get_session(normalized_id)
            if shared is None:
                # Allow prefix match against SQLite ids.
                matches = [
                    item
                    for item in agent_store.list_sessions()
                    if item.id.startswith(normalized_id)
                ]
                if len(matches) == 1:
                    shared = matches[0]
                    normalized_id = shared.id
                elif len(matches) > 1:
                    raise FileNotFoundError(
                        f"Session prefix '{normalized_id}' is ambiguous in the shared store."
                    )
                else:
                    raise FileNotFoundError(f"Session '{normalized_id}' not found.")
            messages = agent_store.list_messages(shared.id)
            trajectory = Trajectory(
                session_id=shared.id,
                title=shared.title,
            )
            pending_user: str | None = None
            for message in messages:
                if message.role == "user":
                    pending_user = message.content
                elif message.role == "assistant" and pending_user is not None:
                    trajectory.add_turn(pending_user, message.content)
                    pending_user = None

        loop = cls(
            session,
            store=agent_store,
            session_id=trajectory.session_id or normalized_id,
        )
        loop.trajectory = trajectory
        if not loop.trajectory.session_id:
            loop.trajectory.session_id = normalized_id
        loop.trace_store = TraceStore(session_id=loop.trajectory.session_id)
        loop._runner = AgentRunner(
            session, trajectory=trajectory, trace_store=loop.trace_store,
        )
        loop._ensure_shared_session()
        # Keep SQLite in sync when resuming a JSONL-only legacy session.
        try:
            import_trajectory(agent_store, loop.trajectory, force=False)
        except Exception:
            logger.exception(
                "Failed to sync resumed CLI session into shared store",
                extra={"session_id": loop.trajectory.session_id},
            )
        return loop

    @classmethod
    def resume_latest(cls, session, store: AgentStore | None = None):
        """Resume the most recent saved session."""
        sessions = Trajectory.list_sessions()
        if sessions:
            latest = sessions[0]
            return cls.resume(session, latest["session_id"], store=store)
        agent_store = store or AgentStore()
        shared = agent_store.list_sessions()
        if not shared:
            raise FileNotFoundError("No saved sessions found.")
        return cls.resume(session, shared[0].id, store=agent_store)
