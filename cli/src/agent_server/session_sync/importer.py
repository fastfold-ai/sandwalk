"""Import a single CLI JSONL trajectory into the shared AgentStore."""

from __future__ import annotations

from datetime import UTC, datetime

from agent.trajectory import Trajectory
from agent_server.session_sync.core import timestamp_to_datetime
from agent_server.store import AgentStore


def import_trajectory(
    store: AgentStore,
    trajectory: Trajectory,
    *,
    force: bool = False,
    mark_recent: bool = False,
) -> str:
    """Import one trajectory into SQLite.

    Returns one of: imported | updated | skipped.

    When ``mark_recent`` is True (e.g. cloud forks), bump session activity
    timestamps to now so the chat sorts to the top of the Web UI list even
    though message history keeps its original times.
    """
    session_id = str(trajectory.session_id or "").strip()
    if not session_id:
        raise ValueError("Trajectory is missing session_id.")

    title = (trajectory.title or "").strip() or f"CLI session {session_id}"
    created_at = timestamp_to_datetime(trajectory.created_at)
    updated_at = timestamp_to_datetime(trajectory.updated_at or trajectory.created_at)
    if mark_recent:
        updated_at = datetime.now(UTC)

    existing = store.get_session(session_id)
    existing_messages = store.list_messages(session_id) if existing else []
    expected_count = len(trajectory.turns) * 2

    if existing and existing_messages and not force:
        if len(existing_messages) >= expected_count and expected_count > 0:
            return "skipped"

    store.ensure_session(
        session_id,
        title=title,
        created_at=created_at,
        updated_at=updated_at,
    )
    from agent_server.service import AgentService

    AgentService(store).ensure_workspace(session_id)

    action = "imported"
    if existing_messages:
        store.clear_messages(session_id)
        action = "updated"

    for index, turn in enumerate(trajectory.turns):
        base = timestamp_to_datetime(turn.timestamp)
        # Guarantee stable user→assistant ordering even when turn timestamps collide.
        user_ts = datetime.fromtimestamp(base.timestamp() + (index * 2), tz=UTC)
        assistant_ts = datetime.fromtimestamp(base.timestamp() + (index * 2) + 1, tz=UTC)
        store.add_message(
            session_id=session_id,
            role="user",
            content=turn.query,
            created_at=user_ts,
            message_id=f"{session_id}-turn-{index:04d}-0-user",
        )
        store.add_message(
            session_id=session_id,
            role="assistant",
            content=turn.answer,
            created_at=assistant_ts,
            message_id=f"{session_id}-turn-{index:04d}-1-assistant",
        )

    store.update_session(session_id, title=title)
    store.set_session_status(session_id, "idle")
    if mark_recent:
        # add_message stamps last_message_at from historical turns — refresh so
        # the UI "Today" / recent sort treats the fork as newly added.
        store.touch_session(session_id)
    return action
