"""Session-scoped HITL grants so one Approve covers a batch of skill actions.

Grants are stored by ``session_id`` (thread-safe), not only on ContextVar state,
because PTC ``tools.*`` calls run inside ``asyncio.to_thread`` / sandbox workers
where ContextVar alone is easy to get wrong.
"""

from __future__ import annotations

import threading
from typing import Any

from agent.hitl.config import (
    SKILLS_MANAGE_TOOL,
    SLACK_SEND_TOOL,
    grant_key_for_slack_target,
)
from agent.hitl.context import HitlRunContext, get_hitl_context

_LOCK = threading.Lock()
# session_id → grant keys (e.g. "skills_manage:remove")
_SESSION_GRANTS: dict[str, set[str]] = {}


def _normalize_action(action: str) -> str:
    act = (action or "").strip().lower()
    if act in {"install", "add"}:
        return "install"
    if act in {"remove", "uninstall"}:
        return "remove"
    if act == "create":
        return "install"
    return act


def grant_key_for_action(action: dict[str, Any] | None) -> str | None:
    """Return a stable grant key for a HITL action request, or None if ungatable."""
    if not isinstance(action, dict):
        return None
    name = str(action.get("name") or "").strip()
    args = action.get("args") if isinstance(action.get("args"), dict) else {}
    if name == SLACK_SEND_TOOL:
        # Scoped to the destination: approving one channel must not silently
        # authorize every other channel for the rest of the run.
        return grant_key_for_slack_target(str(args.get("target") or ""))
    if name != SKILLS_MANAGE_TOOL:
        return None
    act = _normalize_action(str(args.get("action") or ""))
    if act not in {"install", "remove"}:
        return None
    return f"{SKILLS_MANAGE_TOOL}:{act}"


def grant_key_for_skills_kwargs(kwargs: dict[str, Any] | None) -> str | None:
    return grant_key_for_action(
        {
            "name": SKILLS_MANAGE_TOOL,
            "args": {
                key: value
                for key, value in (kwargs or {}).items()
                if not str(key).startswith("_")
            },
        }
    )


def _session_id(ctx: HitlRunContext | None = None, session_id: str | None = None) -> str:
    if session_id and str(session_id).strip():
        return str(session_id).strip()
    current = ctx if ctx is not None else get_hitl_context()
    if current is not None and current.session_id:
        return str(current.session_id).strip()
    return ""


def has_grant(
    key: str | None,
    *,
    ctx: HitlRunContext | None = None,
    session_id: str | None = None,
) -> bool:
    if not key:
        return False
    sid = _session_id(ctx, session_id)
    current = ctx if ctx is not None else get_hitl_context()
    if current is not None and key in current.grants:
        return True
    if not sid:
        return False
    with _LOCK:
        return key in _SESSION_GRANTS.get(sid, set())


def grant_remaining(
    key: str | None,
    *,
    ctx: HitlRunContext | None = None,
    session_id: str | None = None,
) -> None:
    if not key:
        return
    sid = _session_id(ctx, session_id)
    current = ctx if ctx is not None else get_hitl_context()
    if current is not None:
        current.grants.add(key)
    if not sid:
        return
    with _LOCK:
        _SESSION_GRANTS.setdefault(sid, set()).add(key)


def clear_session_grants(session_id: str | None) -> None:
    sid = (session_id or "").strip()
    if not sid:
        return
    with _LOCK:
        _SESSION_GRANTS.pop(sid, None)


def apply_grants_from_decisions(
    decisions: list[dict[str, Any]] | None,
    action_requests: list[dict[str, Any]] | None,
    *,
    ctx: HitlRunContext | None = None,
    session_id: str | None = None,
) -> list[str]:
    """Record grants from approve decisions.

    For ``skills_manage`` install/remove, any approve grants the rest of the
    run unless ``scope`` is explicitly ``once``.
    """
    applied: list[str] = []
    for decision, action in zip(decisions or [], action_requests or [], strict=False):
        if not isinstance(decision, dict) or not isinstance(action, dict):
            continue
        if str(decision.get("type") or "").strip().lower() != "approve":
            continue
        scope = str(decision.get("scope") or "remaining").strip().lower()
        if scope == "once":
            continue
        key = grant_key_for_action(action)
        if not key:
            continue
        if has_grant(key, ctx=ctx, session_id=session_id):
            continue
        grant_remaining(key, ctx=ctx, session_id=session_id)
        applied.append(key)
    return applied
