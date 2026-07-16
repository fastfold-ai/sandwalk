"""Export shared AgentStore history back into a CLI JSONL trajectory."""

from __future__ import annotations

import time

from agent.trajectory import Trajectory
from agent_server.session_sync.core import messages_to_turns
from agent_server.store import AgentStore


def export_store_to_trajectory(
    store: AgentStore,
    trajectory: Trajectory,
) -> str:
    """Pull newer UI/shared-store history into a CLI JSONL trajectory.

    Returns one of: updated | skipped.
    """
    session_id = str(trajectory.session_id or "").strip()
    if not session_id:
        raise ValueError("Trajectory is missing session_id.")

    existing = store.get_session(session_id)
    if existing is None:
        return "skipped"

    store_turns = messages_to_turns(store.list_messages(session_id))
    if len(store_turns) <= len(trajectory.turns):
        return "skipped"

    # Shared SQLite is the cross-surface source of truth when it is ahead of
    # the CLI JSONL (e.g. session continued in the web UI).
    trajectory.turns = []
    # Avoid silently dropping UI history when it exceeds the default window.
    if len(store_turns) > int(trajectory.max_turns or 0):
        trajectory.max_turns = len(store_turns)
    for query, answer in store_turns:
        trajectory.add_turn(query, answer)

    title = (existing.title or "").strip()
    if title:
        trajectory.title = title
    trajectory.updated_at = time.time()
    try:
        trajectory.save()
    except Exception:
        # Resume can still use the in-memory turns even if JSONL write fails.
        pass
    return "updated"
