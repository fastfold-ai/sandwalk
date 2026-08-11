"""
AgentLoop: wraps AgentRunner with trajectory persistence and clarification.

Provides the ``AgentLoop`` class used by the interactive terminal for
multi-turn sessions with memory, and ``ClarificationNeeded`` for requesting
additional input from the user.
"""

import logging
import uuid

from agent.loop.clarification import Clarification, ClarificationNeeded
from agent.loop.progress import LoopProgressMixin
from agent.loop.run import LoopRunMixin
from agent.loop.state import LoopStateMixin
from agent.runner import AgentRunner
from agent.trace_store import TraceStore
from agent.trajectory import Trajectory
from agent_server.session_sync import export_store_to_trajectory, import_trajectory
from agent_server.store import AgentStore

__all__ = ["AgentLoop", "Clarification", "ClarificationNeeded"]

logger = logging.getLogger("loop")


class AgentLoop(LoopRunMixin, LoopProgressMixin, LoopStateMixin):
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
        # Prefer shared SQLite when the session continued in the web UI (or any
        # other surface that writes messages there) so CLI resume shows that
        # history. Then backfill SQLite from JSONL when the store is behind.
        try:
            export_store_to_trajectory(agent_store, loop.trajectory)
        except Exception:
            logger.exception(
                "Failed to sync shared store history into CLI trajectory",
                extra={"session_id": loop.trajectory.session_id},
            )
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
