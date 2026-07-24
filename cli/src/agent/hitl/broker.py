"""Thread-safe approval wait/resume broker for headless (desktop) runs."""

from __future__ import annotations

import logging
import threading
import uuid
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("hitl")


@dataclass
class _Pending:
    interrupt_id: str
    action_requests: list[dict[str, Any]]
    review_configs: list[dict[str, Any]]
    event: threading.Event = field(default_factory=threading.Event)
    decisions: list[dict[str, Any]] | None = None
    cancelled: bool = False
    error: str | None = None


class ApprovalBroker:
    """One pending interrupt per session; waiters block until submit/cancel."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._pending: dict[str, _Pending] = {}

    def begin(
        self,
        session_id: str,
        *,
        action_requests: list[dict[str, Any]],
        review_configs: list[dict[str, Any]],
        interrupt_id: str | None = None,
    ) -> str:
        sid = (session_id or "").strip()
        if not sid:
            raise ValueError("session_id is required for HITL approvals.")
        iid = (interrupt_id or "").strip() or str(uuid.uuid4())
        with self._lock:
            existing = self._pending.get(sid)
            if existing is not None and not existing.event.is_set():
                existing.cancelled = True
                existing.error = "Superseded by a new approval request."
                existing.event.set()
            self._pending[sid] = _Pending(
                interrupt_id=iid,
                action_requests=list(action_requests),
                review_configs=list(review_configs),
            )
        return iid

    def get_pending(self, session_id: str) -> dict[str, Any] | None:
        sid = (session_id or "").strip()
        with self._lock:
            pending = self._pending.get(sid)
            if pending is None or pending.event.is_set():
                return None
            return {
                "interrupt_id": pending.interrupt_id,
                "action_requests": list(pending.action_requests),
                "review_configs": list(pending.review_configs),
            }

    def submit(
        self,
        session_id: str,
        decisions: list[dict[str, Any]],
        *,
        interrupt_id: str | None = None,
    ) -> None:
        from agent.hitl.decisions import validate_decisions
        from agent.hitl.grants import apply_grants_from_decisions

        sid = (session_id or "").strip()
        with self._lock:
            pending = self._pending.get(sid)
            if pending is None or pending.event.is_set():
                raise KeyError("No pending approval for this session.")
            if interrupt_id and interrupt_id != pending.interrupt_id:
                raise ValueError("interrupt_id does not match the pending approval.")
            normalized = validate_decisions(
                decisions,
                action_requests=pending.action_requests,
                review_configs=pending.review_configs,
            )
            # Record run grants immediately on submit (session-scoped), so later
            # PTC tool calls in worker threads see them even if ContextVar is empty.
            apply_grants_from_decisions(
                normalized,
                pending.action_requests,
                session_id=sid,
            )
            pending.decisions = list(normalized)
            pending.event.set()

    def cancel(self, session_id: str, *, reason: str = "Run interrupted") -> bool:
        sid = (session_id or "").strip()
        with self._lock:
            pending = self._pending.get(sid)
            if pending is None:
                return False
            if pending.event.is_set() and pending.decisions is not None:
                return False
            pending.cancelled = True
            pending.error = reason
            pending.event.set()
            return True

    def wait(
        self,
        session_id: str,
        *,
        timeout: float | None = None,
    ) -> list[dict[str, Any]]:
        sid = (session_id or "").strip()
        with self._lock:
            pending = self._pending.get(sid)
            if pending is None:
                raise KeyError("No pending approval for this session.")
            event = pending.event
        ok = event.wait(timeout=timeout)
        with self._lock:
            pending = self._pending.pop(sid, pending)
        if not ok:
            raise TimeoutError("Timed out waiting for human approval.")
        if pending.cancelled or pending.decisions is None:
            raise InterruptedError(pending.error or "Approval cancelled.")
        return list(pending.decisions)


_BROKER = ApprovalBroker()


def get_approval_broker() -> ApprovalBroker:
    return _BROKER
