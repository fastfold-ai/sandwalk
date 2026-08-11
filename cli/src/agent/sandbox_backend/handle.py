"""Session-scoped ``SandboxHandle`` dataclass and the active-handle registry."""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from agent.sandbox_backend.runtime import _run_modal_blocking
from agent.sandbox_sync import pull_tree, push_paths, push_tree

logger = logging.getLogger(__name__)

_SESSION_LOCK = threading.RLock()
_ACTIVE_SESSIONS: dict[str, SandboxHandle] = {}


@dataclass
class SandboxHandle:
    """Session-scoped backend handle with optional Modal lifecycle helpers."""

    kind: str  # "builtin" | "modal"
    backend: Any
    workspace_root: str
    skills_sources: list[str]
    session_id: str | None = None
    provider_sandbox_name: str | None = None
    modal_sandbox: Any | None = None
    seeded: bool = False
    extras: dict[str, Any] = field(default_factory=dict)

    def pull(self) -> int:
        if self.kind != "modal":
            return 0
        # Prefer the Modal default when wrapped in CompositeBackend.
        target = getattr(self.backend, "default", self.backend)
        return pull_tree(target, self.workspace_root)

    def push(self, relative_paths: list[str] | None = None) -> int:
        if self.kind != "modal":
            return 0
        target = getattr(self.backend, "default", self.backend)
        if relative_paths:
            return push_paths(target, self.workspace_root, relative_paths)
        return push_tree(target, self.workspace_root)

    def terminate(self) -> None:
        if self.kind != "modal" or self.modal_sandbox is None:
            return
        sandbox = self.modal_sandbox
        try:
            _run_modal_blocking(sandbox.terminate)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Modal sandbox terminate failed: %s", exc)


def get_active_handle(session_id: str | None) -> SandboxHandle | None:
    if not session_id:
        return None
    with _SESSION_LOCK:
        return _ACTIVE_SESSIONS.get(session_id)


def register_handle(handle: SandboxHandle) -> None:
    if not handle.session_id:
        return
    with _SESSION_LOCK:
        _ACTIVE_SESSIONS[handle.session_id] = handle


def unregister_handle(session_id: str | None) -> None:
    if not session_id:
        return
    with _SESSION_LOCK:
        _ACTIVE_SESSIONS.pop(session_id, None)


def clear_active_handles() -> None:
    with _SESSION_LOCK:
        _ACTIVE_SESSIONS.clear()


def push_paths_for_session(
    session_id: str | None,
    local_root: str | Path,
    relative_paths: list[str],
) -> int:
    handle = get_active_handle(session_id)
    if handle is None or handle.kind != "modal":
        return 0
    # Prefer the live handle workspace; fall back to caller root.
    root = handle.workspace_root or str(local_root)
    target = getattr(handle.backend, "default", handle.backend)
    return push_paths(target, root, relative_paths)
