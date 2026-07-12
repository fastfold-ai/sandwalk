"""Import legacy CLI JSONL sessions into the shared AgentStore (SQLite)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from agent.trajectory import Trajectory
from agent_server.store import AgentStore


@dataclass
class SyncResult:
    scanned: int = 0
    imported: int = 0
    updated: int = 0
    skipped: int = 0
    failed: int = 0
    details: list[str] | None = None

    def __post_init__(self) -> None:
        if self.details is None:
            self.details = []


def _timestamp_to_datetime(value: object) -> datetime:
    if isinstance(value, (int, float)) and value > 0:
        return datetime.fromtimestamp(float(value), tz=UTC)
    if isinstance(value, str) and value.strip():
        try:
            parsed = datetime.fromisoformat(value.strip())
            if parsed.tzinfo is None:
                return parsed.replace(tzinfo=UTC)
            return parsed
        except ValueError:
            pass
    return datetime.now(UTC)


def import_trajectory(
    store: AgentStore,
    trajectory: Trajectory,
    *,
    force: bool = False,
) -> str:
    """Import one trajectory into SQLite.

    Returns one of: imported | updated | skipped.
    """
    session_id = str(trajectory.session_id or "").strip()
    if not session_id:
        raise ValueError("Trajectory is missing session_id.")

    title = (trajectory.title or "").strip() or f"CLI session {session_id}"
    created_at = _timestamp_to_datetime(trajectory.created_at)
    updated_at = _timestamp_to_datetime(trajectory.updated_at or trajectory.created_at)

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
        base = _timestamp_to_datetime(turn.timestamp)
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
    return action


def sync_jsonl_sessions(
    store: AgentStore | None = None,
    *,
    sessions_dir: Path | None = None,
    force: bool = False,
) -> SyncResult:
    """Scan CLI JSONL sessions and import them into the shared SQLite store."""
    result = SyncResult()
    agent_store = store or AgentStore()
    root = sessions_dir or Trajectory.sessions_dir()
    paths = sorted(root.glob("*.jsonl"))
    # Ignore trace files if they ever share the directory naming.
    paths = [path for path in paths if not path.name.endswith(".trace.jsonl")]
    result.scanned = len(paths)

    for path in paths:
        try:
            trajectory = Trajectory.load(path)
            if not trajectory.session_id:
                trajectory.session_id = path.stem
            if not trajectory.turns:
                result.skipped += 1
                result.details.append(f"{path.stem}: skipped (empty)")
                continue
            action = import_trajectory(agent_store, trajectory, force=force)
            if action == "imported":
                result.imported += 1
            elif action == "updated":
                result.updated += 1
            else:
                result.skipped += 1
            result.details.append(f"{trajectory.session_id}: {action}")
        except Exception as exc:  # noqa: BLE001 - collect per-file failures
            result.failed += 1
            result.details.append(f"{path.name}: failed ({exc})")

    return result
