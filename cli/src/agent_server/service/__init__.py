"""Application service for durable agent sessions and runs.

Split package — re-exports the public surface previously defined in
``agent_server/service.py`` so existing imports and monkeypatches
(``agent_server.service.CONFIG_DIR``) keep working.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from agent.config import CONFIG_DIR
from agent_server.service.compacting import _CompactingMixin
from agent_server.service.lifecycle import SessionBusyError, _LifecycleMixin
from agent_server.service.run_pipeline import _RunPipelineMixin
from agent_server.service.sessions_crud import _SessionCrudMixin
from agent_server.service.titling import _TitlingMixin
from agent_server.store import AgentStore

logger = logging.getLogger("agent_server")

__all__ = [
    "AgentService",
    "SessionBusyError",
    "default_workspace_path",
    "prepare_workspace_dir",
    "resolve_session_workspace",
]


def default_workspace_path(session_id: str) -> Path:
    """Canonical per-session workspace root used by the agent server and UI."""
    return (CONFIG_DIR / "workspaces" / session_id).resolve()


def prepare_workspace_dir(workspace: Path) -> Path:
    """Create the standard session workspace subdirs and return the resolved root."""
    root = workspace.expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    (root / "uploads").mkdir(parents=True, exist_ok=True)
    (root / "outputs").mkdir(parents=True, exist_ok=True)
    (root / "artifacts").mkdir(parents=True, exist_ok=True)
    return root


def resolve_session_workspace(
    session_id: str,
    *,
    store: AgentStore | None = None,
    persist: bool = True,
) -> Path:
    """Resolve (and optionally persist) the writable workspace for a session id.

    Used by both the agent server and the CLI AgentLoop so shell/skills always
    have ``SANDWALK_SESSION_WORKSPACE`` and never expand to ``/artifacts/...``.
    """
    normalized = str(session_id or "").strip()
    if not normalized:
        raise ValueError("Session id cannot be empty.")

    existing_path: str | None = None
    if store is not None:
        try:
            session = store.get_session(normalized)
        except Exception:
            session = None
        if session is not None and session.workspace_path:
            existing_path = str(session.workspace_path).strip() or None

    workspace = (
        Path(existing_path).expanduser().resolve()
        if existing_path
        else default_workspace_path(normalized)
    )
    workspace = prepare_workspace_dir(workspace)

    if persist and store is not None:
        try:
            store.ensure_session(normalized)
            if not existing_path or Path(existing_path).expanduser().resolve() != workspace:
                store.set_workspace_path(normalized, str(workspace))
        except Exception:
            logger.exception(
                "Failed to persist session workspace path",
                extra={"session_id": normalized},
            )
    return workspace


class AgentService(
    _SessionCrudMixin,
    _TitlingMixin,
    _CompactingMixin,
    _LifecycleMixin,
    _RunPipelineMixin,
):
    """Owns active runs while delegating persistence to :class:`AgentStore`."""

    def __init__(self, store: AgentStore) -> None:
        self.store = store
        self._active_runs: dict[str, asyncio.Task[None]] = {}
        self._run_ids: dict[str, str] = {}
        # Live AgentRunner instances (worker threads) for real Stop/interrupt.
        self._active_runners: dict[str, object] = {}
