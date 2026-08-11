"""Scan the CLI JSONL sessions directory and import everything found."""

from __future__ import annotations

from pathlib import Path

from agent.trajectory import Trajectory
from agent_server.session_sync.core import SyncResult
from agent_server.session_sync.importer import import_trajectory
from agent_server.store import AgentStore


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
