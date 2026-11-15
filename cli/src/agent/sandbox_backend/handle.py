"""Session-scoped ``SandboxHandle`` dataclass and the active-handle registry."""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from agent.sandbox_backend.activity import SandboxActivity
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
    # Wall-clock time this server attached to the sandbox. Uptime in the UI
    # counts from here, so it survives leaving and reopening the chat.
    started_at: float = field(default_factory=time.time)

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


# Modal ends a sandbox on its idle timeout or time limit without telling us.
# Status reads ask Modal, at most once per this many seconds per sandbox.
_LIVENESS_TTL_SECONDS = 15.0
_FINISHED_ERRORS = {"NotFoundError", "SandboxTerminatedError", "SandboxTimeoutError"}


def modal_sandbox_finished(handle: SandboxHandle) -> bool | None:
    """Ask Modal whether this sandbox has ended.

    ``True`` when Modal reports it finished, ``False`` when it is running,
    ``None`` when Modal could not be reached (keep the last known state).
    """
    sandbox = getattr(handle, "modal_sandbox", None)
    extras = getattr(handle, "extras", None)
    if handle.kind != "modal" or sandbox is None or not isinstance(extras, dict):
        return None
    checked_at = extras.get("liveness_checked_at")
    if (
        isinstance(checked_at, float)
        and time.monotonic() - checked_at < _LIVENESS_TTL_SECONDS
    ):
        return extras.get("liveness_finished")
    finished: bool | None
    exit_code: int | None = None
    try:
        exit_code = _run_modal_blocking(sandbox.poll)
        finished = exit_code is not None
    except Exception as exc:  # noqa: BLE001 - offline must not look like "stopped"
        finished = True if type(exc).__name__ in _FINISHED_ERRORS else None
    extras["liveness_checked_at"] = time.monotonic()
    extras["liveness_finished"] = finished
    extras["exit_code"] = exit_code
    return finished


@dataclass(frozen=True)
class SandboxStop:
    """Why and when a sandbox ended without the user stopping it."""

    stopped_at: float
    # "idle" | "time_limit" | "timeout" | "ended"
    reason: str
    idle_timeout_seconds: int | None = None
    max_lifetime_seconds: int | None = None


# Modal reports that a sandbox finished, not when. A status read can come long
# after the fact (the chat was closed), so the stop time is worked out from the
# deadline that passed. A deadline this close to now still counts as passed.
_STOP_DEADLINE_SLACK_SECONDS = 60.0
_LAST_STOPS: dict[str, SandboxStop] = {}


def _positive_int(value: Any) -> int | None:
    return int(value) if isinstance(value, (int, float)) and value > 0 else None


def record_sandbox_stop(handle: SandboxHandle) -> SandboxStop | None:
    """Remember that Modal ended this session's sandbox, and the likely cause."""
    session_id = getattr(handle, "session_id", None)
    extras = getattr(handle, "extras", None)
    if not session_id or not isinstance(extras, dict):
        return None
    now = time.time()
    idle = _positive_int(extras.get("idle_timeout_seconds"))
    limit = _positive_int(extras.get("max_lifetime_seconds"))
    activity = extras.get("activity")
    started_at = getattr(handle, "started_at", None)
    deadlines: list[tuple[float, str]] = []
    if limit and extras.get("created_here") and isinstance(started_at, (int, float)):
        deadlines.append((started_at + limit, "time_limit"))
    if idle and isinstance(activity, SandboxActivity) and not activity.busy:
        deadlines.append((activity.last_active_at + idle, "idle"))
    passed = [d for d in deadlines if d[0] <= now + _STOP_DEADLINE_SLACK_SECONDS]
    if passed:
        deadline, reason = min(passed)
        stopped_at = min(deadline, now)
    else:
        # 124 is Modal's exit code for a sandbox it timed out.
        reason = "timeout" if extras.get("exit_code") == 124 else "ended"
        stopped_at = now
    stop = SandboxStop(
        stopped_at=stopped_at,
        reason=reason,
        idle_timeout_seconds=idle,
        max_lifetime_seconds=limit,
    )
    with _SESSION_LOCK:
        _LAST_STOPS[session_id] = stop
    return stop


def get_last_stop(session_id: str | None) -> SandboxStop | None:
    if not session_id:
        return None
    with _SESSION_LOCK:
        return _LAST_STOPS.get(session_id)


def clear_last_stop(session_id: str | None) -> None:
    if not session_id:
        return
    with _SESSION_LOCK:
        _LAST_STOPS.pop(session_id, None)


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
        # A new sandbox makes the note about the previous one stale.
        _LAST_STOPS.pop(handle.session_id, None)


def unregister_handle(session_id: str | None) -> None:
    if not session_id:
        return
    with _SESSION_LOCK:
        _ACTIVE_SESSIONS.pop(session_id, None)


def clear_active_handles() -> None:
    with _SESSION_LOCK:
        _ACTIVE_SESSIONS.clear()
        _LAST_STOPS.clear()


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
