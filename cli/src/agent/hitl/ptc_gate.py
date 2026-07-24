"""HITL gate for PTC callables (tools.* inside run_python)."""

from __future__ import annotations

import logging
from typing import Any

from agent.hitl.config import SKILLS_MANAGE_TOOL, skills_manage_needs_approval
from agent.hitl.context import get_hitl_context
from agent.hitl.decisions import build_reject
from agent.hitl.grants import (
    apply_grants_from_decisions,
    grant_key_for_skills_kwargs,
    has_grant,
)
from agent.hitl.resume import collect_decisions_for_interrupt

logger = logging.getLogger("hitl")


def _review_configs_for_skills() -> list[dict[str, Any]]:
    return [
        {
            "action_name": SKILLS_MANAGE_TOOL,
            "allowed_decisions": ["approve", "edit", "reject"],
            "description": (
                "Approve skill install/remove for this run. One approve covers "
                "the rest of the batch (including loops inside run_python)."
            ),
        }
    ]


def apply_skills_manage_hitl(kwargs: dict[str, Any]) -> dict[str, Any] | None:
    """If approval is required, block for a decision.

    Returns:
    - ``None`` to proceed with (possibly edited) ``kwargs`` mutated in place
    - a result dict to return immediately (reject / cancel)
    """
    if not skills_manage_needs_approval(kwargs):
        return None

    ctx = get_hitl_context()
    session_id = ctx.session_id if ctx is not None else None
    if has_grant(
        grant_key_for_skills_kwargs(kwargs),
        ctx=ctx,
        session_id=session_id,
    ):
        return None

    action = str(kwargs.get("action") or "").strip().lower()
    kind = "remove" if action in {"remove", "uninstall"} else "install"
    action_requests = [
        {
            "name": SKILLS_MANAGE_TOOL,
            "args": {
                key: value
                for key, value in kwargs.items()
                if not str(key).startswith("_")
            },
            "description": (
                f"Allow skill {kind} for the rest of this run "
                "(covers batch loops)."
            ),
        }
    ]
    review_configs = _review_configs_for_skills()

    headless = bool(ctx.headless) if ctx is not None else True
    progress_callback = ctx.progress_callback if ctx is not None else None
    console = ctx.console if ctx is not None else None

    try:
        decisions = collect_decisions_for_interrupt(
            session_id=session_id,
            action_requests=action_requests,
            review_configs=review_configs,
            headless=headless,
            progress_callback=progress_callback,
            console=console,
        )
    except InterruptedError as exc:
        return {
            "ok": False,
            "blocked": True,
            "summary": str(exc) or "Skill action cancelled (run interrupted).",
            "error": str(exc) or "Run interrupted",
        }
    except Exception as exc:  # noqa: BLE001
        logger.warning("HITL PTC gate failed; rejecting skill action: %s", exc)
        return {
            "ok": False,
            "blocked": True,
            "summary": f"Skill action blocked; approval failed ({exc}).",
            "error": str(exc),
        }

    # Broker.submit already records session grants; keep ContextVar in sync too.
    apply_grants_from_decisions(
        decisions,
        action_requests,
        ctx=ctx,
        session_id=session_id,
    )

    if progress_callback is not None:
        try:
            progress_callback("approval_resolved", decisions=decisions)
        except Exception:  # noqa: BLE001
            logger.debug("approval_resolved callback failed", exc_info=True)

    decision = decisions[0] if decisions else build_reject()
    dtype = str(decision.get("type") or "").strip().lower()
    if dtype == "reject":
        message = str(decision.get("message") or "").strip() or (
            "User rejected this action. Do not retry the same tool call "
            "unless the user explicitly asks."
        )
        return {
            "ok": False,
            "blocked": True,
            "summary": message,
            "error": message,
            "rejected": True,
        }
    if dtype == "edit":
        edited = decision.get("edited_action")
        if isinstance(edited, dict) and isinstance(edited.get("args"), dict):
            # Replace public args with the human-edited set.
            for key in list(kwargs.keys()):
                if not str(key).startswith("_"):
                    kwargs.pop(key, None)
            kwargs.update(edited["args"])
        return None
    # approve (and unknown → treat as approve only if we got here validated)
    return None
