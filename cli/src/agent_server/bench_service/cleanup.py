"""Delete bench projects and all related session/chat data."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def delete_bench_project_data(store: Any, project_id: str | None) -> int:
    """Delete every session under ``project_id``, then the project.

    Returns the number of sessions deleted. Safe no-op when id is missing.
    """
    if not project_id:
        return 0
    sessions = []
    try:
        sessions = store.list_sessions(project_id=project_id, include_bench=True)
    except Exception as exc:  # noqa: BLE001
        logger.warning("list sessions for bench project %s failed: %s", project_id, exc)
        return 0
    deleted = 0
    for session in sessions:
        sid = getattr(session, "id", None) or (
            session.get("id") if isinstance(session, dict) else None
        )
        if not sid:
            continue
        try:
            if store.delete_session(str(sid)):
                deleted += 1
        except Exception as exc:  # noqa: BLE001
            logger.warning("delete bench session %s failed: %s", sid, exc)
    try:
        store.delete_project(str(project_id))
    except Exception as exc:  # noqa: BLE001
        logger.warning("delete bench project %s failed: %s", project_id, exc)
    return deleted
